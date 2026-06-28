import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))

from modules.rag.postprocess import RetriFlowAnswerPostprocessor


class RetriFlowAnswerPostprocessorTests(unittest.TestCase):
    def test_finalize_preserves_markdown_strong_syntax(self) -> None:
        answer = "根据参考资料：\n\n- **问答链路**：先检索，再生成回答。"

        finalized = RetriFlowAnswerPostprocessor().finalize(answer, [])

        self.assertIn("**问答链路**", finalized)
        self.assertIn("- **问答链路**", finalized)

    def test_finalize_removes_inline_mcp_citations_when_no_kb_sources(self) -> None:
        answer = "今天广州天气晴，当前温度约20°C。[M1]"

        finalized = RetriFlowAnswerPostprocessor().finalize(answer, [])

        self.assertEqual(finalized, "今天广州天气晴，当前温度约20°C。")


if __name__ == "__main__":
    unittest.main()
