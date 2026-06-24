import asyncio
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
from core.state import get_connection


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
        with get_connection() as connection:
            connection.execute(
                """
                insert into admin_sample_questions (
                    id, title, description, question, sort_order, enabled
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                ("sample-chat-bootstrap", "系统交互", "关于助手", "询问助手是做什么的、是谁、能做什么等", 10, 1),
            )
            connection.commit()

        response = self.client.get("/api/v1/chat/bootstrap")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["product"], "RetriFlow")
        self.assertIn("stream_chat", payload["capabilities"])
        self.assertIn("询问助手是做什么的、是谁、能做什么等", payload["starter_prompts"])

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
                json={"session_id": "session-demo-1", "message": "summarize generation path"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["assistant_message"])
        self.assertEqual(payload["workflow"]["adapter"], "langgraph")
        self.assertTrue(payload["sources"])
        self.assertIn("LLM workflow note", {source["document_title"] for source in payload["sources"]})
        generate_answer.assert_called_once()

    def test_llm_generation_uses_three_part_prompt_and_low_temperature(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Return policy",
                "source_type": "manual",
                "content": "Opened iPhone 16 Pro Max units do not support seven-day no-reason returns except quality issues.",
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
                            "content": "According to the reference, opened iPhone 16 Pro Max units normally cannot be returned without reason, but quality issues can use after-sales checks. [1]"
                        }
                    }
                ]
            }

        with patch("infra.llm.service.RetriFlowLLMService._post_json", new=fake_post_json):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "Can an opened iPhone 16 Pro Max be returned?"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("[1]", payload["assistant_message"])
        self.assertEqual(captured_payload["path"], "/chat/completions")
        request_payload = captured_payload["payload"]
        self.assertEqual(request_payload["temperature"], 0.1)
        self.assertEqual(request_payload["messages"][0]["role"], "system")
        self.assertTrue(request_payload["messages"][0]["content"])
        self.assertEqual(request_payload["messages"][1]["role"], "user")
        self.assertIn("参考资料", request_payload["messages"][1]["content"])
        self.assertIn("用户问题", request_payload["messages"][1]["content"])

    def test_chat_message_response_includes_formatted_source_links(self) -> None:
        self._rebuild_app_with_langgraph()

        document_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "RetriFlow source rule",
                "source_type": "manual",
                "content": "RetriFlow source links should point to document chunk routes in chat responses.",
            },
        )
        self.assertEqual(document_response.status_code, 201)

        with patch(
            "modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer",
            return_value="RetriFlow source links point to document chunk routes. [1]",
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "RetriFlow source links document chunk routes"},
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
                "title": "RetriFlow reference rule",
                "source_type": "manual",
                "content": "RetriFlow reference sections should keep source metadata and cite retrieved context.",
            },
        )

        with patch(
            "modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer",
            return_value="RetriFlow reference sections keep source metadata. [1]",
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "RetriFlow reference sections source metadata"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assistant_message"], "RetriFlow reference sections keep source metadata. [1]")
        self.assertTrue(payload["sources"])
        self.assertEqual(payload["sources"][0]["document_title"], "RetriFlow reference rule")
        self.assertEqual(
            payload["sources"][0]["source_link"],
            "/api/v1/knowledge-bases/kb-demo-1/documents/2/chunks",
        )

    def test_assessment_count_question_uses_statistical_source(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "软件工程复习材料",
                "source_type": "manual",
                "content": (
                    "第一部分 复习提纲\n"
                    "一、名词解释(本题共4小题,每小题5分,共20分)\n"
                    "二、单选题(本题共20小题,每小题1分,共20分)\n"
                    "三、问答题(本题共2小题,每题10分,共20分)\n"
                    "四、应用题(第1小题20分,第2小题10分,第3小题10分,共40分)\n"
                    "第二部分 选择题练习\n"
                    "1、软件工程管理的具体内容不包括对_______管理。\n"
                    "14、软件过程成熟度模型CMMI认证最高级别是( )。"
                ),
            },
        )

        with patch("modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer") as generate_answer:
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "软件工程复习题有多少道"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("29 道", payload["assistant_message"])
        self.assertIn("名词解释4小题", payload["assistant_message"])
        self.assertIn("单选题20小题", payload["assistant_message"])
        self.assertIn("问答题2小题", payload["assistant_message"])
        self.assertIn("应用题3小题", payload["assistant_message"])
        self.assertLess(payload["sources"][0]["chunk_id"], 0)
        self.assertIn("题目统计线索", payload["sources"][0]["content"])
        generate_answer.assert_not_called()

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
            return_value=iter(["first ", "second ", "third"]),
        ) as stream_answer:
            with self.client.stream(
                "POST",
                "/api/v1/chat/stream",
                json={"session_id": "session-demo-1", "message": "stream the answer"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

        self.assertIn('data: {"content": "first "}', body)
        self.assertIn('data: {"content": "second "}', body)
        self.assertIn('data: {"content": "third"}', body)
        self.assertIn("event: final", body)
        stream_answer.assert_called_once()

        messages_response = self.client.get("/api/v1/sessions/session-demo-1/messages")
        self.assertEqual(messages_response.status_code, 200)
        items = messages_response.json()["items"]
        self.assertEqual(items[-1]["role"], "assistant")
        self.assertIn("first second third", items[-1]["content"])

    def test_stream_chat_trace_covers_sse_lifecycle_and_first_packet(self) -> None:
        self._rebuild_app_with_langgraph()

        with patch(
            "modules.rag.workflow_adapter.RetriFlowLLMService.stream_answer",
            return_value=iter(["alpha ", "beta"]),
        ):
            with self.client.stream(
                "POST",
                "/api/v1/chat/stream",
                json={"session_id": "session-demo-1", "message": "trace stream lifecycle"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

        self.assertIn("event: done", body)

        trace_response = self.client.get("/api/v1/admin/traces/session-demo-1/nodes")
        self.assertEqual(trace_response.status_code, 200)
        nodes = trace_response.json()["items"]
        stream_roots = [node for node in nodes if node["name"] == "chat.stream"]
        self.assertEqual(len(stream_roots), 1)
        root = stream_roots[0]
        names = [node["name"] for node in nodes]

        self.assertEqual(root["status"], "success")
        self.assertIn("events=done", root["output_summary"])
        self.assertIn("user-first-packet", names)
        first_packet = next(node for node in nodes if node["name"] == "user-first-packet")
        self.assertEqual(first_packet["node_type"], "USER_TTFT")
        self.assertEqual(first_packet["status"], "success")
        self.assertEqual(first_packet["parent_id"], root["id"])
        generation = next(node for node in nodes if node["name"] == "generation.answer")
        self.assertEqual(generation["status"], "success")
        self.assertIn("chunks=2", generation["output_summary"])
        self.assertEqual(generation["parent_id"], root["id"])

    def test_stream_chat_trace_cancels_generation_when_client_disconnects_before_deltas(self) -> None:
        self._rebuild_app_with_langgraph()

        from modules.chat.streaming import RetriFlowStreamingService
        from schemas.chat import ChatMessageRequest

        async def consume_workflow_then_close() -> str:
            stream = RetriFlowStreamingService().build_event_stream(
                ChatMessageRequest(session_id="session-demo-1", message="cancel before deltas"),
                user_id="user-admin",
            )
            first_event = await anext(stream)
            await stream.aclose()
            return first_event

        with patch(
            "modules.rag.workflow_adapter.RetriFlowLLMService.stream_answer",
            return_value=iter(["late answer"]),
        ):
            first_event = asyncio.run(consume_workflow_then_close())

        self.assertIn("event: workflow", first_event)

        trace_response = self.client.get("/api/v1/admin/traces/session-demo-1/nodes")
        self.assertEqual(trace_response.status_code, 200)
        nodes = trace_response.json()["items"]
        root = next(node for node in nodes if node["name"] == "chat.stream")
        generation = next(node for node in nodes if node["name"] == "generation.answer")
        self.assertEqual(root["status"], "cancelled")
        self.assertEqual(generation["status"], "cancelled")
        self.assertEqual(generation["parent_id"], root["id"])

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

    def test_home_chat_routes_each_rewritten_query_and_merges_knowledge_bases(self) -> None:
        first_response = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Insurance KB"},
        )
        second_response = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "RetriFlow KB"},
        )
        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        insurance_kb_id = first_response.json()["id"]
        retriflow_kb_id = second_response.json()["id"]
        self.client.post(
            f"/api/v1/knowledge-bases/{insurance_kb_id}/documents",
            json={
                "title": "Claim handbook",
                "source_type": "manual",
                "content": "Claim reimbursement procedures and insurance policy rules.",
            },
        )
        self.client.post(
            f"/api/v1/knowledge-bases/{retriflow_kb_id}/documents",
            json={
                "title": "RetriFlow migration",
                "source_type": "manual",
                "content": "RetriFlow migration uses LangGraph and retrieval workflows.",
            },
        )

        def fake_route(question: str):
            if "claim" in question:
                return {
                    "mode": "knowledge_base",
                    "knowledge_base_ids": [insurance_kb_id],
                    "confidence": 0.91,
                    "reason": "claim route",
                }
            return {
                "mode": "knowledge_base",
                "knowledge_base_ids": [retriflow_kb_id],
                "confidence": 0.89,
                "reason": "retriflow route",
            }

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
                return_value=["claim reimbursement", "retriflow migration"],
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowKnowledgeRouteService.route_question",
                side_effect=fake_route,
            ) as route_mock,
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "summarize claims and retriflow migration"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        route_questions = [call.args[0] for call in route_mock.call_args_list]
        self.assertEqual(route_questions, ["claim reimbursement", "retriflow migration"])
        source_knowledge_bases = {item["knowledge_base_id"] for item in payload["sources"]}
        self.assertIn(insurance_kb_id, source_knowledge_bases)
        self.assertIn(retriflow_kb_id, source_knowledge_bases)

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
        self.assertTrue(payload["assistant_message"])

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
                json={"session_id": "session-demo-1", "message": "Summarize Beijing weather and RetriFlow migration together"},
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
                    "The user previously discussed migration plans, deployment limits, and pending confirmations.",
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
                ("session-demo-1", "user", "Previous user question", "2026-06-09 10:00:00"),
            )
            connection.execute(
                """
                insert into conversation_messages (session_id, role, content, created_at)
                values (?, ?, ?, ?)
                """,
                ("session-demo-1", "assistant", "Previous assistant answer", "2026-06-09 10:01:00"),
            )
            connection.commit()

        with patch("infra.llm.service.RetriFlowLLMService._post_json", new=fake_post_json):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "continue the previous topic"},
            )

        self.assertEqual(response.status_code, 200)
        request_payload = captured_payload["payload"]
        self.assertEqual(captured_payload["path"], "/chat/completions")
        self.assertEqual(request_payload["messages"][1]["role"], "system")
        self.assertTrue(request_payload["messages"][1]["content"])
        self.assertEqual(request_payload["messages"][2]["role"], "user")
        self.assertTrue(request_payload["messages"][2]["content"])
        self.assertEqual(request_payload["messages"][3]["role"], "assistant")
        self.assertTrue(request_payload["messages"][3]["content"])

    def _create_assistant_message(self, session_id: str = "session-demo-1") -> int:
        from core.state import get_connection

        with get_connection() as connection:
            cursor = connection.execute(
                """
                insert into conversation_messages (session_id, role, content, duration_ms)
                values (?, ?, ?, ?)
                returning id
                """,
                (session_id, "assistant", "Feedback target answer", 12),
            )
            message_id = int(cursor.fetchone()[0])
            connection.execute("update sessions set message_count = message_count + 1 where id = ?", (session_id,))
            connection.commit()
        return message_id

    def test_submit_message_feedback_upserts_assistant_message_vote(self) -> None:
        message_id = self._create_assistant_message()

        create_response = self.client.post(
            f"/api/v1/chat/messages/{message_id}/feedback",
            json={"vote": 1, "reason": "helpful", "comment": "good answer"},
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["vote"], 1)

        update_response = self.client.post(
            f"/api/v1/chat/messages/{message_id}/feedback",
            json={"vote": -1, "reason": "wrong", "comment": "missed context"},
        )
        self.assertEqual(update_response.status_code, 200)
        payload = update_response.json()
        self.assertEqual(payload["vote"], -1)
        self.assertEqual(payload["reason"], "wrong")

        admin_response = self.client.get("/api/v1/admin/message-feedback")
        self.assertEqual(admin_response.status_code, 200)
        items = admin_response.json()["items"]
        self.assertEqual(len([item for item in items if item["message_id"] == message_id]), 1)
        self.assertEqual(next(item for item in items if item["message_id"] == message_id)["vote"], -1)

    def test_submit_message_feedback_rejects_user_message(self) -> None:
        from core.state import get_connection

        with get_connection() as connection:
            cursor = connection.execute(
                """
                insert into conversation_messages (session_id, role, content)
                values (?, ?, ?)
                returning id
                """,
                ("session-demo-1", "user", "Can I rate myself?"),
            )
            message_id = int(cursor.fetchone()[0])
            connection.commit()

        response = self.client.post(
            f"/api/v1/chat/messages/{message_id}/feedback",
            json={"vote": 1},
        )

        self.assertEqual(response.status_code, 400)


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
        self.assertIn("retrieval_stage_metrics", payload["workflow"])
        stage_metrics = payload["workflow"]["retrieval_stage_metrics"]
        self.assertGreaterEqual(stage_metrics["bm25"]["latency_ms"], 0)
        self.assertGreaterEqual(stage_metrics["semantic"]["latency_ms"], 0)
        self.assertEqual(stage_metrics["bm25"]["query_count"], 1)
        self.assertEqual(stage_metrics["semantic"]["top_k"], 80)
        self.assertIn("input_records", stage_metrics["hybrid_rrf"])
        self.assertEqual(stage_metrics["final"]["records"], payload["workflow"]["retrieval_count"])

    def test_chat_message_returns_pipeline_stage_sequence(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Pipeline stage note",
                "source_type": "manual",
                "content": "RetriFlow should expose the chat pipeline stages for runtime tracing.",
            },
        )

        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": "session-demo-1", "message": "pipeline tracing"},
        )

        self.assertEqual(response.status_code, 200)
        stages = response.json()["workflow"]["pipeline_stages"]
        self.assertEqual(stages[0], "memory")
        self.assertIn("intent", stages)
        self.assertIn("rewrite", stages)
        self.assertIn("route", stages)
        self.assertIn("retrieval", stages)
        self.assertEqual(stages[-1], "generation")

    def test_chat_message_persists_rag_trace_nodes_for_workflow_stages(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Trace node note",
                "source_type": "manual",
                "content": "RetriFlow should persist node-level RAG trace stages for admin observability.",
            },
        )

        session_id = "session-demo-1"
        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": session_id, "message": "trace the RetriFlow workflow"},
        )
        self.assertEqual(response.status_code, 200)

        trace_response = self.client.get(f"/api/v1/admin/traces/{session_id}/nodes")
        self.assertEqual(trace_response.status_code, 200)
        nodes = trace_response.json()["items"]
        names = [node["name"] for node in nodes]

        self.assertIn("chat.run", names)
        self.assertIn("memory.load_prompt_messages", names)
        self.assertIn("intent-resolve", names)
        self.assertIn("query-rewrite-and-split", names)
        self.assertIn("knowledge.route", names)
        self.assertIn("retrieval-engine", names)
        self.assertIn("multi-channel-retrieval", names)
        self.assertIn("generation.answer", names)
        self.assertTrue(all(node["status"] == "success" for node in nodes))
        root = next(node for node in nodes if node["name"] == "chat.run")
        self.assertEqual(root["parent_id"], "")
        self.assertTrue(any(node["parent_id"] == root["id"] for node in nodes if node["name"] != "chat.run"))
        retrieval = next(node for node in nodes if node["name"] == "retrieval-engine")
        multi_channel = next(node for node in nodes if node["name"] == "multi-channel-retrieval")
        self.assertEqual(multi_channel["parent_id"], retrieval["id"])

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
                json={"session_id": "session-demo-1", "message": "How should these two topics be handled?"},
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
    def test_chat_message_rewrites_before_tool_call_intent(self) -> None:
        self._rebuild_app_with_langgraph()

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
                return_value=["What is the weather today?"],
            ),
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
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "What is the weather today?"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "tool_call")
        self.assertEqual(payload["workflow"]["rewritten_queries"], ["What is the weather today?"])
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
                "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
                return_value=["hello"],
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer",
                return_value="Hello, how can I help you today?",
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "hello"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "chitchat")
        self.assertEqual(payload["workflow"]["retrieval_count"], 0)
        self.assertEqual(payload["workflow"]["rewrite_query_count"], 1)
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
                    "clarification_question": "你说的“这个”具体指哪个产品、订单或文档？",
                },
            ),
            patch("modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite", return_value=["What does it mean?"]),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "What does it mean?"}
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "clarification")
        self.assertTrue(payload["assistant_message"])
        self.assertEqual(payload["workflow"]["retrieval_count"], 0)
        self.assertEqual(payload["workflow"]["rewrite_query_count"], 1)
        self.assertEqual(payload["workflow"]["route_mode"], "clarification")

    def test_chat_message_overrides_llm_clarification_for_retrievable_question(self) -> None:
        self._rebuild_app_with_langgraph()

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "软件工程复习资料",
                "source_type": "manual",
                "content": "软件工程复习题包括选择题、填空题和简答题。复习题总数为 26 道。",
            },
        )

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
                return_value={
                    "intent": "clarification",
                    "confidence": 0.9,
                    "reason": "question is short",
                    "source": "llm",
                    "clarification_question": "请问您指的是哪个课程、学校或考试类型的软件工程复习题？",
                },
            ),
            patch(
                "modules.rag.workflow_adapter.RetriFlowLLMService.generate_answer",
                return_value="软件工程复习题共有 26 道。[1]",
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "软件工程复习题有多少道"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "knowledge_retrieval")
        self.assertIn("overrode non-referential clarification", payload["workflow"]["intent_reason"])
        self.assertGreaterEqual(payload["workflow"]["retrieval_count"], 1)
        self.assertIn("26", payload["assistant_message"])

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
                json={"session_id": "session-demo-1", "message": "Explain the RetriFlow fallback behavior"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["intent"], "knowledge_retrieval")
        self.assertEqual(payload["workflow"]["intent_source"], "fallback")
        self.assertGreaterEqual(payload["workflow"]["retrieval_count"], 1)


if __name__ == "__main__":
    unittest.main()
