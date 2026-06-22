from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import threading
import time
import uuid
from typing import Any

from core.config import get_settings


@dataclass
class ChatQueueTicket:
    request_id: str
    acquired: bool
    reason: str = ""
    _limiter: "RetriFlowFairQueueLimiter | RetriFlowRedisQueueLimiter | None" = None
    _released: bool = False

    def release(self) -> None:
        if self._released or self._limiter is None or not self.acquired:
            return
        self._released = True
        self._limiter.release(self.request_id)

    def __enter__(self) -> "ChatQueueTicket":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class RetriFlowFairQueueLimiter:
    def __init__(self, *, max_concurrent: int) -> None:
        self.max_concurrent = max(1, int(max_concurrent))
        self._condition = threading.Condition()
        self._queue: deque[str] = deque()
        self._active: set[str] = set()

    def acquire(self, *, max_wait_seconds: float, cancel_event: threading.Event | None = None) -> ChatQueueTicket:
        request_id = uuid.uuid4().hex
        deadline = time.monotonic() + max(0.0, float(max_wait_seconds))
        with self._condition:
            self._queue.append(request_id)
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    self._remove_queued(request_id)
                    self._condition.notify_all()
                    return ChatQueueTicket(request_id=request_id, acquired=False, reason="cancelled")

                if self._can_grant(request_id):
                    self._queue.popleft()
                    self._active.add(request_id)
                    return ChatQueueTicket(request_id=request_id, acquired=True, _limiter=self)

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._remove_queued(request_id)
                    self._condition.notify_all()
                    return ChatQueueTicket(request_id=request_id, acquired=False, reason="timeout")

                self._condition.wait(timeout=min(remaining, 0.05))

    def release(self, request_id: str) -> None:
        with self._condition:
            self._active.discard(request_id)
            self._condition.notify_all()

    def snapshot(self) -> dict[str, int | str]:
        with self._condition:
            active_count = len(self._active)
            queued_count = len(self._queue)
        return {
            "backend": "memory",
            "max_concurrent": self.max_concurrent,
            "active_count": active_count,
            "queued_count": queued_count,
            "available_permits": max(0, self.max_concurrent - active_count),
        }

    def _can_grant(self, request_id: str) -> bool:
        return bool(self._queue) and self._queue[0] == request_id and len(self._active) < self.max_concurrent

    def _remove_queued(self, request_id: str) -> None:
        try:
            self._queue.remove(request_id)
        except ValueError:
            pass


