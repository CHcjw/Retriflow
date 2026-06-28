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
    KNOWN_REGIONS = ["\u534e\u4e1c", "\u534e\u5317", "\u534e\u5357", "\u534e\u4e2d", "\u897f\u5357", "\u897f\u5317", "\u5168\u56fd"]

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
            period = "\u672c\u6708"
            if re.search("\u4eca\u5929|\u4eca\u65e5", question):
                period = "today"
            elif re.search("\u672c\u5468|\u8fd9\u5468", question):
                period = "this_week"
            elif re.search("\u4e0a\u6708|\u4e0a\u4e2a\u6708", question):
                period = "\u4e0a\u6708"
            elif re.search("\u672c\u5b63|\u672c\u5b63\u5ea6", question):
                period = "\u672c\u5b63\u5ea6"
            elif re.search("\u4e0a\u5b63|\u4e0a\u5b63\u5ea6", question):
                period = "\u4e0a\u5b63\u5ea6"
            elif re.search("\u4eca\u5e74|\u672c\u5e74", question):
                period = "\u672c\u5e74"

            query_type = "summary"
            if re.search("\u6392\u884c|\u6392\u540d|\u699c\u5355|top\\s*\\d+|\u524d\\s*\\d+", question, re.I):
                query_type = "ranking"
            if re.search("\u660e\u7ec6|\u8be6\u60c5|\u8bb0\u5f55|\u5217\u8868", question):
                query_type = "detail"
            if re.search("\u8d8b\u52bf|\u8d70\u52bf|\u53d8\u5316", question):
                query_type = "trend"

            params: dict[str, object] = {
                "region": region,
                "period": period,
                "queryType": query_type,
                "limit": self._extract_limit(question),
                "includeRegionBreakdown": bool(re.search("\u6240\u6709\u5730\u533a|\u5404\u5730\u533a|\u6bcf\u4e2a\u5730\u533a|\u5730\u533a.*\u5360\u6bd4|\u9500\u552e\u5360\u6bd4|\u5360\u6bd4\u5206\u6790", question)),
                "includeSalespersonRanking": bool(re.search("\u9500\u552e\u4eba\u5458|\u9500\u552e\u5458|\u4eba\u5458.*\u6392\u884c|\u4eba\u5458.*\u6392\u540d|\u6392\u884c\u699c|\u6392\u540d", question)),
                "includeCustomerSales": bool(re.search("\u6240\u552e\u4f01\u4e1a|\u5ba2\u6237|\u4f01\u4e1a.*\u9500\u552e\u989d|\u516c\u53f8.*\u9500\u552e\u989d", question)),
            }
            if product := self._extract_product(question):
                params["product"] = product
            if sales_person := self._extract_sales_person(question):
                params["salesPerson"] = sales_person
            return params

        if tool_id == "ticket_query":
            params: dict[str, object] = {
                "region": self._extract_region(question),
                "queryType": "summary",
                "limit": self._extract_limit(question),
            }
            if "待处理" in question or "未处理" in question:
                params["status"] = "待处理"
            elif "处理中" in question:
                params["status"] = "处理中"
            elif "已解决" in question:
                params["status"] = "已解决"
            elif "已关闭" in question or "关闭" in question:
                params["status"] = "已关闭"

            if "紧急" in question:
                params["priority"] = "紧急"
                params["queryType"] = "list"
            elif "高优先级" in question or "高优" in question:
                params["priority"] = "高"
                params["queryType"] = "list"

            if any(token in question for token in ("有哪些", "列表", "明细", "进展")):
                params["queryType"] = "list"
            if any(token in question for token in ("统计", "分布", "解决率", "分析")):
                params["queryType"] = "stats"
            if product := self._extract_product(question):
                params["product"] = product
            customer = self._extract_customer_name(question)
            if customer:
                params["customerName"] = customer
            return params

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
        return "\u5168\u56fd"

    @staticmethod
    def _extract_product(question: str) -> str:
        for product in ("\u4f01\u4e1a\u7248", "\u4e13\u4e1a\u7248", "\u57fa\u7840\u7248"):
            if product in question:
                return product
        return ""

    @staticmethod
    def _extract_sales_person(question: str) -> str:
        for person in ("\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94", "\u8d75\u516d", "\u94b1\u4e03", "\u5b59\u516b", "\u5468\u4e5d", "\u5434\u5341", "\u90d1\u51ac", "\u9648\u6625", "\u6797\u590f", "\u9ec4\u79cb", "\u5218\u4e00", "\u6768\u4e8c", "\u9a6c\u4e09"):
            if person in question:
                return person
        return ""

    @staticmethod
    def _extract_customer_name(question: str) -> str:
        for customer in ("腾讯科技", "阿里巴巴", "字节跳动", "网易公司", "美团点评", "京东集团", "小米科技", "格力电器", "百度在线", "华为技术", "中兴通讯", "用友网络"):
            if customer in question:
                return customer
        return ""

    @staticmethod
    def _extract_limit(question: str) -> int:
        match = re.search("(?:top|\u524d)\\s*(\\d+)", question, re.I)
        if match:
            return max(1, min(int(match.group(1)), 50))
        chinese_digits = {"\u4e00": 1, "\u4e8c": 2, "\u4e09": 3, "\u56db": 4, "\u4e94": 5, "\u516d": 6, "\u4e03": 7, "\u516b": 8, "\u4e5d": 9, "\u5341": 10}
        match = re.search("\u524d([\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341])", question)
        if match:
            return chinese_digits[match.group(1)]
        return 10

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
