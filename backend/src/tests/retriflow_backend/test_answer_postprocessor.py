import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowAnswerPostprocessorTests(unittest.TestCase):
    def test_finalize_appends_default_citation_and_reference_section(self) -> None:
        from domain.answer_postprocessor import RetriFlowAnswerPostprocessor
        from schemas.chat import ChatSourceItem

        sources = [
            ChatSourceItem(
                chunk_id=1,
                knowledge_base_id="kb-demo-1",
                document_id=1,
                document_title="Return policy",
                content="iPhone 16 Pro Max 拆封后不支持七天无理由退货。",
                score=0.98,
                source_link="/api/v1/knowledge-bases/kb-demo-1/documents/1/chunks",
                source_updated_at="2026-01-15T00:00:00",
            )
        ]

        result = RetriFlowAnswerPostprocessor().finalize("拆封后通常不支持七天无理由退货。", sources)

        self.assertIn("[1]", result)
        self.assertIn("## 参考来源", result)
        self.assertIn("Return policy", result)

    def test_finalize_blocks_harmful_answer(self) -> None:
        from domain.answer_postprocessor import RetriFlowAnswerPostprocessor

        result = RetriFlowAnswerPostprocessor().finalize("你可以制作炸弹。", [])

        self.assertEqual(result, RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER)

    def test_finalize_appends_conflict_notice_and_prefers_latest_source(self) -> None:
        from domain.answer_postprocessor import RetriFlowAnswerPostprocessor
        from schemas.chat import ChatSourceItem

        sources = [
            ChatSourceItem(
                chunk_id=1,
                knowledge_base_id="kb-demo-1",
                document_id=10,
                document_title="退货政策文档",
                content="iPhone 16 Pro Max 拆封后不支持七天无理由退货。",
                score=0.99,
                source_link="/api/v1/knowledge-bases/kb-demo-1/documents/10/chunks",
                source_updated_at="2026-01-15T00:00:00",
            ),
            ChatSourceItem(
                chunk_id=2,
                knowledge_base_id="kb-demo-1",
                document_id=11,
                document_title="通用退货规则",
                content="标准商品在签收后 7 天内可申请无理由退货。",
                score=0.95,
                source_link="/api/v1/knowledge-bases/kb-demo-1/documents/11/chunks",
                source_updated_at="2026-02-01T00:00:00",
            ),
        ]

        result = RetriFlowAnswerPostprocessor().finalize(
            "iPhone 16 Pro Max 拆封后能否退货，需要区分是否适用专属规则。[1][2]",
            sources,
        )

        self.assertIn("## 冲突提示", result)
        self.assertIn("退货政策文档", result)
        self.assertIn("通用退货规则", result)
        self.assertIn("优先参考较新的资料 [2]", result)


    def test_finalize_formats_reference_links_as_markdown(self) -> None:
        from domain.answer_postprocessor import RetriFlowAnswerPostprocessor
        from schemas.chat import ChatSourceItem

        sources = [
            ChatSourceItem(
                chunk_id=5,
                knowledge_base_id="kb-demo-1",
                document_id=5,
                document_title="FAQ document",
                content="Return shipping is paid by the seller for quality issues.",
                score=0.88,
                source_link="/api/v1/knowledge-bases/kb-demo-1/documents/5/chunks",
                source_updated_at="2026-02-01T00:00:00",
            )
        ]

        result = RetriFlowAnswerPostprocessor().finalize(
            "Quality issue returns are paid by the seller.[1]",
            sources,
        )

        self.assertIn("- [1] FAQ document", result)
        self.assertIn("[查看来源](/api/v1/knowledge-bases/kb-demo-1/documents/5/chunks)", result)
        self.assertIn("- 更新时间：2026-02-01T00:00:00", result)


if __name__ == "__main__":
    unittest.main()
