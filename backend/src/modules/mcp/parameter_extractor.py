from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import quote_plus

from core.config import get_settings
from infra.llm import RetriFlowLLMService
from modules.mcp.models import McpToolDefinition


class RetriFlowMcpParameterExtractor:
    KNOWN_CITIES = [
        "北京",
        "上海",
        "广州",
        "深圳",
        "杭州",
        "南京",
        "苏州",
        "成都",
        "武汉",
        "西安",
        "重庆",
        "长沙",
        "天津",
        "郑州",
        "青岛",
        "厦门",
        "昆明",
        "哈尔滨",
    ]
    KNOWN_REGIONS = ["华东", "华北", "华南", "华中", "西南", "全国"]

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = RetriFlowLLMService()

    def extract(
        self,
        question: str,
        tool_definition: McpToolDefinition,
        param_prompt_template: str = "",
    ) -> dict[str, object]:
        if self._llm_is_available():
            extracted = self._try_llm_extract(
                question=question,
                tool_definition=tool_definition,
                param_prompt_template=param_prompt_template,
            )
            if extracted:
                return self._fill_defaults(extracted, tool_definition)

        heuristic = self._heuristic_extract(
            question=question,
            tool_definition=tool_definition,
        )
        return self._fill_defaults(heuristic, tool_definition)

    def _llm_is_available(self) -> bool:
        provider = self.llm_service._resolve_provider(capability="rewrite")
        return provider is not None and provider.name != "disabled"

    def _try_llm_extract(
        self,
        question: str,
        tool_definition: McpToolDefinition,
        param_prompt_template: str = "",
    ) -> dict[str, object]:
        system_prompt = param_prompt_template.strip() or (
            "你是 MCP 工具参数提取器。"
            "请根据给定工具定义，从用户问题中提取参数。"
            "只返回 JSON 对象，不要输出解释。"
        )
        user_prompt = (
            f"工具 ID: {tool_definition.tool_id}\n"
            f"工具描述: {tool_definition.description}\n"
            f"参数 Schema: {tool_definition.parameter_schema}\n"
            f"用户问题: {question}"
        )
        try:
            return self.llm_service.extract_json_object(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                capability="rewrite",
            )
        except Exception:
            return {}

    def _heuristic_extract(
        self,
        question: str,
        tool_definition: McpToolDefinition,
    ) -> dict[str, object]:
        tool_id = tool_definition.tool_id
        lowered_tool_id = tool_id.lower()

        if tool_id == "weather_query":
            city = self._extract_city(question)
            query_type = "forecast" if re.search(r"明天|后天|未来|预报|三天|几天|近几日", question) else "current"
            return {"city": city, "query_type": query_type}

        if "aisearch" in lowered_tool_id or "ai_search" in lowered_tool_id:
            return {
                "query": self._normalize_search_query(question),
                "model": "ernie-3.5-8k",
            }

        if tool_id == "get_forecast":
            city = self._extract_city(question)
            return {
                "location_name": city,
                "days": 1 if re.search(r"今天|今日|现在", question) else 3,
            }

        if tool_id == "get_current_conditions":
            return {"location_name": self._extract_city(question)}

        if tool_id == "get-weather-forecast":
            city = self._normalize_china_city_name(self._extract_city(question))
            forecast_type = "forecast" if re.search(r"明天|后天|未来|预报|三天|几天", question) else "current"
            return {
                "cityName": city,
                "date": self._extract_relative_date(question).isoformat(),
                "forecastType": forecast_type,
            }

        if tool_id == "search_location":
            return {"query": self._extract_city(question)}

        if tool_id == "sales_query":
            region = self._extract_region(question)
            period = "this_month"
            if re.search(r"今天|今日", question):
                period = "today"
            elif re.search(r"本周", question):
                period = "this_week"
            elif re.search(r"本季|本季度", question):
                period = "this_quarter"
            return {"region": region, "period": period}

        return self._generic_text_parameters(question, tool_definition)

    def _extract_city(self, question: str) -> str:
        for city in self.KNOWN_CITIES:
            if city in question:
                return city
        return "北京"

    @staticmethod
    def _normalize_china_city_name(city: str) -> str:
        if city.endswith("市"):
            return city
        return f"{city}市"

    @staticmethod
    def _extract_relative_date(question: str) -> date:
        today = date.today()
        if "后天" in question:
            return today + timedelta(days=2)
        if "明天" in question:
            return today + timedelta(days=1)
        return today

    def _extract_region(self, question: str) -> str:
        for region in self.KNOWN_REGIONS:
            if region in question:
                return region
        return "全国"

    @staticmethod
    def _normalize_search_query(question: str) -> str:
        query = question.strip()
        query = re.sub(r"^请?(帮我)?(用)?(mcp|MCP)?(上网|联网|网上)?搜索", "", query).strip()
        query = re.sub(r"^请?(帮我)?(上网查|网上查|查网页|联网查)", "", query).strip()
        return query or question.strip()

    @staticmethod
    def _fill_defaults(
        parameters: dict[str, object],
        tool_definition: McpToolDefinition,
    ) -> dict[str, object]:
        result = dict(parameters)
        properties = tool_definition.parameter_schema.get("properties", {}) if isinstance(tool_definition.parameter_schema, dict) else {}
        if not isinstance(properties, dict):
            return result
        for name, schema in properties.items():
            if name not in result and isinstance(schema, dict) and "default" in schema:
                result[name] = schema["default"]
        return result

    @staticmethod
    def _generic_text_parameters(question: str, tool_definition: McpToolDefinition) -> dict[str, object]:
        properties = tool_definition.parameter_schema.get("properties", {}) if isinstance(tool_definition.parameter_schema, dict) else {}
        if not isinstance(properties, dict):
            return {}
        result: dict[str, object] = {}
        for name, schema in properties.items():
            if not isinstance(schema, dict):
                continue
            lowered = str(name).lower()
            if lowered in {"query", "q", "keyword", "keywords", "text", "prompt", "input"}:
                result[name] = question
            elif lowered in {"url", "uri"} and not result:
                result[name] = f"https://www.baidu.com/s?wd={quote_plus(question)}"
        return result
