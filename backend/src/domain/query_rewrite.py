from __future__ import annotations

from typing import Any

from domain.llm import RetriFlowLLMService


class RetriFlowQueryRewriteService:
    SYSTEM_PROMPT = (
        "你是一个查询改写助手。根据对话历史和用户的最新问题，将问题改写为适合检索的查询。\n\n"
        "要求：\n"
        "1. 补全代词和省略的上下文信息\n"
        "2. 将口语化表达转化为更正式、更适合检索的表达\n"
        "3. 如果问题包含多个独立意图，拆分为多个子查询\n"
        "4. 如果问题已经完整清晰且只有一个意图，只输出一个查询\n"
        "5. 以 JSON 格式输出，格式为：{\"queries\": [\"查询1\", \"查询2\"]}\n"
        "6. 不要输出 JSON 以外的任何内容"
    )

    def __init__(self) -> None:
        self.llm_service = RetriFlowLLMService()

    def rewrite(
        self,
        *,
        history_messages: list[dict[str, str]],
        query: str,
    ) -> list[str]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        provider = self.llm_service._resolve_provider(capability="rewrite")
        if provider is None or provider.name == "disabled":
            return [normalized_query]

        payload = self.llm_service.extract_json_object(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(history_messages=history_messages, query=normalized_query),
            capability="rewrite",
        )
        return self._normalize_queries(payload, fallback_query=normalized_query)

    @staticmethod
    def _build_user_prompt(
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
        return f"对话历史：\n{history_text}\n\n用户最新问题：{query}"

    @staticmethod
    def _normalize_queries(payload: dict[str, Any], fallback_query: str) -> list[str]:
        raw_queries = payload.get("queries", [])
        if not isinstance(raw_queries, list):
            return [fallback_query]

        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_queries:
            text = str(item).strip()
            if not text:
                continue
            if text in seen:
                continue
            seen.add(text)
            normalized.append(text)

        return normalized or [fallback_query]
