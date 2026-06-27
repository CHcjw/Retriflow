from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta
import random

from modules.mcp.models import McpToolCallResult, McpToolDefinition


class RetriFlowMcpToolExecutor(ABC):
    @abstractmethod
    def get_definition(self) -> McpToolDefinition:
        raise NotImplementedError

    @abstractmethod
    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        raise NotImplementedError


class WeatherMcpToolExecutor(RetriFlowMcpToolExecutor):
    CITY_COORDINATES = {
        "北京": (39.9, 116.4),
        "上海": (31.2, 121.5),
        "广州": (23.1, 113.3),
        "深圳": (22.5, 114.1),
        "杭州": (30.3, 120.2),
        "成都": (30.6, 104.1),
        "武汉": (30.6, 114.3),
        "南京": (32.1, 118.8),
        "西安": (34.3, 108.9),
        "重庆": (29.6, 106.5),
        "长沙": (28.2, 112.9),
        "天津": (39.1, 117.2),
        "苏州": (31.3, 120.6),
        "郑州": (34.7, 113.6),
        "青岛": (36.1, 120.4),
        "大连": (38.9, 121.6),
        "厦门": (24.5, 118.1),
        "昆明": (25.0, 102.7),
        "哈尔滨": (45.8, 126.5),
        "三亚": (18.3, 109.5),
    }
    WEATHER_TYPES = {
        "spring": ["晴", "多云", "阴", "小雨", "阵雨", "多云转晴"],
        "summer": ["晴", "多云", "雷阵雨", "大雨", "暴雨", "多云转阴"],
        "autumn": ["晴", "多云", "阴", "小雨", "晴转多云", "多云转晴"],
        "winter": ["晴", "多云", "阴", "小雪", "中雪", "晴转多云", "雾"],
    }
    WIND_DIRECTIONS = ["东风", "南风", "西风", "北风", "东南风", "西北风", "东北风", "西南风"]

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
                    "days": {
                        "type": "integer",
                        "description": "Forecast days, used only when query_type is forecast.",
                        "default": 3,
                    },
                },
                "required": ["city"],
            },
        )

    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        city = str(arguments.get("city", "Beijing"))
        query_type = str(arguments.get("query_type") or arguments.get("queryType") or "current")
        days = self._int_arg(arguments.get("days"), 3)
        days = max(1, min(days, 7))

        if city == "Beijing":
            city = "北京"
        elif city == "Shanghai":
            city = "上海"
        elif city == "Guangzhou":
            city = "广州"

        if query_type == "forecast":
            content = self._build_forecast(city, days)
        else:
            content = self._build_current(city)
        return McpToolCallResult(
            tool_id=self.get_definition().tool_id,
            arguments={"city": city, "query_type": query_type, "days": days},
            content=content,
        )

    def _build_current(self, city: str) -> str:
        today = date.today()
        weather = self._weather_for(city, today)
        lines = [
            f"【{city}今日天气】",
            f"日期: {today:%Y-%m-%d}",
            f"天气: {weather['weather_type']}",
            f"当前温度: {weather['current_temp']}°C",
            f"最高温度: {weather['high_temp']}°C",
            f"最低温度: {weather['low_temp']}°C",
            f"相对湿度: {weather['humidity']}%",
            f"风向: {weather['wind_direction']}",
            f"风力: {weather['wind_level']}",
            f"空气质量: {weather['air_quality']}",
        ]
        if "雨" in str(weather["weather_type"]) or "雪" in str(weather["weather_type"]):
            lines.append("提示: 今日有降水，出行请携带雨具。")
        elif int(weather["high_temp"]) >= 35:
            lines.append("提示: 今日高温，注意防暑降温。")
        elif int(weather["low_temp"]) <= 0:
            lines.append("提示: 今日气温较低，注意防寒保暖。")
        return "\n".join(lines)

    def _build_forecast(self, city: str, days: int) -> str:
        today = date.today()
        rows = [
            f"【{city}未来{days}天天气预报】",
            "| 日期 | 天气 | 温度 | 湿度 | 风向 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for offset in range(days):
            target_date = today + timedelta(days=offset)
            label = {0: "今天", 1: "明天", 2: "后天"}.get(offset, target_date.strftime("%m-%d"))
            weather = self._weather_for(city, target_date)
            rows.append(
                "| {label} | {weather_type} | {low}°C~{high}°C | {humidity}% | {wind} {level} |".format(
                    label=label,
                    weather_type=weather["weather_type"],
                    low=weather["low_temp"],
                    high=weather["high_temp"],
                    humidity=weather["humidity"],
                    wind=weather["wind_direction"],
                    level=weather["wind_level"],
                )
            )
        return "\n".join(rows)

    def _weather_for(self, city: str, target_date: date) -> dict[str, object]:
        latitude = self.CITY_COORDINATES.get(city, self.CITY_COORDINATES["北京"])[0]
        rng = random.Random(target_date.toordinal() * 31 + hash(city))
        month = target_date.month
        season = (
            "spring" if 3 <= month <= 5
            else "summer" if 6 <= month <= 8
            else "autumn" if 9 <= month <= 11
            else "winter"
        )
        base_temp = {
            "spring": 15 - (latitude - 25) * 0.5,
            "summer": 30 - (latitude - 25) * 0.3,
            "autumn": 18 - (latitude - 25) * 0.5,
            "winter": 5 - (latitude - 25) * 0.8,
        }[season]
        high_temp = int(base_temp + 3 + rng.randint(0, 5))
        low_temp = int(base_temp - 3 - rng.randint(0, 4))
        current_temp = low_temp + rng.randint(0, max(1, high_temp - low_temp))
        weather_type = rng.choice(self.WEATHER_TYPES[season])
        humidity = (60 + rng.randint(0, 29)) if season == "summer" else (20 + rng.randint(0, 29)) if season == "winter" else (40 + rng.randint(0, 29))
        if "雨" in weather_type or "雪" in weather_type:
            humidity = min(95, humidity + 20)
        wind_force = 1 + rng.randint(0, 4)
        aqi_base = 30 + rng.randint(0, 119) + (20 if latitude > 35 else 0)
        air_quality = "优" if aqi_base <= 50 else "良" if aqi_base <= 100 else "轻度污染" if aqi_base <= 150 else "中度污染"
        return {
            "weather_type": weather_type,
            "current_temp": current_temp,
            "high_temp": high_temp,
            "low_temp": low_temp,
            "humidity": humidity,
            "wind_direction": rng.choice(self.WIND_DIRECTIONS),
            "wind_level": f"{wind_force}-{wind_force + 1}级",
            "air_quality": air_quality,
        }

    @staticmethod
    def _int_arg(value: object, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


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
