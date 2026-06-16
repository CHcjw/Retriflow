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


if __name__ == "__main__":
    unittest.main()
