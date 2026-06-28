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
        os.environ["RETRIFLOW_STORAGE_BACKEND"] = "local"
        os.environ["RETRIFLOW_STORAGE_LOCAL_DIR"] = str(Path(self.temp_dir.name) / "uploads")

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
        os.environ.pop("RETRIFLOW_STORAGE_BACKEND", None)
        os.environ.pop("RETRIFLOW_STORAGE_LOCAL_DIR", None)
        os.environ.pop("RETRIFLOW_ROUTE_USE_LLM", None)
        os.environ.pop("RETRIFLOW_INTENT_TREE_CACHE_ENABLED", None)
        os.environ.pop("RETRIFLOW_INTENT_TREE_CACHE_REDIS_URL", None)
        os.environ.pop("RETRIFLOW_INTENT_TREE_CACHE_KEY", None)
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

    def test_route_question_uses_admin_intent_tree_nodes(self) -> None:
        from modules.admin import RetriFlowAdminService
        from modules.knowledge.routing import RetriFlowKnowledgeRouteService
        from schemas.admin import AdminIntentNodeCreateRequest

        RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Insurance Claims",
                code="insurance_claims",
                level="INTENT",
                node_type="KB",
                knowledge_base_id="kb-1",
                description="Claims reimbursement routing",
                sample_questions=["How do I submit claim reimbursement materials?"],
                rule_snippet="claim reimbursement materials payout",
                top_k=6,
                sort_order=1,
            )
        )

        decision = RetriFlowKnowledgeRouteService().route_question("claim reimbursement materials checklist")

        self.assertEqual(decision.mode, "knowledge_base")
        self.assertEqual(decision.knowledge_base_ids, ["kb-1"])
        self.assertGreaterEqual(decision.confidence, 0.45)
        self.assertIn("intent path", decision.reason)
        self.assertEqual(decision.candidates[0].top_k, 6)

    def test_route_question_falls_back_from_matched_parent_to_child_kb_node(self) -> None:
        from modules.admin import RetriFlowAdminService
        from modules.knowledge.routing import RetriFlowKnowledgeRouteService
        from schemas.admin import AdminIntentNodeCreateRequest

        parent = RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Claims Domain",
                code="claims_domain",
                level="DOMAIN",
                node_type="KB",
                description="insurance claims domain",
                sort_order=1,
            )
        )
        RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Claims Reimbursement Leaf",
                code="claims_reimbursement_leaf",
                level="TOPIC",
                node_type="KB",
                parent_id=parent.id,
                knowledge_base_id="kb-1",
                description="reimbursement materials checklist",
                sort_order=1,
            )
        )

        decision = RetriFlowKnowledgeRouteService().route_question("insurance claims domain")

        self.assertEqual(decision.mode, "knowledge_base")
        self.assertEqual(decision.knowledge_base_ids, ["kb-1"])
        self.assertIn("Claims Domain", decision.reason)
        self.assertIn("Claims Reimbursement Leaf", decision.reason)
        self.assertEqual(decision.candidates[0].matched_node_path, "Claims Domain")
        self.assertEqual(decision.candidates[0].target_node_path, "Claims Domain / Claims Reimbursement Leaf")
        self.assertGreater(decision.candidates[0].target_score, 0)
        self.assertIn("insurance", decision.candidates[0].matched_terms)

    def test_route_question_uses_mcp_intent_tree_nodes(self) -> None:
        from modules.admin import RetriFlowAdminService
        from modules.knowledge.routing import RetriFlowKnowledgeRouteService
        from schemas.admin import AdminIntentNodeCreateRequest

        parent = RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Sales Domain",
                code="sales_domain",
                level="DOMAIN",
                node_type="MCP",
                description="sales statistics domain",
                sort_order=1,
            )
        )
        RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Sales Statistics",
                code="sales_statistics_leaf",
                level="CATEGORY",
                node_type="MCP",
                parent_id=parent.id,
                mcp_tool_id="sales_query",
                description="sales amount and sales volume statistics",
                sort_order=1,
            )
        )

        decision = RetriFlowKnowledgeRouteService().route_question("sales statistics domain")

        self.assertEqual(decision.mode, "mcp")
        self.assertEqual(decision.knowledge_base_ids, [])
        self.assertEqual(decision.mcp_tool_ids, ["sales_query"])
        self.assertIn("Sales Domain", decision.reason)
        self.assertIn("Sales Statistics", decision.reason)

    def test_route_question_keeps_multiple_intent_tree_candidates(self) -> None:
        from modules.admin import RetriFlowAdminService
        from modules.knowledge import RetriFlowKnowledgeService
        from modules.knowledge.routing import RetriFlowKnowledgeRouteService
        from schemas.admin import AdminIntentNodeCreateRequest
        from schemas.knowledge import KnowledgeBaseCreateRequest, KnowledgeDocumentCreateRequest

        knowledge_service = RetriFlowKnowledgeService()
        knowledge_service.create_knowledge_base(KnowledgeBaseCreateRequest(name="RetriFlow KB"))
        knowledge_service.create_document(
            "kb-2",
            KnowledgeDocumentCreateRequest(
                title="RetriFlow workflow guide",
                source_type="manual",
                content="RetriFlow workflow uses LangGraph, LangChain, RAG and retrieval workflows.",
            ),
        )

        admin_service = RetriFlowAdminService()
        admin_service.create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Insurance Claims",
                code="multi_insurance_claims",
                level="INTENT",
                node_type="KB",
                knowledge_base_id="kb-1",
                description="insurance claim reimbursement policy",
                sample_questions=["How do claim reimbursements work?"],
                rule_snippet="claim reimbursement insurance policy",
                sort_order=1,
            )
        )
        admin_service.create_intent_node(
            AdminIntentNodeCreateRequest(
                name="RetriFlow Workflow",
                code="multi_retriflow_workflow",
                level="INTENT",
                node_type="KB",
                knowledge_base_id="kb-2",
                description="retriflow workflow langgraph rag",
                sample_questions=["How does RetriFlow workflow work?"],
                rule_snippet="retriflow workflow langgraph rag",
                sort_order=2,
            )
        )

        decision = RetriFlowKnowledgeRouteService().route_question(
            "claim reimbursement and retriflow workflow"
        )

        self.assertEqual(decision.mode, "knowledge_base")
        self.assertEqual(decision.knowledge_base_ids, ["kb-1", "kb-2"])
        self.assertLessEqual(len(decision.knowledge_base_ids), 3)
        self.assertIn("Insurance Claims", decision.reason)
        self.assertIn("RetriFlow Workflow", decision.reason)
        self.assertEqual([candidate.knowledge_base_id for candidate in decision.candidates], ["kb-1", "kb-2"])

        from modules.rag.guidance import RetriFlowIntentGuidanceService

        guidance = RetriFlowIntentGuidanceService().detect("policy workflow", decision)
        self.assertTrue(guidance.is_prompt)
        self.assertIn("Insurance Claims", guidance.prompt)
        self.assertIn("RetriFlow Workflow", guidance.prompt)

    def test_intent_tree_is_cached_in_redis_and_cleared_on_admin_change(self) -> None:
        import redis

        redis_url = os.getenv("RETRIFLOW_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
        cache_key = f"retriflow:test:intent:tree:{uuid.uuid4().hex}"
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        client.delete(cache_key)

        os.environ["RETRIFLOW_INTENT_TREE_CACHE_ENABLED"] = "true"
        os.environ["RETRIFLOW_INTENT_TREE_CACHE_REDIS_URL"] = redis_url
        os.environ["RETRIFLOW_INTENT_TREE_CACHE_KEY"] = cache_key

        from core.config import get_settings
        from modules.admin import RetriFlowAdminService
        from modules.knowledge.routing import RetriFlowKnowledgeRouteService
        from schemas.admin import AdminIntentNodeCreateRequest

        get_settings.cache_clear()
        RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Cached Claims",
                code="cached_claims",
                level="INTENT",
                node_type="KB",
                knowledge_base_id="kb-1",
                description="cached claim reimbursement",
                sort_order=1,
            )
        )

        decision = RetriFlowKnowledgeRouteService().route_question("cached claim reimbursement")

        self.assertEqual(decision.mode, "knowledge_base")
        self.assertTrue(client.exists(cache_key))

        RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Another Cached Claims",
                code="another_cached_claims",
                level="INTENT",
                node_type="KB",
                knowledge_base_id="kb-1",
                description="another cached claim",
                sort_order=2,
            )
        )

        self.assertFalse(client.exists(cache_key))


if __name__ == "__main__":
    unittest.main()
