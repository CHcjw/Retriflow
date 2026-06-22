from __future__ import annotations

import json
from typing import Any

from core.config import get_settings
from core.state import get_connection


class QueryTermMappingCacheManager:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_mappings_from_cache(self) -> list[dict[str, Any]] | None:
        if not self.settings.query_term_mapping_cache_enabled:
            return None
        try:
            raw = self._client().get(self.settings.query_term_mapping_cache_key)
            if not raw:
                return None
            payload = json.loads(raw)
            return payload if isinstance(payload, list) else None
        except Exception:
            return None

    def save_mappings_to_cache(self, mappings: list[dict[str, Any]]) -> None:
        if not self.settings.query_term_mapping_cache_enabled:
            return
        try:
            self._client().set(
                self.settings.query_term_mapping_cache_key,
                json.dumps(mappings, ensure_ascii=False),
                ex=max(1, self.settings.query_term_mapping_cache_ttl_days) * 24 * 60 * 60,
            )
        except Exception:
            return

    def clear_cache(self) -> None:
        if not self.settings.query_term_mapping_cache_enabled:
            return
        try:
            self._client().delete(self.settings.query_term_mapping_cache_key)
        except Exception:
            return

    def _client(self):
        import redis

        return redis.Redis.from_url(
            self.settings.query_term_mapping_cache_redis_url,
            decode_responses=True,
        )


class QueryTermMappingService:
    def __init__(self) -> None:
        self.cache_manager = QueryTermMappingCacheManager()

    def normalize(self, text: str) -> str:
        if not text:
            return text

        result = text
        for mapping in self._load_mappings():
            if not mapping.get("enabled", True):
                continue
            if str(mapping.get("match_type") or "exact") != "exact":
                continue
            source = str(mapping.get("raw_keyword") or "")
            target = str(mapping.get("target_keyword") or "")
            if not source or not target:
                continue
            result = self._apply_mapping(result, source, target)
        return result

    def _load_mappings(self) -> list[dict[str, Any]]:
        cached = self.cache_manager.get_mappings_from_cache()
        if cached:
            return cached

        mappings = self._load_mappings_from_db()
        self.cache_manager.save_mappings_to_cache(mappings)
        return mappings

    @staticmethod
    def _load_mappings_from_db() -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select raw_keyword, target_keyword, match_type, priority, enabled, knowledge_base_id
                from admin_keyword_mappings
                where enabled = 1
                order by priority desc, length(raw_keyword) desc, raw_keyword
                """
            ).fetchall()
        return [
            {
                "raw_keyword": str(row["raw_keyword"]),
                "target_keyword": str(row["target_keyword"]),
                "match_type": str(row["match_type"] or "exact"),
                "priority": int(row["priority"] or 0),
                "enabled": bool(row["enabled"]),
                "knowledge_base_id": str(row["knowledge_base_id"] or ""),
            }
            for row in rows
        ]

    @staticmethod
    def _apply_mapping(text: str, source: str, target: str) -> str:
        if not text or not source:
            return text

        parts: list[str] = []
        index = 0
        source_len = len(source)
        target_len = len(target)
        while index < len(text):
            hit = text.find(source, index)
            if hit < 0:
                parts.append(text[index:])
                break
            parts.append(text[index:hit])
            if target and text.startswith(target, hit):
                parts.append(text[hit : hit + target_len])
                index = hit + target_len
            else:
                parts.append(target)
                index = hit + source_len
        return "".join(parts)
