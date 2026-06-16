import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowRemoteMcpClientTests(unittest.TestCase):
    def test_list_tools_parses_json_rpc_response(self) -> None:
        from modules.mcp.client import RemoteMcpServerConfig, RetriFlowRemoteMcpClient

        client = RetriFlowRemoteMcpClient(
            RemoteMcpServerConfig(name="finance-remote", url="http://mcp.example")
        )

        with patch.object(
            client,
            "_post_jsonrpc",
            return_value={
                "tools": [
                    {
                        "name": "stock_query",
                        "description": "查询股票行情",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string", "default": "000001"},
                            },
                        },
                        "keywords": ["股票", "股价", "行情"],
                    }
                ]
            },
        ):
            tools = client.list_tools()

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].tool_id, "stock_query")
        self.assertIn("股票", tools[0].keywords)

    def test_call_tool_parses_text_content(self) -> None:
        from modules.mcp.client import RemoteMcpServerConfig, RetriFlowRemoteMcpClient

        client = RetriFlowRemoteMcpClient(
            RemoteMcpServerConfig(name="finance-remote", url="http://mcp.example")
        )

        with patch.object(
            client,
            "_post_jsonrpc",
            return_value={
                "content": [
                    {"type": "text", "text": "贵州茅台当前价格表现稳定。"},
                ],
                "isError": False,
            },
        ):
            result = client.call_tool("stock_query", {"ticker": "600519"})

        self.assertEqual(result.tool_id, "stock_query")
        self.assertEqual(result.arguments["ticker"], "600519")
        self.assertIn("贵州茅台", result.content)
        self.assertFalse(result.is_error)

    def test_call_tool_uses_fallback_text_when_remote_returns_empty_content(self) -> None:
        from modules.mcp.client import RemoteMcpServerConfig, RetriFlowRemoteMcpClient

        client = RetriFlowRemoteMcpClient(
            RemoteMcpServerConfig(name="finance-remote", url="http://mcp.example")
        )

        with patch.object(
            client,
            "_post_jsonrpc",
            return_value={"content": [], "isError": False},
        ):
            result = client.call_tool("stock_query", {"ticker": "600519"})

        self.assertIn("未返回文本内容", result.content)


if __name__ == "__main__":
    unittest.main()
