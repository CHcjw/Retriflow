from __future__ import annotations

import re
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
            return [self._heuristic_rewrite(history_messages=history_messages, query=normalized_query)]

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

    def _heuristic_rewrite(
        self,
        *,
        history_messages: list[dict[str, str]],
        query: str,
    ) -> str:
        latest_user_question = self._latest_user_question(history_messages)
        if not latest_user_question or not self._looks_like_follow_up(query):
            return query

        city = self._extract_city(latest_user_question)
        if city and self._contains_weather_intent(latest_user_question) and self._contains_forecast_time(query):
            return f"{city}{query.rstrip('呢？?。')}天气怎么样？"

        return query

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
    def _latest_user_question(history_messages: list[dict[str, str]]) -> str:
        for message in reversed(history_messages):
            if str(message.get("role", "")).strip() != "user":
                continue
            content = str(message.get("content", "")).strip()
            if content:
                return content
        return ""

    @staticmethod
    def _looks_like_follow_up(query: str) -> bool:
        stripped = query.strip()
        return bool(stripped and (stripped.endswith("呢") or re.search(r"^(未来|明天|后天|接下来|那|还有)", stripped)))

    @staticmethod
    def _contains_weather_intent(text: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in ("天气", "气温", "温度", "预报", "weather", "forecast"))

    @staticmethod
    def _contains_forecast_time(text: str) -> bool:
        return bool(re.search(r"未来|明天|后天|三天|几天|预报", text))

    @staticmethod
    def _extract_city(text: str) -> str:
        for city in ("北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "武汉", "西安"):
            if city in text:
                return city
        return ""

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
