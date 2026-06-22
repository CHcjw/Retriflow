from __future__ import annotations

import json
from typing import Any

from core.config import get_settings


class IntentTreeCacheManager:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_intent_tree_from_cache(self) -> list[dict[str, Any]] | None:
        if not self.settings.intent_tree_cache_enabled:
            return None
        try:
            client = self._client()
            raw = client.get(self.settings.intent_tree_cache_key)
            if not raw:
                return None
            payload = json.loads(raw)
            return payload if isinstance(payload, list) else None
        except Exception:
            return None

    def save_intent_tree_to_cache(self, roots: list[dict[str, Any]]) -> None:
        if not self.settings.intent_tree_cache_enabled:
            return
        try:
            client = self._client()
            client.set(
                self.settings.intent_tree_cache_key,
                json.dumps(roots, ensure_ascii=False),
                ex=max(1, self.settings.intent_tree_cache_ttl_days) * 24 * 60 * 60,
            )
        except Exception:
            return

    def clear_intent_tree_cache(self) -> None:
        if not self.settings.intent_tree_cache_enabled:
            return
        try:
            self._client().delete(self.settings.intent_tree_cache_key)
        except Exception:
            return

    def is_cache_exists(self) -> bool:
        if not self.settings.intent_tree_cache_enabled:
            return False
        try:
            return bool(self._client().exists(self.settings.intent_tree_cache_key))
        except Exception:
            return False

    def get_cache_status(self) -> dict[str, Any]:
        if not self.settings.intent_tree_cache_enabled:
            return {
                "enabled": False,
                "available": False,
                "exists": False,
                "key": self.settings.intent_tree_cache_key,
                "ttl_seconds": None,
                "ttl_days": self.settings.intent_tree_cache_ttl_days,
                "backend": "redis",
                "error": "",
            }
        try:
            client = self._client()
            exists = bool(client.exists(self.settings.intent_tree_cache_key))
            ttl = client.ttl(self.settings.intent_tree_cache_key) if exists else None
            if ttl is not None and ttl < 0:
                ttl = None
            return {
                "enabled": True,
                "available": True,
                "exists": exists,
                "key": self.settings.intent_tree_cache_key,
                "ttl_seconds": ttl,
                "ttl_days": self.settings.intent_tree_cache_ttl_days,
                "backend": "redis",
                "error": "",
            }
        except Exception as exc:
            return {
                "enabled": True,
                "available": False,
                "exists": False,
                "key": self.settings.intent_tree_cache_key,
                "ttl_seconds": None,
                "ttl_days": self.settings.intent_tree_cache_ttl_days,
                "backend": "redis",
                "error": str(exc),
            }

    def _client(self):
        import redis

        return redis.Redis.from_url(self.settings.intent_tree_cache_redis_url, decode_responses=True)
