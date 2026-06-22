import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowPromptServiceTests(unittest.TestCase):
    def _source(self):
        from schemas.chat import ChatSourceItem

        return ChatSourceItem(
            chunk_id=1,
            knowledge_base_id="kb-1",
            document_id=1,
            document_title="Policy",
            content="Use UTF-8 for all text files.",
            score=0.9,
        )

    def test_prompt_service_selects_scene_from_context(self) -> None:
        from modules.rag.prompt import PromptScene, RAGPromptService

        service = RAGPromptService()

        kb_plan = service.plan(question="How to encode files?", sources=[self._source()], extra_context="")
        self.assertEqual(kb_plan.scene, PromptScene.KB_ONLY)
        self.assertIn("Use UTF-8", kb_plan.kb_context)

        mcp_plan = service.plan(question="Check weather", sources=[], extra_context="weather tool returned sunny")
        self.assertEqual(mcp_plan.scene, PromptScene.MCP_ONLY)
        self.assertIn("weather tool", mcp_plan.mcp_context)

        mixed_plan = service.plan(question="Summarize", sources=[self._source()], extra_context="tool result")
        self.assertEqual(mixed_plan.scene, PromptScene.MIXED)

        empty_plan = service.plan(question="Hello", sources=[], extra_context="")
        self.assertEqual(empty_plan.scene, PromptScene.EMPTY)

    def test_prompt_service_builds_existing_answer_prompts_without_changing_sections(self) -> None:
        from modules.rag.prompt import RAGPromptService

        service = RAGPromptService()
        messages = service.build_messages(question="How to encode files?", sources=[self._source()])

        self.assertEqual([message["role"] for message in messages], ["system", "user"])
        self.assertIn("无法从知识库中找到答案", messages[0]["content"])
        self.assertIn("【参考资料】", messages[1]["content"])
        self.assertIn("【用户问题】", messages[1]["content"])
