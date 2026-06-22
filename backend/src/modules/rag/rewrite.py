from __future__ import annotations

from typing import Any

from infra.llm import RetriFlowLLMService
from modules.rag.prompt import get_prompt_template_loader
from modules.rag.term_mapping import QueryTermMappingService


class RetriFlowQueryRewriteService:
    def __init__(self) -> None:
        self.llm_service = RetriFlowLLMService()
        self.term_mapping_service = QueryTermMappingService()
        self.prompt_loader = get_prompt_template_loader()

    def rewrite(
        self,
        *,
        history_messages: list[dict[str, str]],
        query: str,
    ) -> list[str]:
        normalized_query = self.term_mapping_service.normalize(query.strip()).strip()
        if not normalized_query:
            return []

        provider = self.llm_service._resolve_provider(capability="rewrite")
        if provider is None or provider.name == "disabled":
            return [normalized_query]

        try:
            payload = self.llm_service.extract_json_object(
                system_prompt=self.prompt_loader.render_section("rewrite.md", "system"),
                user_prompt=self._build_user_prompt(
                    history_messages=history_messages,
                    query=normalized_query,
                ),
                capability="rewrite",
            )
        except Exception:
            return [normalized_query]
        return self._normalize_queries(payload, fallback_query=normalized_query)

    def _build_user_prompt(
        self,
        *,
        history_messages: list[dict[str, str]],
        query: str,
    ) -> str:
        history_lines: list[str] = []
        for message in history_messages:
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"system", "user", "assistant"} or not content:
                continue
            role_name = {
                "system": "系统",
                "user": "用户",
                "assistant": "助手",
            }[role]
            history_lines.append(f"{role_name}：{content}")

        history_text = "\n".join(history_lines).strip() or "无"
        return self.prompt_loader.render_section(
            "rewrite.md",
            "user",
            {"history": history_text, "query": query},
        )

    @staticmethod
    def _normalize_queries(payload: dict[str, Any], fallback_query: str) -> list[str]:
        raw_queries = payload.get("queries", [])
        if not isinstance(raw_queries, list):
            return [fallback_query]

        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_queries:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)

        return normalized or [fallback_query]