class RetriFlowRedisQueueLimiter:
    _CLAIM_LUA = """
local queueKey = KEYS[1]
local activeKey = KEYS[2]
local requestId = ARGV[1]
local maxPermits = tonumber(ARGV[2])
local entryPrefix = ARGV[3]
local activeTtlMillis = tonumber(ARGV[4])

local active = tonumber(redis.call('GET', activeKey) or '0')
local available = maxPermits - active
if available <= 0 then return {0} end

local slack = 16
local headEntries = redis.call('ZRANGE', queueKey, 0, available + slack - 1)
local liveRank = -1
local liveCount = 0
for i = 1, #headEntries do
    local member = headEntries[i]
    if redis.call('EXISTS', entryPrefix .. member) == 1 then
        if member == requestId then
            liveRank = liveCount
        end
        liveCount = liveCount + 1
    else
        redis.call('ZREM', queueKey, member)
    end
end

if liveRank < 0 or liveRank >= available then return {0} end

local score = redis.call('ZSCORE', queueKey, requestId)
redis.call('ZREM', queueKey, requestId)
redis.call('DEL', entryPrefix .. requestId)
redis.call('INCR', activeKey)
redis.call('PEXPIRE', activeKey, activeTtlMillis)
return {1, score}
"""

    _RELEASE_LUA = """
local activeKey = KEYS[1]
local active = tonumber(redis.call('GET', activeKey) or '0')
if active <= 1 then
    redis.call('DEL', activeKey)
    return 0
end
return redis.call('DECR', activeKey)
"""

    def __init__(
        self,
        *,
        redis_url: str,
        key_prefix: str,
        max_concurrent: int,
        lease_seconds: int,
        poll_interval_ms: int,
    ) -> None:
        import redis

        self.redis_url = redis_url
        self.key_prefix = key_prefix.rstrip(":")
        self.max_concurrent = max(1, int(max_concurrent))
        self.lease_seconds = max(1, int(lease_seconds))
        self.poll_interval_ms = max(20, int(poll_interval_ms))
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._queue_key = f"{self.key_prefix}:queue"
        self._seq_key = f"{self.key_prefix}:queue:seq"
        self._active_key = f"{self.key_prefix}:active"
        self._notify_key = f"{self.key_prefix}:queue:notify"
        self._entry_prefix = f"{self.key_prefix}:entry:"

    def acquire(self, *, max_wait_seconds: float, cancel_event: threading.Event | None = None) -> ChatQueueTicket:
        request_id = uuid.uuid4().hex
        max_wait_seconds = max(0.0, float(max_wait_seconds))
        deadline = time.monotonic() + max_wait_seconds
        ttl_ms = int((max_wait_seconds * 1000) + 5000)
        self._redis.set(f"{self._entry_prefix}{request_id}", "1", px=max(1, ttl_ms))
        self._redis.zadd(self._queue_key, {request_id: self._next_score()})

        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(self._notify_key)
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    self._cleanup_request(request_id)
                    return ChatQueueTicket(request_id=request_id, acquired=False, reason="cancelled")

                if self._claim_if_ready(request_id):
                    return ChatQueueTicket(request_id=request_id, acquired=True, _limiter=self)  # type: ignore[arg-type]

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._cleanup_request(request_id)
                    return ChatQueueTicket(request_id=request_id, acquired=False, reason="timeout")

                wait_timeout = min(remaining, self.poll_interval_ms / 1000)
                if cancel_event is not None:
                    wait_timeout = min(wait_timeout, 0.05)
                self._wait_for_notify(pubsub, timeout=wait_timeout)
        finally:
            pubsub.close()

    def release(self, request_id: str) -> None:
        self._redis.eval(self._RELEASE_LUA, 1, self._active_key)
        self._redis.publish(self._notify_key, "permit_changed")

    def snapshot(self) -> dict[str, int | str]:
        active_count = int(self._redis.get(self._active_key) or 0)
        queued_count = int(self._redis.zcard(self._queue_key) or 0)
        return {
            "backend": "redis",
            "max_concurrent": self.max_concurrent,
            "active_count": max(0, active_count),
            "queued_count": max(0, queued_count),
            "available_permits": max(0, self.max_concurrent - active_count),
        }

    def _claim_if_ready(self, request_id: str) -> bool:
        result: list[Any] = self._redis.eval(
            self._CLAIM_LUA,
            2,
            self._queue_key,
            self._active_key,
            request_id,
            str(self.max_concurrent),
            self._entry_prefix,
            str(self.lease_seconds * 1000),
        )
        return bool(result and int(result[0]) == 1)

    def _next_score(self) -> int:
        return int(self._redis.incr(self._seq_key))

    def _cleanup_request(self, request_id: str) -> None:
        self._redis.zrem(self._queue_key, request_id)
        self._redis.delete(f"{self._entry_prefix}{request_id}")
        self._redis.publish(self._notify_key, "permit_changed")

    @staticmethod
    def _wait_for_notify(pubsub: Any, *, timeout: float) -> None:
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            message = pubsub.get_message(timeout=remaining)
            if message and message.get("type") == "message":
                return


_CHAT_QUEUE_LIMITER: RetriFlowFairQueueLimiter | RetriFlowRedisQueueLimiter | None = None


def get_chat_queue_limiter() -> RetriFlowFairQueueLimiter | RetriFlowRedisQueueLimiter:
    global _CHAT_QUEUE_LIMITER
    settings = get_settings()
    backend = settings.chat_queue_backend.strip().lower()
    if backend == "redis":
        if (
            _CHAT_QUEUE_LIMITER is None
            or not isinstance(_CHAT_QUEUE_LIMITER, RetriFlowRedisQueueLimiter)
            or _CHAT_QUEUE_LIMITER.redis_url != settings.chat_queue_redis_url
            or _CHAT_QUEUE_LIMITER.max_concurrent != settings.chat_queue_max_concurrent
        ):
            _CHAT_QUEUE_LIMITER = RetriFlowRedisQueueLimiter(
                redis_url=settings.chat_queue_redis_url,
                key_prefix=settings.chat_queue_redis_key_prefix,
                max_concurrent=settings.chat_queue_max_concurrent,
                lease_seconds=settings.chat_queue_lease_seconds,
                poll_interval_ms=settings.chat_queue_poll_interval_ms,
            )
        return _CHAT_QUEUE_LIMITER

    if (
        _CHAT_QUEUE_LIMITER is None
        or not isinstance(_CHAT_QUEUE_LIMITER, RetriFlowFairQueueLimiter)
        or _CHAT_QUEUE_LIMITER.max_concurrent != settings.chat_queue_max_concurrent
    ):
        _CHAT_QUEUE_LIMITER = RetriFlowFairQueueLimiter(max_concurrent=settings.chat_queue_max_concurrent)
    return _CHAT_QUEUE_LIMITER


def reset_chat_queue_limiter() -> None:
    global _CHAT_QUEUE_LIMITER
    _CHAT_QUEUE_LIMITER = None
