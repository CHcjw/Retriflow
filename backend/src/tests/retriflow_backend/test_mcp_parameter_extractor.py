import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowMcpParameterExtractorTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"
        from core.config import get_settings

        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        from core.config import get_settings

        get_settings.cache_clear()

    def test_weather_tool_uses_heuristic_parameter_extraction_when_llm_is_disabled(self) -> None:
        from domain.mcp.executors import WeatherMcpToolExecutor
        from domain.mcp.parameter_extractor import RetriFlowMcpParameterExtractor

        extractor = RetriFlowMcpParameterExtractor()
        params = extractor.extract(
            question="北京今天天气怎么样？",
            tool_definition=WeatherMcpToolExecutor().get_definition(),
        )

        self.assertEqual(params["city"], "北京")
        self.assertEqual(params["query_type"], "current")

    def test_sales_tool_extracts_region_and_period(self) -> None:
        from domain.mcp.executors import SalesMcpToolExecutor
        from domain.mcp.parameter_extractor import RetriFlowMcpParameterExtractor

        extractor = RetriFlowMcpParameterExtractor()
        params = extractor.extract(
            question="帮我看一下华东本周销售表现",
            tool_definition=SalesMcpToolExecutor().get_definition(),
        )

        self.assertEqual(params["region"], "华东")
        self.assertEqual(params["period"], "this_week")


if __name__ == "__main__":
    unittest.main()
