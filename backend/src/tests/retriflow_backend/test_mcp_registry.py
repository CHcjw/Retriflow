import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowMcpRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "false"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = "[]"
        from core.config import get_settings

        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_MCP_REMOTE_ENABLED", None)
        os.environ.pop("RETRIFLOW_MCP_REMOTE_SERVERS_JSON", None)
        from core.config import get_settings

        get_settings.cache_clear()

    def test_registry_auto_registers_builtin_tools(self) -> None:
        from modules.mcp.registry import RetriFlowMcpRegistry

        registry = RetriFlowMcpRegistry()

        tool_ids = {tool.tool_id for tool in registry.list_tools()}
        self.assertIn("weather_query", tool_ids)
        self.assertIn("sales_query", tool_ids)
        self.assertIn("ticket_query", tool_ids)
        self.assertTrue(registry.contains("weather_query"))
        self.assertGreaterEqual(registry.size(), 3)
        self.assertGreaterEqual(len(registry.list_executors()), 3)

    def test_registry_can_unregister_tool(self) -> None:
        from modules.mcp.registry import RetriFlowMcpRegistry

        registry = RetriFlowMcpRegistry()

        self.assertTrue(registry.contains("weather_query"))
        registry.unregister("weather_query")

        self.assertFalse(registry.contains("weather_query"))
        self.assertIsNone(registry.get_executor("weather_query"))

    def test_registry_can_register_remote_tools(self) -> None:
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "true"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = (
            '[{"name":"finance-remote","url":"http://mcp.example"}]'
        )
        from core.config import get_settings
        from modules.mcp.models import McpToolDefinition
        from modules.mcp.registry import RetriFlowMcpRegistry

        get_settings.cache_clear()

        remote_tool = McpToolDefinition(
            tool_id="stock_query",
            description="查询股票行情",
            parameter_schema={"type": "object", "properties": {"ticker": {"type": "string"}}},
            keywords=["股票", "股价", "行情"],
        )

        with patch(
            "modules.mcp.registry.RetriFlowRemoteMcpClient.list_tools",
            return_value=[remote_tool],
        ):
            registry = RetriFlowMcpRegistry()

        tool_ids = {tool.tool_id for tool in registry.list_tools()}
        self.assertIn("stock_query", tool_ids)
        statuses = registry.remote_server_statuses()
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].name, "finance-remote")
        self.assertTrue(statuses[0].healthy)
        self.assertEqual(statuses[0].tool_count, 1)

    def test_remote_tool_with_same_id_overrides_builtin_executor(self) -> None:
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "true"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = (
            '[{"name":"weather-remote","url":"http://mcp.example"}]'
        )
        from core.config import get_settings
        from modules.mcp.models import McpToolDefinition
        from modules.mcp.registry import RetriFlowMcpRegistry

        get_settings.cache_clear()

        remote_weather = McpToolDefinition(
            tool_id="weather_query",
            description="联网查询真实天气",
            parameter_schema={"type": "object", "properties": {"city": {"type": "string"}}},
            keywords=["天气"],
            server_name="weather-remote",
            transport="streamable_http",
        )

        with patch(
            "modules.mcp.registry.RetriFlowRemoteMcpClient.list_tools",
            return_value=[remote_weather],
        ):
            registry = RetriFlowMcpRegistry()

        executor = registry.get_executor("weather_query")
        self.assertIsNotNone(executor)
        definition = executor.get_definition()
        self.assertEqual(definition.server_name, "weather-remote")
        self.assertEqual(definition.transport, "streamable_http")

    def test_registry_skips_unhealthy_remote_server_without_losing_builtins(self) -> None:
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "true"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = (
            '[{"name":"bad-remote","url":"http://mcp.invalid"}]'
        )
        from core.config import get_settings
        from modules.mcp.registry import RetriFlowMcpRegistry

        get_settings.cache_clear()

        with patch(
            "modules.mcp.registry.RetriFlowRemoteMcpClient.list_tools",
            side_effect=RuntimeError("remote unavailable"),
        ):
            registry = RetriFlowMcpRegistry()

        tool_ids = {tool.tool_id for tool in registry.list_tools()}
        self.assertIn("weather_query", tool_ids)
        self.assertIn("sales_query", tool_ids)
        self.assertIn("ticket_query", tool_ids)

        statuses = registry.remote_server_statuses()
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].name, "bad-remote")
        self.assertFalse(statuses[0].healthy)
        self.assertEqual(statuses[0].tool_count, 0)
        self.assertIn("remote unavailable", statuses[0].error)


if __name__ == "__main__":
    unittest.main()
