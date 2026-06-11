import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowIntentClassifierTests(unittest.TestCase):
    def tearDown(self) -> None:
        keys = [
            "RETRIFLOW_LLM_PROVIDER",
            "RETRIFLOW_INTENT_PROVIDER",
            "RETRIFLOW_INTENT_CONFIDENCE_THRESHOLD",
        ]
        for key in keys:
            os.environ.pop(key, None)

        from core.config import get_settings

        get_settings.cache_clear()

    def test_classifier_uses_rule_for_tool_call(self) -> None:
        from domain.intent_classifier import RetriFlowIntentClassifier

        decision = RetriFlowIntentClassifier().classify(
            question="北京今天天气怎么样？",
            memory_messages=[],
        )

        self.assertEqual(decision.intent, "tool_call")
        self.assertEqual(decision.source, "rule")
        self.assertGreater(decision.confidence, 0.7)

    def test_classifier_uses_rule_for_chitchat(self) -> None:
        from domain.intent_classifier import RetriFlowIntentClassifier

        decision = RetriFlowIntentClassifier().classify(
            question="你好呀，先打个招呼",
            memory_messages=[],
        )

        self.assertEqual(decision.intent, "chitchat")
        self.assertEqual(decision.source, "rule")

    def test_classifier_uses_rule_for_clarification_when_context_is_missing(self) -> None:
        from domain.intent_classifier import RetriFlowIntentClassifier

        decision = RetriFlowIntentClassifier().classify(
            question="这个怎么处理？",
            memory_messages=[],
        )

        self.assertEqual(decision.intent, "clarification")
        self.assertEqual(decision.source, "rule")
        self.assertTrue(decision.clarification_question)

    def test_classifier_falls_back_to_knowledge_retrieval_when_llm_classification_fails(self) -> None:
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"

        from core.config import get_settings
        from domain.intent_classifier import RetriFlowIntentClassifier

        get_settings.cache_clear()

        decision = RetriFlowIntentClassifier().classify(
            question="保险理赔流程是什么？",
            memory_messages=[],
        )

        self.assertEqual(decision.intent, "knowledge_retrieval")
        self.assertEqual(decision.source, "fallback")

    def test_classifier_accepts_llm_result_when_confident(self) -> None:
        os.environ["RETRIFLOW_INTENT_PROVIDER"] = "ollama"

        from core.config import get_settings
        from domain.intent_classifier import RetriFlowIntentClassifier

        get_settings.cache_clear()

        with patch(
            "domain.intent_classifier.RetriFlowLLMService.extract_json_object",
            return_value={
                "intent": "tool_call",
                "confidence": 0.91,
                "reason": "matched tool usage",
                "clarification_question": "",
            },
        ):
            decision = RetriFlowIntentClassifier().classify(
                question="请判断这个需求更适合走工具还是知识库",
                memory_messages=[{"role": "user", "content": "我们继续"}],
            )

        self.assertEqual(decision.intent, "tool_call")
        self.assertEqual(decision.source, "llm")
        self.assertEqual(decision.reason, "matched tool usage")


if __name__ == "__main__":
    unittest.main()
