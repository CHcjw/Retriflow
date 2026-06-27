import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowMcpSourceExtractionTests(unittest.TestCase):
    def test_call_tool_extracts_sources_from_structured_text(self) -> None:
        from modules.mcp.client import RemoteMcpServerConfig, RetriFlowRemoteMcpClient

        client = RetriFlowRemoteMcpClient(
            RemoteMcpServerConfig(name="search-remote", url="http://mcp.example")
        )

        with patch.object(
            client,
            "_post_jsonrpc",
            return_value={
                "content": [
                    {
                        "type": "text",
                        "text": '{"results":[{"title":"广州天气","url":"https://example.com/weather","snippet":"晴，30℃"}]}',
                    }
                ],
                "isError": False,
            },
        ):
            result = client.call_tool("AIsearch", {"query": "广州天气"})

        self.assertEqual(result.sources[0]["title"], "广州天气")
        self.assertEqual(result.sources[0]["url"], "https://example.com/weather")
        self.assertIn("30", result.sources[0]["snippet"])


if __name__ == "__main__":
    unittest.main()
