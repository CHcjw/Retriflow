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

        from core.config import get_settings

        get_settings.cache_clear()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        os.environ.pop("RETRIFLOW_WORKFLOW_ADAPTER", None)
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
            "domain.workflow_adapter.RetriFlowLLMService.generate_answer",
            return_value="这是来自模型服务的回答。[1]",
        ) as generate_answer:
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "请总结一下生成链路"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("这是来自模型服务的回答。", payload["assistant_message"])
        self.assertIn("## 参考来源", payload["assistant_message"])
        self.assertEqual(payload["workflow"]["adapter"], "langgraph")
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

        with patch("domain.llm.RetriFlowLLMService._post_json", new=fake_post_json):
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
            "domain.workflow_adapter.RetriFlowLLMService.generate_answer",
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
            "domain.workflow_adapter.RetriFlowLLMService.generate_answer",
            return_value="质量问题退货时，运费由商家承担。[1]",
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "质量问题退货运费谁承担？"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("## 参考来源", payload["assistant_message"])
        self.assertIn("[1] Shipping rule", payload["assistant_message"])
        self.assertIn("/api/v1/knowledge-bases/kb-demo-1/documents/2/chunks", payload["assistant_message"])

    def test_stream_chat_returns_sse_events_with_final_answer(self) -> None:
        self._rebuild_app_with_langgraph()

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
            json={"session_id": "session-demo-1", "message": "RetriFlow streaming workflow"},
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
            "domain.workflow_adapter.RetriFlowLLMService.stream_answer",
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
        self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Insurance KB"},
        )
        self.client.post(
            "/api/v1/knowledge-bases/kb-2/documents",
            json={
                "title": "Insurance handbook",
                "source_type": "manual",
                "content": "Insurance claims and underwriting knowledge live in this knowledge base.",
            },
        )

        fake_route = {
            "mode": "knowledge_base",
            "knowledge_base_ids": ["kb-2"],
            "confidence": 0.92,
            "reason": "matched insurance domain",
        }

        with patch("domain.workflow_adapter.RetriFlowKnowledgeRouteService.route_question", return_value=fake_route):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "保险理赔流程是什么？"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["sources"])
        self.assertTrue(all(item["knowledge_base_id"] == "kb-2" for item in payload["sources"]))


if __name__ == "__main__":
    unittest.main()
