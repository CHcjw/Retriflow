from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Iterator
from uuid import uuid4

from core.config import get_settings


@dataclass(frozen=True)
class _MemoryLockRecord:
    token: str
    expires_at: float


class DistributedLockService:
    _memory_guard = Lock()
    _memory_locks: dict[str, _MemoryLockRecord] = {}

    def __init__(
        self,
        *,
        backend: str,
        redis_url: str,
        key_prefix: str,
        ttl_seconds: int,
    ) -> None:
        self.backend = backend.strip().lower()
        self.redis_url = redis_url
        self.key_prefix = key_prefix.strip().rstrip(":") or "retriflow:lock"
        self.ttl_seconds = max(1, ttl_seconds)
        self._redis = None

    @contextmanager
    def acquire(self, key: str, *, ttl_seconds: int | None = None) -> Iterator[bool]:
        normalized_key = self._normalize_key(key)
        token = uuid4().hex
        ttl = max(1, ttl_seconds or self.ttl_seconds)

        if self.backend == "redis":
            acquired = self._acquire_redis(normalized_key, token, ttl)
            if acquired:
                try:
                    yield True
                finally:
                    self._release_redis(normalized_key, token)
                return
            if self._redis is not None:
                yield False
                return

        acquired = self._acquire_memory(normalized_key, token, ttl)
        try:
            yield acquired
        finally:
            if acquired:
                self._release_memory(normalized_key, token)

    def _normalize_key(self, key: str) -> str:
        cleaned = ":".join(part.strip() for part in key.split(":") if part.strip())
        return f"{self.key_prefix}:{cleaned or 'default'}"

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis

            self._redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
            self._redis.ping()
        except Exception:
            self._redis = None
        return self._redis

    def _acquire_redis(self, key: str, token: str, ttl_seconds: int) -> bool:
        client = self._get_redis()
        if client is None:
            return False
        try:
            return bool(client.set(key, token, nx=True, ex=ttl_seconds))
        except Exception:
            self._redis = None
            return False

    def _release_redis(self, key: str, token: str) -> None:
        client = self._get_redis()
        if client is None:
            return
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        end
        return 0
        """
        try:
            client.eval(script, 1, key, token)
        except Exception:
            self._redis = None

    def _acquire_memory(self, key: str, token: str, ttl_seconds: int) -> bool:
        now = monotonic()
        expires_at = now + ttl_seconds
        with self._memory_guard:
            record = self._memory_locks.get(key)
            if record is not None and record.expires_at > now:
                return False
            self._memory_locks[key] = _MemoryLockRecord(token=token, expires_at=expires_at)
            return True

    def _release_memory(self, key: str, token: str) -> None:
        with self._memory_guard:
            record = self._memory_locks.get(key)
            if record is not None and record.token == token:
                self._memory_locks.pop(key, None)


_LOCK_SERVICE: DistributedLockService | None = None
_LOCK_SIGNATURE: tuple[str, str, str, int] | None = None


def get_distributed_lock_service() -> DistributedLockService:
    global _LOCK_SERVICE, _LOCK_SIGNATURE

    settings = get_settings()
    signature = (
        settings.distributed_lock_backend,
        settings.distributed_lock_redis_url,
        settings.distributed_lock_key_prefix,
        settings.distributed_lock_ttl_seconds,
    )
    if _LOCK_SERVICE is None or _LOCK_SIGNATURE != signature:
        _LOCK_SERVICE = DistributedLockService(
            backend=settings.distributed_lock_backend,
            redis_url=settings.distributed_lock_redis_url,
            key_prefix=settings.distributed_lock_key_prefix,
            ttl_seconds=settings.distributed_lock_ttl_seconds,
        )
        _LOCK_SIGNATURE = signature
    return _LOCK_SERVICE
