from __future__ import annotations

from abc import ABC, abstractmethod

from domain.mcp.models import McpToolCallResult, McpToolDefinition


class RetriFlowMcpToolExecutor(ABC):
    @abstractmethod
    def get_definition(self) -> McpToolDefinition:
        raise NotImplementedError

    @abstractmethod
    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        raise NotImplementedError


class WeatherMcpToolExecutor(RetriFlowMcpToolExecutor):
    def get_definition(self) -> McpToolDefinition:
        return McpToolDefinition(
            tool_id="weather_query",
            description="查询城市天气，可返回当前天气或未来天气趋势。",
            keywords=["天气", "气温", "下雨", "温度", "预报"],
            parameter_schema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称",
                        "default": "北京",
                    },
                    "query_type": {
                        "type": "string",
                        "description": "查询类型",
                        "enum": ["current", "forecast"],
                        "default": "current",
                    },
                },
                "required": ["city"],
            },
        )

    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        city = str(arguments.get("city", "北京"))
        query_type = str(arguments.get("query_type", "current"))
        if query_type == "forecast":
            content = f"{city}未来两天天气以多云到晴为主，气温在 22 到 30 摄氏度之间。"
        else:
            content = f"{city}当前天气晴，气温 26 摄氏度，适合出行。"
        return McpToolCallResult(
            tool_id=self.get_definition().tool_id,
            arguments={"city": city, "query_type": query_type},
            content=content,
        )


class SalesMcpToolExecutor(RetriFlowMcpToolExecutor):
    def get_definition(self) -> McpToolDefinition:
        return McpToolDefinition(
            tool_id="sales_query",
            description="查询区域销售表现，可按周期返回销售额摘要。",
            keywords=["销售", "销量", "销售额", "业绩", "营收"],
            parameter_schema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "销售区域",
                        "default": "全国",
                    },
                    "period": {
                        "type": "string",
                        "description": "统计周期",
                        "enum": ["today", "this_week", "this_month", "this_quarter"],
                        "default": "this_month",
                    },
                },
                "required": ["region"],
            },
        )

    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        region = str(arguments.get("region", "全国"))
        period = str(arguments.get("period", "this_month"))
        period_label = {
            "today": "今日",
            "this_week": "本周",
            "this_month": "本月",
            "this_quarter": "本季度",
        }.get(period, "本月")
        content = f"{region}{period_label}销售额表现稳定，当前摘要显示核心产品线持续增长。"
        return McpToolCallResult(
            tool_id=self.get_definition().tool_id,
            arguments={"region": region, "period": period},
            content=content,
        )
