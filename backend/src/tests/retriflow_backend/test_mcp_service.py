import os
import sys
import time
import unittest
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
        from domain.mcp.models import McpToolDefinition

        return McpToolDefinition(
            tool_id=self.tool_id,
            description=f"fake executor for {self.tool_id}",
            parameter_schema={"type": "object", "properties": {}},
            keywords=[],
        )

    def execute(self, arguments):
        from domain.mcp.models import McpToolCallResult

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
        from domain.mcp.service import RetriFlowMcpService

        service = RetriFlowMcpService()
        decision = service.route_question("上海今天天气如何？")

        self.assertEqual(decision.mode, "mcp")
        self.assertIn("weather_query", decision.tool_ids)
        self.assertGreater(decision.confidence, 0.4)

    def test_execute_question_returns_tool_call_and_context(self) -> None:
        from domain.mcp.service import RetriFlowMcpService

        service = RetriFlowMcpService()
        result = service.execute_question("华东本月销售额怎么样？")

        self.assertEqual(result.route.mode, "mcp")
        self.assertEqual(len(result.calls), 1)
        self.assertEqual(result.calls[0].tool_id, "sales_query")
        self.assertIn("华东", result.calls[0].content)
        self.assertIn("Tool: sales_query", result.context)

    def test_execute_question_supports_multiple_builtin_tools(self) -> None:
        from domain.mcp.service import RetriFlowMcpService

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
        from domain.mcp.models import McpRouteDecision
        from domain.mcp.service import RetriFlowMcpService

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
        from domain.mcp.models import McpRouteDecision
        from domain.mcp.service import RetriFlowMcpService

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
        from domain.mcp.models import McpRouteDecision
        from domain.mcp.service import RetriFlowMcpService

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
        from domain.mcp.models import McpToolCallResult, McpToolDefinition
        from domain.mcp.service import RetriFlowMcpService

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
            patch("domain.mcp.registry.RetriFlowRemoteMcpClient.list_tools", return_value=[remote_tool]),
            patch(
                "domain.mcp.parameter_extractor.RetriFlowMcpParameterExtractor.extract",
                return_value={"ticker": "600519"},
            ),
            patch(
                "domain.mcp.client.RetriFlowRemoteMcpClient.call_tool",
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
        self.assertEqual(result.calls[0].tool_id, "stock_query")
        self.assertIn("贵州茅台", result.calls[0].content)


if __name__ == "__main__":
    unittest.main()
