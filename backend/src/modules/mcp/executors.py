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
    REGIONS = ["华东", "华南", "华北", "西南", "西北"]
    PRODUCTS = ["企业版", "专业版", "基础版"]
    SALES_BY_REGION = {
        "华东": ["张三", "李四", "王五"],
        "华南": ["赵六", "钱七", "孙八"],
        "华北": ["周九", "吴十", "郑冬"],
        "西南": ["陈春", "林夏", "黄秋"],
        "西北": ["刘一", "杨二", "马三"],
    }
    CUSTOMER_POOL = [
        "腾讯科技",
        "阿里巴巴",
        "字节跳动",
        "美团点评",
        "京东集团",
        "百度在线",
        "网易公司",
        "小米科技",
        "华为技术",
        "中兴通讯",
        "用友网络",
        "金蝶软件",
        "浪潮集团",
        "东软集团",
        "科大讯飞",
        "三一重工",
        "中联重科",
        "格力电器",
        "美的集团",
        "海尔智家",
    ]

    def get_definition(self) -> McpToolDefinition:
        return McpToolDefinition(
            tool_id="sales_query",
            description="查询软件销售数据，支持按地区、时间、产品、销售人员等维度筛选，支持汇总统计、排名、明细列表、趋势等查询。",
            keywords=[
                "\u9500\u552e",
                "\u9500\u91cf",
                "\u9500\u552e\u989d",
                "\u5360\u6bd4",
                "\u6392\u884c\u699c",
                "\u6392\u540d",
                "\u4f01\u4e1a",
                "\u5ba2\u6237",
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
                        "description": "地区筛选：华东、华南、华北、西南、西北，不填则查询全国。",
                        "enum": ["华东", "华南", "华北", "西南", "西北", "全国"],
                        "default": "全国",
                    },
                    "period": {
                        "type": "string",
                        "description": "时间段：本月、上月、本季度、上季度、本年，默认本月。",
                        "enum": ["本月", "上月", "本季度", "上季度", "本年", "today", "this_week", "this_month", "this_quarter"],
                        "default": "本月",
                    },
                    "product": {
                        "type": "string",
                        "description": "产品筛选：企业版、专业版、基础版，不填则查询全部产品。",
                        "enum": ["企业版", "专业版", "基础版"],
                    },
                    "salesPerson": {
                        "type": "string",
                        "description": "销售人员姓名，不填则查询全部销售。",
                    },
                    "queryType": {
                        "type": "string",
                        "description": "查询类型：summary(汇总)、ranking(排名)、detail(明细)、trend(趋势)。",
                        "enum": ["summary", "ranking", "detail", "trend"],
                        "default": "summary",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回记录数限制，默认10。",
                        "default": 10,
                    },
                    "includeRegionBreakdown": {
                        "type": "boolean",
                        "description": "是否输出所有地区销售额和销售占比。",
                        "default": False,
                    },
                    "includeSalespersonRanking": {
                        "type": "boolean",
                        "description": "是否输出每个地区下销售人员排行榜。",
                        "default": False,
                    },
                    "includeCustomerSales": {
                        "type": "boolean",
                        "description": "是否输出所售企业销售额。",
                        "default": False,
                    },
                },
                "required": [],
            },
        )

    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        region = self._none_if_all(arguments.get("region"))
        period = self._normalize_period(arguments.get("period"))
        product = self._optional_str(arguments.get("product"))
        sales_person = self._optional_str(arguments.get("salesPerson") or arguments.get("sales_person"))
        query_type = str(arguments.get("queryType") or arguments.get("query_type") or "summary")
        limit = self._int_arg(arguments.get("limit"), 10)
        limit = max(1, min(limit, 50))

        data = self._filter_records(
            self._generate_records(period),
            region=region,
            product=product,
            sales_person=sales_person,
        )

        include_region_breakdown = self._bool_arg(arguments.get("includeRegionBreakdown"))
        include_salesperson_ranking = self._bool_arg(arguments.get("includeSalespersonRanking"))
        include_customer_sales = self._bool_arg(arguments.get("includeCustomerSales"))
        if include_region_breakdown or include_salesperson_ranking or include_customer_sales:
            content = self._build_compound_result(
                data,
                period=period,
                limit=limit,
                include_region_breakdown=include_region_breakdown,
                include_salesperson_ranking=include_salesperson_ranking,
                include_customer_sales=include_customer_sales,
            )
        elif query_type == "ranking":
            content = self._build_ranking_result(data, region=region, period=period, limit=limit)
        elif query_type == "detail":
            content = self._build_detail_result(data, region=region, period=period, limit=limit)
        elif query_type == "trend":
            content = self._build_trend_result(data, region=region, period=period)
        else:
            content = self._build_summary_result(
                data,
                region=region,
                period=period,
                product=product,
                sales_person=sales_person,
            )
        return McpToolCallResult(
            tool_id=self.get_definition().tool_id,
            arguments={
                "region": region or "全国",
                "period": period,
                "product": product or "",
                "salesPerson": sales_person or "",
                "queryType": query_type,
                "limit": limit,
                "includeRegionBreakdown": include_region_breakdown,
                "includeSalespersonRanking": include_salesperson_ranking,
                "includeCustomerSales": include_customer_sales,
            },
            content=content,
        )

    def _build_summary_result(
        self,
        data: list[dict[str, object]],
        *,
        region: str | None,
        period: str,
        product: str | None,
        sales_person: str | None,
    ) -> str:
        total_amount = self._sum_amount(data)
        order_count = len(data)
        avg_amount = total_amount / order_count if order_count else 0
        lines = [f"【{period} 销售数据汇总】", ""]
        filters = []
        if region:
            filters.append(f"地区：{region}")
        if product:
            filters.append(f"产品：{product}")
        if sales_person:
            filters.append(f"销售：{sales_person}")
        if filters:
            lines.extend([f"筛选条件：{'；'.join(filters)}", ""])
        lines.extend(
            [
                f"- 总销售额：¥{total_amount:.2f} 万",
                f"- 成交订单：{order_count} 笔",
                f"- 平均单价：¥{avg_amount:.2f} 万/笔",
            ]
        )
        if not product:
            lines.extend(["", "### 按产品分布", self._amount_table(data, group_key="product", first_column="产品")])
        if not region:
            lines.extend(["", "### 按地区销售额与占比", self._amount_table(data, group_key="region", first_column="地区")])
        return "\n".join(lines).strip()

    def _build_compound_result(
        self,
        data: list[dict[str, object]],
        *,
        period: str,
        limit: int,
        include_region_breakdown: bool,
        include_salesperson_ranking: bool,
        include_customer_sales: bool,
    ) -> str:
        total_amount = self._sum_amount(data)
        lines = [
            f"【{period} 销售数据分析】",
            "",
            f"- 总销售额：¥{total_amount:.2f} 万",
            f"- 成交订单：{len(data)} 笔",
        ]
        if include_region_breakdown:
            lines.extend(["", "### 按地区销售额与占比", self._amount_table(data, group_key="region", first_column="地区")])
        if include_salesperson_ranking:
            lines.extend(["", "### 地区内销售人员排行", self._regional_salesperson_ranking_table(data, limit=limit)])
        if include_customer_sales:
            lines.extend(["", "### 所售企业销售额", self._amount_table(data, group_key="customer", first_column="企业", limit=limit)])
        return "\n".join(lines).strip()

    def _build_ranking_result(
        self,
        data: list[dict[str, object]],
        *,
        region: str | None,
        period: str,
        limit: int,
    ) -> str:
        title = f"【{period}{' ' + region if region else ''} 销售排名】"
        return "\n\n".join([title, self._amount_table(data, group_key="salesPerson", first_column="销售人员", limit=limit)])

    def _build_detail_result(
        self,
        data: list[dict[str, object]],
        *,
        region: str | None,
        period: str,
        limit: int,
    ) -> str:
        rows = sorted(data, key=lambda item: float(item["amount"]), reverse=True)[:limit]
        title = f"【{period}{' ' + region if region else ''} 销售明细】"
        lines = [
            title,
            "",
            f"共 {len(data)} 条记录，显示金额最高的 {len(rows)} 条：",
            "",
            "| 企业 | 产品 | 金额 | 销售人员 | 地区 | 日期 |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| {row['customer']} | {row['product']} | ¥{float(row['amount']):.2f} 万 | "
                f"{row['salesPerson']} | {row['region']} | {row['date']} |"
            )
        return "\n".join(lines)

    def _build_trend_result(self, data: list[dict[str, object]], *, region: str | None, period: str) -> str:
        by_week: dict[str, float] = {}
        for row in data:
            day = int(str(row["date"]).split("-")[-1])
            label = f"第{(day - 1) // 7 + 1}周"
            by_week[label] = by_week.get(label, 0.0) + float(row["amount"])
        title = f"【{period}{' ' + region if region else ''} 销售趋势】"
        lines = [title, "", "| 周期 | 销售额 |", "| --- | ---: |"]
        for label in sorted(by_week):
            lines.append(f"| {label} | ¥{by_week[label]:.2f} 万 |")
        return "\n".join(lines)

    def _amount_table(
        self,
        data: list[dict[str, object]],
        *,
        group_key: str,
        first_column: str,
        limit: int | None = None,
    ) -> str:
        grouped: dict[str, float] = {}
        for row in data:
            key = str(row[group_key])
            grouped[key] = grouped.get(key, 0.0) + float(row["amount"])
        total_amount = self._sum_amount(data)
        rows = sorted(grouped.items(), key=lambda item: item[1], reverse=True)
        if limit:
            rows = rows[:limit]
        if not rows:
            return "暂无销售数据。"
        lines = [f"| {first_column} | 销售额 | 占比 |", "| --- | ---: | ---: |"]
        for name, amount in rows:
            ratio = amount / total_amount * 100 if total_amount else 0
            lines.append(f"| {name} | ¥{amount:.2f} 万 | {ratio:.1f}% |")
        return "\n".join(lines)

    def _regional_salesperson_ranking_table(self, data: list[dict[str, object]], *, limit: int) -> str:
        grouped: dict[str, dict[str, float]] = {}
        for row in data:
            region = str(row["region"])
            person = str(row["salesPerson"])
            grouped.setdefault(region, {})
            grouped[region][person] = grouped[region].get(person, 0.0) + float(row["amount"])
        if not grouped:
            return "暂无销售数据。"
        lines = ["| 地区 | 排名 | 销售人员 | 销售额 |", "| --- | ---: | --- | ---: |"]
        for region in self.REGIONS:
            ranking = sorted(grouped.get(region, {}).items(), key=lambda item: item[1], reverse=True)[:limit]
            for index, (person, amount) in enumerate(ranking, start=1):
                lines.append(f"| {region} | {index} | {person} | ¥{amount:.2f} 万 |")
        return "\n".join(lines)

    def _generate_records(self, period: str) -> list[dict[str, object]]:
        start, end = self._date_range(period)
        records: list[dict[str, object]] = []
        rng = random.Random(start.toordinal())
        current = start
        while current <= end:
            if current.weekday() < 5:
                orders_per_day = 3 + rng.randrange(6)
                for _ in range(orders_per_day):
                    region = self.REGIONS[rng.randrange(len(self.REGIONS))]
                    product = self.PRODUCTS[rng.randrange(len(self.PRODUCTS))]
                    amount = {
                        "企业版": 50 + rng.random() * 150,
                        "专业版": 10 + rng.random() * 40,
                        "基础版": 1 + rng.random() * 9,
                    }[product]
                    records.append(
                        {
                            "region": region,
                            "salesPerson": self.SALES_BY_REGION[region][rng.randrange(3)],
                            "product": product,
                            "customer": f"{self.CUSTOMER_POOL[rng.randrange(len(self.CUSTOMER_POOL))]}{current.day}",
                            "amount": round(amount, 2),
                            "date": current.isoformat(),
                        }
                    )
            current += timedelta(days=1)
        return records

    @staticmethod
    def _date_range(period: str) -> tuple[date, date]:
        today = date.today()
        if period == "today":
            return today, today
        if period == "this_week":
            return today - timedelta(days=today.weekday()), today
        if period == "上月":
            first_this_month = today.replace(day=1)
            end = first_this_month - timedelta(days=1)
            return end.replace(day=1), end
        if period in {"本季度", "this_quarter"}:
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            return today.replace(month=quarter_start_month, day=1), today
        if period == "上季度":
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            current_quarter_start = today.replace(month=quarter_start_month, day=1)
            end = current_quarter_start - timedelta(days=1)
            previous_start_month = ((end.month - 1) // 3) * 3 + 1
            return end.replace(month=previous_start_month, day=1), end
        if period == "本年":
            return today.replace(month=1, day=1), today
        return today.replace(day=1), today

    def _filter_records(
        self,
        data: list[dict[str, object]],
        *,
        region: str | None,
        product: str | None,
        sales_person: str | None,
    ) -> list[dict[str, object]]:
        return [
            row
            for row in data
            if (region is None or row["region"] == region)
            and (product is None or row["product"] == product)
            and (sales_person is None or row["salesPerson"] == sales_person)
        ]

    @staticmethod
    def _sum_amount(data: list[dict[str, object]]) -> float:
        return sum(float(row["amount"]) for row in data)

    @staticmethod
    def _normalize_period(value: object) -> str:
        raw = str(value or "").strip()
        mapping = {
            "today": "today",
            "this_week": "this_week",
            "this_month": "本月",
            "this_quarter": "本季度",
            "本周": "this_week",
            "这个月": "本月",
            "本月": "本月",
            "上月": "上月",
            "本季度": "本季度",
            "上季度": "上季度",
            "本年": "本年",
            "今年": "本年",
        }
        return mapping.get(raw, "本月")

    @staticmethod
    def _none_if_all(value: object) -> str | None:
        normalized = str(value or "").strip()
        if not normalized or normalized in {"全国", "全部", "所有", "national", "all"}:
            return None
        return normalized

    @staticmethod
    def _optional_str(value: object) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _bool_arg(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "要", "需要"}

    @staticmethod
    def _int_arg(value: object, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default



class TicketMcpToolExecutor(RetriFlowMcpToolExecutor):
    REGIONS = ["华东", "华南", "华北", "西南", "西北"]
    PRODUCTS = ["企业版", "专业版", "基础版"]
    STATUSES = ["待处理", "处理中", "已解决", "已关闭"]
    PRIORITIES = ["紧急", "高", "中", "低"]
    CATEGORIES = ["功能异常", "性能问题", "安装部署", "使用咨询", "数据问题", "权限问题"]
    CUSTOMERS_BY_REGION = {
        "华东": ["腾讯科技", "阿里巴巴", "字节跳动", "网易公司"],
        "华南": ["美团点评", "京东集团", "小米科技", "格力电器"],
        "华北": ["百度在线", "华为技术", "中兴通讯", "用友网络"],
        "西南": ["科大讯飞", "金蝶软件", "三一重工", "中联重科"],
        "西北": ["浪潮集团", "东软集团", "美的集团", "海尔智家"],
    }
    ENGINEERS_BY_REGION = {
        "华东": ["工程师A1", "工程师A2"],
        "华南": ["工程师B1", "工程师B2"],
        "华北": ["工程师C1", "工程师C2"],
        "西南": ["工程师D1", "工程师D2"],
        "西北": ["工程师E1", "工程师E2"],
    }
    ISSUE_TEMPLATES = [
        "系统登录后页面白屏无法操作",
        "报表导出功能超时失败",
        "用户权限配置不生效",
        "数据同步延迟超过预期",
        "批量导入数据格式校验异常",
        "API接口调用返回500错误",
        "定时任务未按计划执行",
        "搜索功能结果不准确",
        "通知消息无法正常推送",
        "文件上传大小限制配置无效",
        "仪表盘数据展示不一致",
        "多租户数据隔离存在问题",
        "审批流程节点卡住无法流转",
        "移动端页面适配显示异常",
        "数据备份任务执行失败",
    ]

    def get_definition(self) -> McpToolDefinition:
        return McpToolDefinition(
            tool_id="ticket_query",
            description="查询客户技术支持工单数据，支持按地区、状态、优先级、产品、客户等维度筛选，支持汇总概览、工单列表、统计分析。",
            keywords=[
                "工单",
                "待处理",
                "处理中",
                "已解决",
                "已关闭",
                "紧急",
                "高优先级",
                "解决率",
                "ticket",
                "support",
                "work order",
            ],
            parameter_schema={
                "type": "object",
                "properties": {
                    "region": {"type": "string", "enum": ["华东", "华南", "华北", "西南", "西北", "全国"], "default": "全国"},
                    "status": {"type": "string", "enum": self.STATUSES},
                    "priority": {"type": "string", "enum": self.PRIORITIES},
                    "product": {"type": "string", "enum": self.PRODUCTS},
                    "customerName": {"type": "string"},
                    "queryType": {"type": "string", "enum": ["summary", "list", "stats"], "default": "summary"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": [],
            },
        )

    def execute(self, arguments: dict[str, object]) -> McpToolCallResult:
        region = self._none_if_all(arguments.get("region"))
        status = self._optional_str(arguments.get("status"))
        priority = self._optional_str(arguments.get("priority"))
        product = self._optional_str(arguments.get("product"))
        customer_name = self._optional_str(arguments.get("customerName") or arguments.get("customer_name"))
        query_type = str(arguments.get("queryType") or arguments.get("query_type") or "summary")
        limit = max(1, min(self._int_arg(arguments.get("limit"), 10), 50))

        records = self._filter_records(
            self._generate_records(),
            region=region,
            status=status,
            priority=priority,
            product=product,
            customer_name=customer_name,
        )
        if query_type == "list":
            content = self._build_list_result(records, limit=limit)
            filter_line = self._format_filter_line(region=region, status=status, priority=priority, product=product)
            if filter_line:
                content = f"{filter_line}\n\n{content}"
        elif query_type == "stats":
            content = self._build_stats_result(records)
        else:
            content = self._build_summary_result(records, region=region, status=status, priority=priority, product=product)
        return McpToolCallResult(
            tool_id=self.get_definition().tool_id,
            arguments={
                "region": region or "全国",
                "status": status or "",
                "priority": priority or "",
                "product": product or "",
                "customerName": customer_name or "",
                "queryType": query_type,
                "limit": limit,
            },
            content=content,
        )

    def _build_summary_result(
        self,
        records: list[dict[str, object]],
        *,
        region: str | None,
        status: str | None,
        priority: str | None,
        product: str | None,
    ) -> str:
        total = len(records)
        pending = self._count(records, "status", "待处理")
        in_progress = self._count(records, "status", "处理中")
        resolved = self._count(records, "status", "已解决")
        closed = self._count(records, "status", "已关闭")
        urgent = self._count(records, "priority", "紧急")
        high = self._count(records, "priority", "高")
        lines = ["【客户工单汇总概览】", ""]
        filters = []
        if region:
            filters.append(f"地区：{region}")
        if status:
            filters.append(f"状态：{status}")
        if priority:
            filters.append(f"优先级：{priority}")
        if product:
            filters.append(f"产品：{product}")
        if filters:
            lines.extend([f"筛选条件：{'；'.join(filters)}", ""])
        lines.extend(
            [
                f"工单总数：{total} 个",
                "",
                "### 状态分布",
                f"- 待处理：{pending} 个",
                f"- 处理中：{in_progress} 个",
                f"- 已解决：{resolved} 个",
                f"- 已关闭：{closed} 个",
            ]
        )
        if total:
            lines.append(f"- 整体解决率：{(resolved + closed) * 100 / total:.1f}%")
        if urgent + high:
            lines.extend(["", f"紧急/高优先级工单：{urgent + high} 个（紧急 {urgent}，高 {high}）"])
        if not product:
            lines.extend(["", "### 按产品分布", self._count_table(records, "product", "产品")])
        if not region:
            lines.extend(["", "### 按地区分布", self._count_table(records, "region", "地区")])
        return "\n".join(lines).strip()

    @staticmethod
    def _format_filter_line(*, region: str | None, status: str | None, priority: str | None, product: str | None) -> str:
        filters = []
        if region:
            filters.append(f"地区：{region}")
        if status:
            filters.append(f"状态：{status}")
        if priority:
            filters.append(f"优先级：{priority}")
        if product:
            filters.append(f"产品：{product}")
        return f"筛选条件：{'；'.join(filters)}" if filters else ""

    def _build_list_result(self, records: list[dict[str, object]], *, limit: int) -> str:
        priority_order = {priority: index for index, priority in enumerate(self.PRIORITIES)}
        rows = sorted(records, key=lambda item: (priority_order.get(str(item["priority"]), 99), str(item["createDate"])))[:limit]
        lines = [f"【工单列表】共 {len(records)} 条，显示 {len(rows)} 条（按优先级排序）", ""]
        if not rows:
            return "\n".join([*lines, "暂无工单数据。"])
        lines.extend(
            [
                "| 工单号 | 标题 | 客户 | 地区 | 产品 | 优先级 | 状态 | 处理人 | 创建时间 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in rows:
            lines.append(
                f"| {row['ticketId']} | {row['title']} | {row['customer']} | {row['region']} | {row['product']} | "
                f"{row['priority']} | {row['status']} | {row['engineer']} | {row['createDate']} |"
            )
        return "\n".join(lines)

    def _build_stats_result(self, records: list[dict[str, object]]) -> str:
        if not records:
            return "【工单统计分析】\n\n暂无工单数据。"
        lines = ["【工单统计分析】", "", "### 问题分类统计", self._count_table(records, "category", "分类")]
        lines.extend(["", "### 各产品解决率", "| 产品 | 已解决/关闭 | 总数 | 解决率 |", "| --- | ---: | ---: | ---: |"])
        for product in self.PRODUCTS:
            product_rows = [row for row in records if row["product"] == product]
            if not product_rows:
                continue
            done = sum(1 for row in product_rows if row["status"] in {"已解决", "已关闭"})
            lines.append(f"| {product} | {done} | {len(product_rows)} | {done * 100 / len(product_rows):.1f}% |")
        active = [row for row in records if row["status"] in {"待处理", "处理中"}]
        lines.extend(["", "### 处理人工单量排名", self._count_table(active, "engineer", "处理人", suffix="个待处理")])
        return "\n".join(lines)

    def _count_table(self, records: list[dict[str, object]], key: str, first_column: str, suffix: str = "个") -> str:
        grouped: dict[str, int] = {}
        for row in records:
            name = str(row[key])
            grouped[name] = grouped.get(name, 0) + 1
        if not grouped:
            return "暂无工单数据。"
        total = len(records)
        lines = [f"| {first_column} | 数量 | 占比 |", "| --- | ---: | ---: |"]
        for name, count in sorted(grouped.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"| {name} | {count} {suffix} | {count * 100 / total:.1f}% |")
        return "\n".join(lines)

    def _generate_records(self) -> list[dict[str, object]]:
        today = date.today()
        rng = random.Random(today.toordinal())
        records: list[dict[str, object]] = []
        sequence = 1
        for offset in range(30):
            current = today - timedelta(days=offset)
            if current.weekday() > 4:
                continue
            for _ in range(2 + rng.randrange(5)):
                region = self.REGIONS[rng.randrange(len(self.REGIONS))]
                priority_weight = rng.randrange(100)
                if priority_weight < 5:
                    priority = "紧急"
                elif priority_weight < 20:
                    priority = "高"
                elif priority_weight < 60:
                    priority = "中"
                else:
                    priority = "低"
                if offset > 7:
                    status = "已关闭" if rng.randrange(100) < 80 else "已解决"
                elif offset > 3:
                    status_weight = rng.randrange(100)
                    status = "已解决" if status_weight < 30 else "已关闭" if status_weight < 60 else "处理中" if status_weight < 85 else "待处理"
                else:
                    status_weight = rng.randrange(100)
                    status = "待处理" if status_weight < 35 else "处理中" if status_weight < 70 else "已解决" if status_weight < 90 else "已关闭"
                records.append(
                    {
                        "ticketId": f"TK-{today:%Y%m}-{sequence:04d}",
                        "region": region,
                        "customer": self.CUSTOMERS_BY_REGION[region][rng.randrange(4)],
                        "product": self.PRODUCTS[rng.randrange(len(self.PRODUCTS))],
                        "title": self.ISSUE_TEMPLATES[rng.randrange(len(self.ISSUE_TEMPLATES))],
                        "category": self.CATEGORIES[rng.randrange(len(self.CATEGORIES))],
                        "priority": priority,
                        "status": status,
                        "engineer": self.ENGINEERS_BY_REGION[region][rng.randrange(2)],
                        "createDate": current.isoformat(),
                    }
                )
                sequence += 1
        return records

    def _filter_records(
        self,
        records: list[dict[str, object]],
        *,
        region: str | None,
        status: str | None,
        priority: str | None,
        product: str | None,
        customer_name: str | None,
    ) -> list[dict[str, object]]:
        return [
            row
            for row in records
            if (region is None or row["region"] == region)
            and (status is None or row["status"] == status)
            and (priority is None or row["priority"] == priority)
            and (product is None or row["product"] == product)
            and (customer_name is None or customer_name in str(row["customer"]))
        ]

    @staticmethod
    def _count(records: list[dict[str, object]], key: str, value: str) -> int:
        return sum(1 for row in records if row[key] == value)

    @staticmethod
    def _none_if_all(value: object) -> str | None:
        normalized = str(value or "").strip()
        if not normalized or normalized in {"全国", "全部", "所有", "national", "all"}:
            return None
        return normalized

    @staticmethod
    def _optional_str(value: object) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _int_arg(value: object, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
