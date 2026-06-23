from __future__ import annotations

from abc import ABC, abstractmethod

from modules.mcp.models import McpToolCallResult, McpToolDefinition


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
            description="Query city weather and return current or forecast summaries.",
            keywords=[
                "\u5929\u6c14",
                "\u6c14\u6e29",
                "\u4e0b\u96e8",
                "\u6e29\u5ea6",
                "\u9884\u62a5",
                "weather",
                "temperature",
                "rain",
                "forecast",
                "Beijing",
                "Shanghai",
                "Guangzhou",
            ],
            parameter_schema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name.",
                        "default": "Beijing",
                    },
                    "query_type": {
                        "type": "string",
                        "description": "Weather query type.",
                        "enum": ["current", "forecast"],
                        "default": "current",
                    },
                },
                "required": ["city"],
            },
        )

    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        city = str(arguments.get("city", "Beijing"))
        query_type = str(arguments.get("query_type", "current"))
        if query_type == "forecast":
            content = (
                f"{city}未来三天天气预报：\n"
                "| 日期 | 天气 | 温度 | 湿度 | 风向 |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| 今天 | 晴 | 2°C~14°C | 44% | 东南风2-3级 |\n"
                "| 明天 | 晴 | 3°C~10°C | 41% | 东风5-6级 |\n"
                "| 后天 | 阵雨 | 4°C~14°C | 81% | 东南风4-5级 |"
            )
        else:
            content = f"{city}今天天气晴，当前约12°C，气温2°C~14°C，湿度44%，东南风2-3级。"
        return McpToolCallResult(
            tool_id=self.get_definition().tool_id,
            arguments={"city": city, "query_type": query_type},
            content=content,
        )


class SalesMcpToolExecutor(RetriFlowMcpToolExecutor):
    def get_definition(self) -> McpToolDefinition:
        return McpToolDefinition(
            tool_id="sales_query",
            description="Query regional sales performance summaries by period.",
            keywords=[
                "\u9500\u552e",
                "\u9500\u91cf",
                "\u9500\u552e\u989d",
                "\u4e1a\u7ee9",
                "\u8425\u6536",
                "sales",
                "revenue",
                "performance",
                "east china",
                "north china",
            ],
            parameter_schema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "Sales region.",
                        "default": "national",
                    },
                    "period": {
                        "type": "string",
                        "description": "Reporting period.",
                        "enum": ["today", "this_week", "this_month", "this_quarter"],
                        "default": "this_month",
                    },
                },
                "required": ["region"],
            },
        )

    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        region = str(arguments.get("region", "national"))
        period = str(arguments.get("period", "this_month"))
        period_label = {
            "today": "today",
            "this_week": "this week",
            "this_month": "this month",
            "this_quarter": "this quarter",
        }.get(period, "this month")
        content = f"{region} sales for {period_label}: stable, with core product lines continuing to grow."
        return McpToolCallResult(
            tool_id=self.get_definition().tool_id,
            arguments={"region": region, "period": period},
            content=content,
        )


class TicketMcpToolExecutor(RetriFlowMcpToolExecutor):
    def get_definition(self) -> McpToolDefinition:
        return McpToolDefinition(
            tool_id="ticket_query",
            description="Query ticket, order, booking, or support-work-order status.",
            keywords=[
                "\u5de5\u5355",
                "\u7968\u52a1",
                "\u8f66\u7968",
                "\u673a\u7968",
                "ticket",
                "order",
                "booking",
                "support",
                "work order",
            ],
            parameter_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket, order, or booking identifier.",
                        "default": "latest",
                    },
                    "query_type": {
                        "type": "string",
                        "description": "Query type.",
                        "enum": ["status", "detail"],
                        "default": "status",
                    },
                },
                "required": ["ticket_id"],
            },
        )

    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        ticket_id = str(arguments.get("ticket_id", "latest"))
        query_type = str(arguments.get("query_type", "status"))
        if query_type == "detail":
            content = f"{ticket_id} detail: created, assigned, and waiting for the next confirmation step."
        else:
            content = f"{ticket_id} status: in progress, with an update expected during this business day."
        return McpToolCallResult(
            tool_id=self.get_definition().tool_id,
            arguments={"ticket_id": ticket_id, "query_type": query_type},
            content=content,
        )
