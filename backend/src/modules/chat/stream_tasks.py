from __future__ import annotations

import uuid

from core.config import get_settings


class RetriFlowStreamTaskManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._cancelled_local: set[str] = set()

    def create_task_id(self) -> str:
        return f"stream-{uuid.uuid4().hex}"

    def cancel(self, task_id: str) -> None:
        normalized = task_id.strip()
        if not normalized:
            return
        self._cancelled_local.add(normalized)
        try:
            self._client().set(
                self._cancel_key(normalized),
                "1",
                ex=max(1, self.settings.stream_task_cancel_ttl_seconds),
            )
        except Exception:
            return

    def is_cancelled(self, task_id: str) -> bool:
        normalized = task_id.strip()
        if not normalized:
            return False
        if normalized in self._cancelled_local:
            return True
        try:
            cancelled = bool(self._client().exists(self._cancel_key(normalized)))
        except Exception:
            return False
        if cancelled:
            self._cancelled_local.add(normalized)
        return cancelled

    def unregister(self, task_id: str) -> None:
        normalized = task_id.strip()
        if not normalized:
            return
        self._cancelled_local.discard(normalized)
        try:
            self._client().delete(self._cancel_key(normalized))
        except Exception:
            return

    def _cancel_key(self, task_id: str) -> str:
        return f"{self.settings.stream_task_cancel_key_prefix.rstrip(':')}:{task_id}"

    def _client(self):
        import redis

        return redis.Redis.from_url(
            self.settings.stream_task_cancel_redis_url,
            decode_responses=True,
        )


_STREAM_TASK_MANAGER = RetriFlowStreamTaskManager()


def get_stream_task_manager() -> RetriFlowStreamTaskManager:
    return _STREAM_TASK_MANAGER
