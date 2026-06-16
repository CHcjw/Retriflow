import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))

from main import create_app


class RetriFlowChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"
        os.environ["RETRIFLOW_SEED_DEMO_CONTENT"] = "true"

        from core.config import get_settings

        get_settings.cache_clear()
        self.client = TestClient(create_app())
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.token = login_response.json()["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        self._ensure_legacy_demo_session()

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        os.environ.pop("RETRIFLOW_SEED_DEMO_CONTENT", None)
        os.environ.pop("RETRIFLOW_WORKFLOW_ADAPTER", None)
        os.environ.pop("RETRIFLOW_MEMORY_MID_ENABLED", None)
        os.environ.pop("RETRIFLOW_MEMORY_MID_MAX_ITEMS", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def _rebuild_app_with_langgraph(self) -> None:
        os.environ["RETRIFLOW_WORKFLOW_ADAPTER"] = "langgraph"
        from core.config import get_settings

        get_settings.cache_clear()
        self.client.close()
        self.client = TestClient(create_app())
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.token = login_response.json()["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        self._ensure_legacy_demo_session()

    @staticmethod
    def _ensure_legacy_demo_session() -> None:
        from core.state import get_connection

        with get_connection() as connection:
            row = connection.execute(
                """
                select id
                from sessions
                where id = ?
                limit 1
                """,
                ("session-demo-1",),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    insert into sessions (id, title, message_count, owner_id)
                    values (?, ?, ?, ?)
                    """,
                    ("session-demo-1", "RetriFlow migration planning", 0, "user-admin"),
                )
                connection.commit()

    def test_chat_bootstrap_endpoint_returns_capabilities(self) -> None:
        response = self.client.get("/api/v1/chat/bootstrap")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["product"], "RetriFlow")
        self.assertIn("stream_chat", payload["capabilities"])

    def test_chat_message_returns_retrieved_sources(self) -> None:
        document_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "LangGraph plan",
                "source_type": "manual",
                "content": (
                    "LangGraph orchestrates the RetriFlow chat workflow. "
                    "RetriFlow uses chunks and retrieval before generating answers."
                ),
            },
        )
        self.assertEqual(document_response.status_code, 201)

        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": "session-demo-1", "message": "LangGraph 在 RetriFlow 中做什么？"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("assistant_message", payload)
        self.assertGreaterEqual(len(payload["sources"]), 1)
        self.assertEqual(payload["sources"][0]["knowledge_base_id"], "kb-demo-1")
        self.assertIn("LangGraph", payload["sources"][0]["content"])
        self.assertEqual(payload["workflow"]["name"], "retriflow_langgraph_ready")
        self.assertIn("bm25", payload["workflow"]["retrieval_channels"])
        self.assertIn("semantic", payload["workflow"]["retrieval_channels"])
        self.assertIn("hybrid_rrf", payload["workflow"]["retrieval_channels"])
        self.assertIn("rerank", payload["workflow"]["retrieval_channels"])
        self.assertEqual(payload["workflow"]["adapter"], "langgraph")

    def test_chat_message_uses_llm_service_output_when_langgraph_generation_succeeds(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "LLM workflow note",
                "source_type": "manual",
                "content": "RetriFlow should pass retrieved context into the generation model.",
            },
        )

        with patch(
            "modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer",
            return_value="这是来自模型服务的回答。[1]",
        ) as generate_answer:
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "请总结一下生成链路"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("这是来自模型服务的回答。", payload["assistant_message"])
        self.assertEqual(payload["workflow"]["adapter"], "langgraph")
        self.assertTrue(payload["sources"])
        self.assertEqual(payload["sources"][0]["document_title"], "RetriFlow migration baseline")
        generate_answer.assert_called_once()

    def test_llm_generation_uses_three_part_prompt_and_low_temperature(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Return policy",
                "source_type": "manual",
                "content": "iPhone 16 Pro Max 拆封后不支持七天无理由退货，质量问题除外。",
            },
        )

        captured_payload: dict[str, object] = {}

        def fake_post_json(self, provider, payload, path):
            captured_payload["payload"] = payload
            captured_payload["path"] = path
            return {
                "choices": [
                    {
                        "message": {
                            "content": "根据参考资料，iPhone 16 Pro Max 拆封后通常不支持七天无理由退货，但如存在质量问题可走售后检测流程。[1]"
                        }
                    }
                ]
            }

        with patch("infra.llm.service.RetriFlowLLMService._post_json", new=fake_post_json):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "iPhone 16 Pro Max 拆封后还能退吗？"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("[1]", payload["assistant_message"])
        self.assertEqual(captured_payload["path"], "/chat/completions")
        request_payload = captured_payload["payload"]
        self.assertEqual(request_payload["temperature"], 0.1)
        self.assertEqual(request_payload["messages"][0]["role"], "system")
        self.assertIn("只基于【参考资料】", request_payload["messages"][0]["content"])
        self.assertEqual(request_payload["messages"][1]["role"], "user")
        self.assertIn("【参考资料】", request_payload["messages"][1]["content"])
        self.assertIn("【用户问题】", request_payload["messages"][1]["content"])

    def test_chat_message_response_includes_formatted_source_links(self) -> None:
        self._rebuild_app_with_langgraph()

        document_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "After-sales rule",
                "source_type": "manual",
                "content": "质量问题退货，运费由商家承担。",
            },
        )
        self.assertEqual(document_response.status_code, 201)

        with patch(
            "modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer",
            return_value="质量问题退货时，运费由商家承担。[1]",
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "质量问题退货运费谁承担？"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("source_link", payload["sources"][0])
        self.assertTrue(payload["sources"][0]["source_link"].endswith("/documents/2/chunks"))

    def test_chat_message_appends_markdown_reference_section(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Shipping rule",
                "source_type": "manual",
                "content": "质量问题退货，运费由商家承担。",
            },
        )

        with patch(
            "modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer",
            return_value="质量问题退货时，运费由商家承担。[1]",
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "质量问题退货运费谁承担？"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assistant_message"], "质量问题退货时，运费由商家承担。[1]")
        self.assertTrue(payload["sources"])
        self.assertEqual(payload["sources"][0]["document_title"], "Shipping rule")
        self.assertEqual(
            payload["sources"][0]["source_link"],
            "/api/v1/knowledge-bases/kb-demo-1/documents/2/chunks",
        )

    def test_stream_chat_returns_sse_events_with_final_answer(self) -> None:
        self._rebuild_app_with_langgraph()
        session_response = self.client.post(
            "/api/v1/sessions",
            json={"title": "Streaming test session"},
        )
        self.assertEqual(session_response.status_code, 201)
        session_id = session_response.json()["id"]

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Streaming note",
                "source_type": "manual",
                "content": "RetriFlow streaming chat should emit workflow metadata and assistant deltas.",
            },
        )

        with self.client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"session_id": session_id, "message": "RetriFlow streaming workflow"},
        ) as response:
            self.assertEqual(response.status_code, 200)
            body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

        self.assertIn("event: workflow", body)
        self.assertIn("event: delta", body)
        self.assertIn("event: final", body)
        self.assertIn("retriflow_langgraph_ready", body)

    def test_stream_chat_uses_llm_stream_deltas_and_persists_full_reply(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Streaming LLM note",
                "source_type": "manual",
                "content": "RetriFlow should forward model streaming chunks to the frontend in order.",
            },
        )

        with patch(
            "modules.rag.workflow_adapter.RetriFlowLLMService.stream_answer",
            return_value=iter(["第一段。", "第二段。", "第三段。"]),
        ) as stream_answer:
            with self.client.stream(
                "POST",
                "/api/v1/chat/stream",
                json={"session_id": "session-demo-1", "message": "请流式回答"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

        self.assertIn('data: {"content": "第一段。"}', body)
        self.assertIn('data: {"content": "第二段。"}', body)
        self.assertIn('data: {"content": "第三段。"}', body)
        self.assertIn("event: final", body)
        stream_answer.assert_called_once()

        messages_response = self.client.get("/api/v1/sessions/session-demo-1/messages")
        self.assertEqual(messages_response.status_code, 200)
        items = messages_response.json()["items"]
        self.assertEqual(items[-1]["role"], "assistant")
        self.assertIn("第一段。第二段。第三段。", items[-1]["content"])

    def test_home_chat_routes_retrieval_to_intent_matched_knowledge_base(self) -> None:
        kb_response = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Insurance KB"},
        )
        self.assertEqual(kb_response.status_code, 201)
        knowledge_base_id = kb_response.json()["id"]
        self.client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            json={
                "title": "Insurance handbook",
                "source_type": "manual",
                "content": "Insurance claims and underwriting knowledge live in this knowledge base.",
            },
        )

        fake_route = {
            "mode": "knowledge_base",
            "knowledge_base_ids": [knowledge_base_id],
            "confidence": 0.92,
            "reason": "matched insurance domain",
        }

        with patch("modules.rag.workflow_adapter.RetriFlowKnowledgeRouteService.route_question", return_value=fake_route):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "保险理赔流程是什么？"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["sources"])
        self.assertTrue(all(item["knowledge_base_id"] == knowledge_base_id for item in payload["sources"]))

    def test_chat_message_supports_mcp_only_tool_answer(self) -> None:
        self._rebuild_app_with_langgraph()

        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": "session-demo-1", "message": "北京今天天气怎么样？"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "mcp_only")
        self.assertEqual(payload["workflow"]["mcp_tool_count"], 1)
        self.assertTrue(payload["mcp_calls"])
        self.assertEqual(payload["mcp_calls"][0]["tool_id"], "weather_query")
        self.assertIn("北京", payload["assistant_message"])

    def test_chat_message_supports_mixed_kb_and_mcp_answer(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Weather migration note",
                "source_type": "manual",
                "content": "RetriFlow migration documentation mentions LangGraph deployment in Beijing.",
            },
        )

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowKnowledgeRouteService.route_question",
                return_value={
                    "mode": "knowledge_base",
                    "knowledge_base_ids": ["kb-demo-1"],
                    "confidence": 0.95,
                    "reason": "matched migration note",
                },
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
                return_value={
                    "intent": "tool_call",
                    "confidence": 0.95,
                    "reason": "contains both weather and migration intents",
                    "source": "rule",
                    "clarification_question": "",
                },
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "北京天气和 RetriFlow 迁移说明一起总结一下"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "mixed")
        self.assertEqual(payload["workflow"]["mcp_tool_count"], 1)
        self.assertGreaterEqual(payload["workflow"]["retrieval_count"], 1)
        self.assertTrue(payload["mcp_calls"])
        self.assertEqual(payload["mcp_calls"][0]["tool_id"], "weather_query")

    def test_chat_message_injects_short_term_memory_into_prompt(self) -> None:
        self._rebuild_app_with_langgraph()

        captured_payload: dict[str, object] = {}

        def fake_post_json(self, provider, payload, path):
            captured_payload["payload"] = payload
            captured_payload["path"] = path
            return {
                "choices": [
                    {
                        "message": {
                            "content": "已结合历史上下文给出回答。[1]"
                        }
                    }
                ]
            }

        from core.state import get_connection

        with get_connection() as connection:
            connection.execute(
                """
                insert into conversation_memory_summaries (session_id, content, last_message_id, updated_at, expires_at)
                values (?, ?, ?, ?, ?)
                """,
                (
                    "session-demo-1",
                    "用户之前讨论过迁移方案、部署限制和当前待确认事项。",
                    2,
                    "2026-06-09 09:00:00",
                    "2026-07-09 09:00:00",
                ),
            )
            connection.execute(
                """
                insert into conversation_messages (session_id, role, content, created_at)
                values (?, ?, ?, ?)
                """,
                ("session-demo-1", "user", "上一轮用户问题", "2026-06-09 10:00:00"),
            )
            connection.execute(
                """
                insert into conversation_messages (session_id, role, content, created_at)
                values (?, ?, ?, ?)
                """,
                ("session-demo-1", "assistant", "上一轮助手回答", "2026-06-09 10:01:00"),
            )
            connection.commit()

        with patch("infra.llm.service.RetriFlowLLMService._post_json", new=fake_post_json):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "继续刚才的话题"},
            )

        self.assertEqual(response.status_code, 200)
        request_payload = captured_payload["payload"]
        self.assertEqual(captured_payload["path"], "/chat/completions")
        self.assertEqual(request_payload["messages"][1]["role"], "system")
        self.assertIn("对话摘要", request_payload["messages"][1]["content"])
        self.assertIn("迁移方案", request_payload["messages"][1]["content"])
        self.assertEqual(request_payload["messages"][2]["role"], "user")
        self.assertIn("上一轮用户问题", request_payload["messages"][2]["content"])
        self.assertEqual(request_payload["messages"][3]["role"], "assistant")
        self.assertIn("上一轮助手回答", request_payload["messages"][3]["content"])


    def test_chat_message_injects_mid_term_memory_into_prompt(self) -> None:
        os.environ["RETRIFLOW_MEMORY_MID_ENABLED"] = "true"
        os.environ["RETRIFLOW_MEMORY_MID_MAX_ITEMS"] = "4"
        self._rebuild_app_with_langgraph()

        captured_payload: dict[str, object] = {}

        def fake_post_json(self, provider, payload, path):
            captured_payload["payload"] = payload
            captured_payload["path"] = path
            return {
                "choices": [
                    {
                        "message": {
                            "content": "Mid-term memory was injected.[1]"
                        }
                    }
                ]
            }

        from core.state import get_connection

        with get_connection() as connection:
            connection.execute(
                """
                insert into conversation_mid_memories (
                    session_id,
                    memory_type,
                    content,
                    status,
                    updated_at
                )
                values (?, ?, ?, ?, ?)
                """,
                (
                    "session-demo-1",
                    "goal",
                    "Complete RetriFlow mid-term memory support",
                    "active",
                    "2026-06-09 10:00:00",
                ),
            )
            connection.execute(
                """
                insert into conversation_mid_memories (
                    session_id,
                    memory_type,
                    content,
                    status,
                    updated_at
                )
                values (?, ?, ?, ?, ?)
                """,
                (
                    "session-demo-1",
                    "constraint",
                    "Keep current model configuration unchanged",
                    "active",
                    "2026-06-09 10:01:00",
                ),
            )
            connection.commit()

        with patch("modules.memory.service.RetriFlowConversationMidMemoryExtractor.extract", return_value=[]):
            with patch("infra.llm.service.RetriFlowLLMService._post_json", new=fake_post_json):
                response = self.client.post(
                    "/api/v1/chat/messages",
                    json={"session_id": "session-demo-1", "message": "continue memory design"},
                )

        self.assertEqual(response.status_code, 200)
        request_payload = captured_payload["payload"]
        self.assertEqual(captured_payload["path"], "/chat/completions")
        self.assertEqual(request_payload["messages"][1]["role"], "system")
        self.assertIn("中期记忆", request_payload["messages"][1]["content"])
        self.assertIn("Complete RetriFlow mid-term memory support", request_payload["messages"][1]["content"])
        self.assertIn("Keep current model configuration unchanged", request_payload["messages"][1]["content"])


    def test_chat_message_returns_retrieval_stage_counts(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Stage count note",
                "source_type": "manual",
                "content": "RetriFlow should expose retrieval stage counts for debugging.",
            },
        )

        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": "session-demo-1", "message": "retrieval debugging"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("retrieval_stage_counts", payload["workflow"])
        stage_counts = payload["workflow"]["retrieval_stage_counts"]
        self.assertIn("bm25", stage_counts)
        self.assertIn("semantic", stage_counts)
        self.assertIn("hybrid_rrf", stage_counts)
        self.assertIn("rerank", stage_counts)
        self.assertIn("final", stage_counts)
        self.assertEqual(stage_counts["final"], payload["workflow"]["retrieval_count"])

    def test_chat_message_returns_rewritten_queries_in_workflow_metadata(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Insurance process note",
                "source_type": "manual",
                "content": "Insurance claims and underwriting rules are stored in RetriFlow.",
            },
        )

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
                return_value={
                    "intent": "knowledge_retrieval",
                    "confidence": 0.95,
                    "reason": "forced by test",
                    "source": "rule",
                    "clarification_question": "",
                },
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
                return_value=["insurance claim process", "underwriting policy rules"],
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "这个和那个分别怎么处理？"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("rewritten_queries", payload["workflow"])
        self.assertEqual(
            payload["workflow"]["rewritten_queries"],
            ["insurance claim process", "underwriting policy rules"],
        )
        self.assertEqual(payload["workflow"]["rewrite_query_count"], 2)

    def test_chat_message_falls_back_to_original_query_when_rewrite_fails(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Rewrite fallback note",
                "source_type": "manual",
                "content": "RetriFlow should still retrieve when query rewrite is unavailable.",
            },
        )

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
                return_value={
                    "intent": "knowledge_retrieval",
                    "confidence": 0.95,
                    "reason": "forced by test",
                    "source": "rule",
                    "clarification_question": "",
                },
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
                side_effect=RuntimeError("rewrite provider unavailable"),
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "继续刚才那个问题"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["rewritten_queries"], ["继续刚才那个问题"])
        self.assertEqual(payload["workflow"]["rewrite_query_count"], 1)


    def test_chat_message_without_any_evidence_returns_standard_no_answer_reply(self) -> None:
        self._rebuild_app_with_langgraph()

        from modules.rag.postprocess import RetriFlowAnswerPostprocessor
        from modules.rag.workflow_adapter import PreparedWorkflowContext

        with patch(
            "modules.rag.workflow_adapter.LangGraphWorkflowAdapter._prepare_context",
            return_value=PreparedWorkflowContext(
                rewritten_queries=["RetriFlow business model"],
                route_mode="global",
                retrieval_channels=[],
                retrieval_stage_counts={},
                sources=[],
                extra_context="",
                mcp_calls=[],
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "RetriFlow business model"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assistant_message"], RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER)
        self.assertEqual(payload["workflow"]["retrieval_count"], 0)
        self.assertEqual(payload["workflow"]["mcp_tool_count"], 0)
    def test_chat_message_skips_query_rewrite_for_tool_call_intent(self) -> None:
        self._rebuild_app_with_langgraph()

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
                return_value={
                    "intent": "tool_call",
                    "confidence": 0.95,
                    "reason": "matched weather tool",
                    "source": "rule",
                    "clarification_question": "",
                },
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
                side_effect=AssertionError("rewrite should not be called"),
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "鍖椾含浠婂ぉ澶╂皵鎬庝箞鏍凤紵"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "tool_call")
        self.assertEqual(payload["workflow"]["rewrite_query_count"], 0)
        self.assertEqual(payload["workflow"]["route_mode"], "mcp_only")

    def test_chat_message_supports_chitchat_intent_without_retrieval(self) -> None:
        self._rebuild_app_with_langgraph()

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
                return_value={
                    "intent": "chitchat",
                    "confidence": 0.88,
                    "reason": "greeting",
                    "source": "rule",
                    "clarification_question": "",
                },
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer",
                return_value="浣犲ソ锛屾垜鍦ㄨ繖鍎匡紝鍙互鐩存帴鍜屼綘鑱婏紝涔熷彲浠ュ府浣犳煡鐭ヨ瘑搴撱€?",
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
                side_effect=AssertionError("rewrite should not be called"),
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "浣犲ソ"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "chitchat")
        self.assertEqual(payload["workflow"]["retrieval_count"], 0)
        self.assertEqual(payload["workflow"]["rewrite_query_count"], 0)
        self.assertEqual(payload["workflow"]["route_mode"], "chitchat")

    def test_chat_message_returns_clarification_question_for_clarification_intent(self) -> None:
        self._rebuild_app_with_langgraph()

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
                return_value={
                    "intent": "clarification",
                    "confidence": 0.9,
                    "reason": "missing referent",
                    "source": "rule",
                    "clarification_question": "浣犺鐨勨€滆繖涓€濆叿浣撴寚鍝釜浜у搧銆佽鍗曟垨鏂囨。锛?",
                },
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
                side_effect=AssertionError("rewrite should not be called"),
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "杩欎釜鎬庝箞澶勭悊锛?"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "clarification")
        self.assertEqual(payload["assistant_message"], "浣犺鐨勨€滆繖涓€濆叿浣撴寚鍝釜浜у搧銆佽鍗曟垨鏂囨。锛?")
        self.assertEqual(payload["workflow"]["retrieval_count"], 0)
        self.assertEqual(payload["workflow"]["route_mode"], "clarification")

    def test_chat_message_falls_back_to_knowledge_retrieval_when_intent_classification_fails(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Intent fallback note",
                "source_type": "manual",
                "content": "RetriFlow should default to knowledge retrieval when intent classification fails.",
            },
        )

        with patch(
            "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
            side_effect=RuntimeError("intent classifier unavailable"),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "RetriFlow 鐨勯粯璁ゆ剰鍥惧厹搴曟槸浠€涔堬紵"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "knowledge_retrieval")
        self.assertEqual(payload["workflow"]["intent_source"], "fallback")
        self.assertGreaterEqual(payload["workflow"]["retrieval_count"], 1)


if __name__ == "__main__":
    unittest.main()
