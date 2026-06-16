import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowKnowledgeRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"

        from core.config import get_settings
        from core.state import initialize_database
        from modules.knowledge import RetriFlowKnowledgeService
        from schemas.knowledge import KnowledgeBaseCreateRequest, KnowledgeDocumentCreateRequest

        get_settings.cache_clear()
        initialize_database()

        knowledge_service = RetriFlowKnowledgeService()
        knowledge_service.create_knowledge_base(KnowledgeBaseCreateRequest(name="Insurance KB"))
        knowledge_service.create_document(
            "kb-1",
            KnowledgeDocumentCreateRequest(
                title="Insurance handbook",
                source_type="manual",
                content=(
                    "Insurance claims, underwriting, premiums, reimbursement and policy workflows "
                    "belong to this knowledge base."
                ),
            ),
        )

    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        os.environ.pop("RETRIFLOW_ROUTE_USE_LLM", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_route_profiles_are_persisted_for_knowledge_bases(self) -> None:
        from core.state import get_connection

        with get_connection() as connection:
            rows = connection.execute(
                """
                select knowledge_base_id, profile_text, sample_questions_json, keywords_json
                from knowledge_base_route_profiles
                order by knowledge_base_id
                """
            ).fetchall()

        self.assertGreaterEqual(len(rows), 1)
        insurance_row = next(row for row in rows if row["knowledge_base_id"] == "kb-1")
        self.assertIn("Insurance KB", insurance_row["profile_text"])
        self.assertIn("Insurance handbook", insurance_row["profile_text"])
        self.assertIn("insurance", insurance_row["keywords_json"].lower())

    def test_route_question_uses_profile_match_when_llm_is_disabled(self) -> None:
        from modules.knowledge.routing import RetriFlowKnowledgeRouteService

        decision = RetriFlowKnowledgeRouteService().route_question("保险理赔流程是什么？")

        self.assertEqual(decision.mode, "knowledge_base")
        self.assertEqual(decision.knowledge_base_ids, ["kb-1"])
        self.assertGreater(decision.confidence, 0.45)

    def test_route_question_uses_llm_result_when_available(self) -> None:
        os.environ["RETRIFLOW_ROUTE_USE_LLM"] = "true"
        from core.config import get_settings
        from modules.knowledge.routing import RetriFlowKnowledgeRouteService

        get_settings.cache_clear()

        with patch(
            "modules.knowledge.routing.RetriFlowLLMService.route_knowledge_bases",
            return_value={
                "mode": "knowledge_base",
                "knowledge_base_ids": ["kb-1"],
                "confidence": 0.93,
                "reason": "matched insurance domain",
            },
        ) as route_mock:
            decision = RetriFlowKnowledgeRouteService().route_question("保险保单核保规则有哪些？")

        route_mock.assert_called_once()
        self.assertEqual(decision.mode, "knowledge_base")
        self.assertEqual(decision.knowledge_base_ids, ["kb-1"])
        self.assertEqual(decision.confidence, 0.93)

    def test_route_question_falls_back_when_llm_route_fails(self) -> None:
        os.environ["RETRIFLOW_ROUTE_USE_LLM"] = "true"
        from core.config import get_settings
        from modules.knowledge.routing import RetriFlowKnowledgeRouteService

        get_settings.cache_clear()

        with patch(
            "modules.knowledge.routing.RetriFlowLLMService.route_knowledge_bases",
            side_effect=RuntimeError("route provider unavailable"),
        ):
            decision = RetriFlowKnowledgeRouteService().route_question("保险理赔材料清单是什么？")

        self.assertEqual(decision.mode, "knowledge_base")
        self.assertEqual(decision.knowledge_base_ids, ["kb-1"])
        self.assertGreater(decision.confidence, 0.45)


if __name__ == "__main__":
    unittest.main()
