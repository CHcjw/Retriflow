import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))

from modules.rag.postprocess import RetriFlowAnswerPostprocessor


class RetriFlowAnswerPostprocessorTests(unittest.TestCase):
    def test_finalize_preserves_markdown_strong_syntax(self) -> None:
        answer = "根据参考资料：\n\n- **迁移流程**：迁移到 Python 和 Vue。"

        finalized = RetriFlowAnswerPostprocessor().finalize(answer, [])

        self.assertIn("**迁移流程**", finalized)
        self.assertIn("- **迁移流程**", finalized)


if __name__ == "__main__":
    unittest.main()
