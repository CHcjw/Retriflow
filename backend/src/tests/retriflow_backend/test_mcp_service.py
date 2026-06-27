import os
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class FakeExecutor:
    def __init__(self, tool_id: str, content: str, *, delay_seconds: float = 0.0, should_fail: bool = False):
        self.tool_id = tool_id
        self.content = content
        self.delay_seconds = delay_seconds
        self.should_fail = should_fail

    def get_definition(self):
        from modules.mcp.models import McpToolDefinition

        return McpToolDefinition(
            tool_id=self.tool_id,
            description=f"fake executor for {self.tool_id}",
            parameter_schema={"type": "object", "properties": {}},
            keywords=[],
        )

    def execute(self, arguments):
        from modules.mcp.models import McpToolCallResult

        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self.should_fail:
            raise RuntimeError(f"{self.tool_id} failed")
        return McpToolCallResult(
            tool_id=self.tool_id,
            arguments=dict(arguments),
            content=self.content,
        )


class RetriFlowMcpServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "false"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = "[]"
        os.environ["RETRIFLOW_MCP_EXECUTION_MODE"] = "sequential"
        os.environ["RETRIFLOW_MCP_MAX_TOOL_CANDIDATES"] = "3"
        os.environ["RETRIFLOW_MCP_FAIL_FAST"] = "false"
        os.environ["RETRIFLOW_MCP_PARALLEL_MAX_WORKERS"] = "3"
        from core.config import get_settings

        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        os.environ.pop("RETRIFLOW_MCP_REMOTE_ENABLED", None)
        os.environ.pop("RETRIFLOW_MCP_REMOTE_SERVERS_JSON", None)
        os.environ.pop("RETRIFLOW_MCP_EXECUTION_MODE", None)
        os.environ.pop("RETRIFLOW_MCP_MAX_TOOL_CANDIDATES", None)
        os.environ.pop("RETRIFLOW_MCP_FAIL_FAST", None)
        os.environ.pop("RETRIFLOW_MCP_PARALLEL_MAX_WORKERS", None)
        from core.config import get_settings

        get_settings.cache_clear()

    def test_route_question_matches_weather_tool(self) -> None:
        from modules.mcp.service import RetriFlowMcpService

        service = RetriFlowMcpService()
        decision = service.route_question("上海今天天气如何？")

        self.assertEqual(decision.mode, "mcp")
        self.assertIn("weather_query", decision.tool_ids)
        self.assertGreater(decision.confidence, 0.4)


    def test_today_weather_tool_receives_current_date_context(self) -> None:
        from modules.mcp.service import RetriFlowMcpService

        captured_questions: list[str] = []

        def fake_extract(self, *, question, tool_definition, param_prompt_template=""):
            captured_questions.append(question)
            return {"city": "北京", "query_type": "current"}

        with patch(
            "modules.mcp.parameter_extractor.RetriFlowMcpParameterExtractor.extract",
            new=fake_extract,
        ):
            result = RetriFlowMcpService().execute_question("北京今天天气如何？")

        self.assertEqual(result.route.mode, "mcp")
        self.assertEqual(result.calls[0].tool_id, "weather_query")
        self.assertTrue(captured_questions)
        self.assertIn("当前日期", captured_questions[0])
        self.assertIn("今天、明天、本周、本月", captured_questions[0])

    def test_builtin_weather_uses_city_specific_dynamic_fallback_instead_of_fixed_demo_answer(self) -> None:
        from modules.mcp.executors import WeatherMcpToolExecutor

        executor = WeatherMcpToolExecutor()
        guangzhou = executor.execute({"city": "广州", "query_type": "current"})
        beijing = executor.execute({"city": "北京", "query_type": "current"})

        self.assertFalse(guangzhou.is_error)
        self.assertIn("广州", guangzhou.content)
        self.assertIn("当前温度", guangzhou.content)
        self.assertNotIn("2掳C~14掳C", guangzhou.content)
        self.assertNotEqual(guangzhou.content, beijing.content)

    def test_execute_question_returns_tool_call_and_context(self) -> None:
        from modules.mcp.service import RetriFlowMcpService

        service = RetriFlowMcpService()
        result = service.execute_question("华东本月销售额怎么样？")

        self.assertEqual(result.route.mode, "mcp")
        self.assertEqual(len(result.calls), 1)
        self.assertEqual(result.calls[0].tool_id, "sales_query")
        self.assertIn("华东", result.calls[0].content)
        self.assertIn("Tool: sales_query", result.context)

    def test_execute_question_persists_tool_level_trace_node(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""

        from core.config import get_settings
        from core.state import initialize_database
        from modules.mcp.service import RetriFlowMcpService
        from modules.rag.trace import RetriFlowTraceService

        get_settings.cache_clear()
        initialize_database()
        trace_service = RetriFlowTraceService()
        session_id = "mcp-trace-session"

        try:
            with trace_service.start_root(session_id=session_id, task_id="chat", name="chat.run"):
                result = RetriFlowMcpService().execute_question("北京今天天气如何？")

            self.assertEqual(result.route.mode, "mcp")
            nodes = trace_service.list_nodes(session_id)
            tool_node = next(node for node in nodes if node["name"] == "mcp.tool.weather_query")
            self.assertEqual(tool_node["status"], "success")
            self.assertEqual(tool_node["metadata"]["tool_id"], "weather_query")
            self.assertEqual(tool_node["metadata"]["server_name"], "builtin")
            self.assertEqual(tool_node["metadata"]["transport"], "builtin")
            self.assertEqual(tool_node["metadata"]["schema_version"], "json_schema")
        finally:
            os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
            os.environ.pop("RETRIFLOW_DB_PATH", None)
            os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
            os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
            get_settings.cache_clear()
            temp_dir.cleanup()

    def test_execute_question_supports_multiple_builtin_tools(self) -> None:
        from modules.mcp.service import RetriFlowMcpService

        service = RetriFlowMcpService()
        result = service.execute_question("请同时告诉我北京今天天气和华东本月销售额情况")

        self.assertEqual(result.route.mode, "mcp")
        self.assertEqual(len(result.calls), 2)
        tool_ids = [call.tool_id for call in result.calls]
        self.assertIn("weather_query", tool_ids)
        self.assertIn("sales_query", tool_ids)
        self.assertIn("[M1]", result.context)
        self.assertIn("[M2]", result.context)

    def test_execute_question_parallel_preserves_route_order(self) -> None:
        os.environ["RETRIFLOW_MCP_EXECUTION_MODE"] = "parallel"
        from core.config import get_settings
        from modules.mcp.models import McpRouteDecision
        from modules.mcp.service import RetriFlowMcpService

        get_settings.cache_clear()
        service = RetriFlowMcpService()
        executors = {
            "tool_fast": FakeExecutor("tool_fast", "fast result", delay_seconds=0.0),
            "tool_slow": FakeExecutor("tool_slow", "slow result", delay_seconds=0.05),
        }

        with (
            patch.object(
                service,
                "route_question",
                return_value=McpRouteDecision(
                    mode="mcp",
                    tool_ids=["tool_slow", "tool_fast"],
                    confidence=0.9,
                    reason="test",
                ),
            ),
            patch.object(service.registry, "get_executor", side_effect=lambda tool_id: executors[tool_id]),
            patch.object(service.parameter_extractor, "extract", return_value={}),
        ):
            result = service.execute_question("run tools")

        self.assertEqual([call.tool_id for call in result.calls], ["tool_slow", "tool_fast"])

    def test_execute_question_continues_after_single_tool_failure_when_fail_fast_is_false(self) -> None:
        from modules.mcp.models import McpRouteDecision
        from modules.mcp.service import RetriFlowMcpService

        service = RetriFlowMcpService()
        executors = {
            "tool_fail": FakeExecutor("tool_fail", "unused", should_fail=True),
            "tool_ok": FakeExecutor("tool_ok", "success result"),
        }

        with (
            patch.object(
                service,
                "route_question",
                return_value=McpRouteDecision(
                    mode="mcp",
                    tool_ids=["tool_fail", "tool_ok"],
                    confidence=0.9,
                    reason="test",
                ),
            ),
            patch.object(service.registry, "get_executor", side_effect=lambda tool_id: executors[tool_id]),
            patch.object(service.parameter_extractor, "extract", return_value={}),
        ):
            result = service.execute_question("run tools")

        self.assertEqual(len(result.calls), 2)
        self.assertTrue(result.calls[0].is_error)
        self.assertIn("tool_fail failed", result.calls[0].content)
        self.assertFalse(result.calls[1].is_error)
        self.assertEqual(result.calls[1].content, "success result")

    def test_execute_question_stops_on_failure_when_fail_fast_is_true(self) -> None:
        os.environ["RETRIFLOW_MCP_FAIL_FAST"] = "true"
        from core.config import get_settings
        from modules.mcp.models import McpRouteDecision
        from modules.mcp.service import RetriFlowMcpService

        get_settings.cache_clear()
        service = RetriFlowMcpService()
        executors = {
            "tool_fail": FakeExecutor("tool_fail", "unused", should_fail=True),
            "tool_ok": FakeExecutor("tool_ok", "success result"),
        }

        with (
            patch.object(
                service,
                "route_question",
                return_value=McpRouteDecision(
                    mode="mcp",
                    tool_ids=["tool_fail", "tool_ok"],
                    confidence=0.9,
                    reason="test",
                ),
            ),
            patch.object(service.registry, "get_executor", side_effect=lambda tool_id: executors[tool_id]),
            patch.object(service.parameter_extractor, "extract", return_value={}),
        ):
            result = service.execute_question("run tools")

        self.assertEqual(len(result.calls), 1)
        self.assertTrue(result.calls[0].is_error)
        self.assertEqual(result.calls[0].tool_id, "tool_fail")

    def test_execute_question_supports_remote_mcp_tools(self) -> None:
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "true"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = (
            '[{"name":"finance-remote","url":"http://mcp.example"}]'
        )
        from core.config import get_settings
        from modules.mcp.models import McpToolCallResult, McpToolDefinition
        from modules.mcp.service import RetriFlowMcpService

        get_settings.cache_clear()

        remote_tool = McpToolDefinition(
            tool_id="stock_query",
            description="查询股票行情",
            parameter_schema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "default": "600519"},
                },
            },
            keywords=["股票", "股价", "行情"],
        )

        with (
            patch("modules.mcp.registry.RetriFlowRemoteMcpClient.list_tools", return_value=[remote_tool]),
            patch(
                "modules.mcp.parameter_extractor.RetriFlowMcpParameterExtractor.extract",
                return_value={"ticker": "600519"},
            ),
            patch(
                "modules.mcp.client.RetriFlowRemoteMcpClient.call_tool",
                return_value=McpToolCallResult(
                    tool_id="stock_query",
                    arguments={"ticker": "600519"},
                    content="贵州茅台当前价格表现稳定。",
                ),
            ),
        ):
            service = RetriFlowMcpService()
            result = service.execute_question("请查询贵州茅台股票行情")

        self.assertEqual(result.route.mode, "mcp")
        self.assertEqual(len(result.calls), 1)
        self.assertIn("贵州茅台", result.calls[0].content)
        self.assertIn("贵州茅台", result.calls[0].content)

    def test_weather_question_prefers_remote_weather_mcp(self) -> None:
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "true"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = (
            '[{"name":"china-weather","url":"http://mcp.example"}]'
        )
        from core.config import get_settings
        from modules.mcp.models import McpToolCallResult, McpToolDefinition
        from modules.mcp.service import RetriFlowMcpService

        get_settings.cache_clear()

        weather_tool = McpToolDefinition(
            tool_id="get-weather-forecast",
            description="查询中国城市天气预报",
            parameter_schema={"type": "object", "properties": {"cityName": {"type": "string"}}},
            keywords=[],
            server_name="china-weather",
            transport="remote_http",
        )
        calls: list[tuple[str, dict]] = []

        def fake_call_tool(self, tool_id, arguments):
            calls.append((tool_id, dict(arguments)))
            return McpToolCallResult(
                tool_id=tool_id,
                arguments=dict(arguments),
                content="广州实时天气：多云，当前温度28°C。",
            )

        try:
            with (
                patch("modules.mcp.registry.RetriFlowRemoteMcpClient.list_tools", return_value=[weather_tool]),
                patch("modules.mcp.client.RetriFlowRemoteMcpClient.call_tool", new=fake_call_tool),
            ):
                result = RetriFlowMcpService().execute_question("广州今天天气如何？")
        finally:
            os.environ.pop("RETRIFLOW_MCP_REMOTE_ENABLED", None)
            os.environ.pop("RETRIFLOW_MCP_REMOTE_SERVERS_JSON", None)
            get_settings.cache_clear()

        self.assertEqual(result.route.mode, "mcp")
        self.assertEqual([call.tool_id for call in result.calls], ["get-weather-forecast"])
        self.assertEqual(calls[0][0], "get-weather-forecast")

    def test_explicit_web_search_question_routes_to_baidu_search_mcp(self) -> None:
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "true"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = (
            '[{"name":"baidu-ai-search","url":"http://mcp.example"}]'
        )
        from core.config import get_settings
        from modules.mcp.models import McpToolCallResult, McpToolDefinition
        from modules.mcp.service import RetriFlowMcpService

        get_settings.cache_clear()

        search_tool = McpToolDefinition(
            tool_id="AIsearch",
            description="百度 AI 搜索",
            parameter_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            keywords=[],
            server_name="baidu-ai-search",
            transport="remote_http",
        )
        calls: list[tuple[str, dict]] = []

        def fake_call_tool(self, tool_id, arguments):
            calls.append((tool_id, dict(arguments)))
            return McpToolCallResult(
                tool_id=tool_id,
                arguments=dict(arguments),
                content="RAG 通常通过检索、重排和生成完成回答。",
            )

        try:
            with (
                patch("modules.mcp.registry.RetriFlowRemoteMcpClient.list_tools", return_value=[search_tool]),
                patch("modules.mcp.client.RetriFlowRemoteMcpClient.call_tool", new=fake_call_tool),
            ):
                result = RetriFlowMcpService().execute_question("上网搜索怎么实现 rag")
        finally:
            os.environ.pop("RETRIFLOW_MCP_REMOTE_ENABLED", None)
            os.environ.pop("RETRIFLOW_MCP_REMOTE_SERVERS_JSON", None)
            get_settings.cache_clear()

        self.assertEqual(result.route.mode, "mcp")
        self.assertEqual([call.tool_id for call in result.calls], ["AIsearch"])
        self.assertIn("rag", str(calls[0][1].get("query", "")).lower())

if __name__ == "__main__":
    unittest.main()


