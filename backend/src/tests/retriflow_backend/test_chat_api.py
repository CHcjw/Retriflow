import sys
import unittest
from pathlib import Path
import os
import tempfile
import uuid
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
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"
        from core.config import get_settings

        get_settings.cache_clear()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

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
        self.assertIn("keyword", payload["workflow"]["retrieval_channels"])
        self.assertIn("document", payload["workflow"]["retrieval_channels"])
        self.assertEqual(payload["workflow"]["adapter"], "langgraph")

    def test_chat_message_deduplicates_and_sorts_sources_from_multiple_channels(self) -> None:
        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Retrieval note A",
                "source_type": "manual",
                "content": "RetriFlow retrieval combines LangGraph context with source chunks.",
            },
        )
        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Retrieval note B",
                "source_type": "manual",
                "content": "LangGraph retrieval in RetriFlow should return ranked source chunks.",
            },
        )

        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": "session-demo-1", "message": "RetriFlow LangGraph retrieval"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        sources = payload["sources"]
        self.assertGreaterEqual(len(sources), 2)
        self.assertEqual(len({item["chunk_id"] for item in sources}), len(sources))
        self.assertGreaterEqual(sources[0]["score"], sources[1]["score"])

    def test_chat_workflow_reports_hybrid_retrieval_channels(self) -> None:
        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Graph workflow design",
                "source_type": "manual",
                "content": "RetriFlow combines lexical and semantic style retrieval before answer generation.",
            },
        )

        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": "session-demo-1", "message": "semantic retrieval workflow"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("keyword", payload["workflow"]["retrieval_channels"])
        self.assertIn("document", payload["workflow"]["retrieval_channels"])
        self.assertIn("semantic", payload["workflow"]["retrieval_channels"])
        self.assertGreaterEqual(payload["workflow"]["retrieval_count"], 1)

    def test_langgraph_adapter_is_selected_when_dependencies_exist(self) -> None:
        os.environ["RETRIFLOW_WORKFLOW_ADAPTER"] = "langgraph"

        from core.config import get_settings
        from domain.workflow_adapter import resolve_workflow_adapter

        get_settings.cache_clear()
        adapter = resolve_workflow_adapter()

        self.assertEqual(adapter.name, "langgraph")

    def test_chat_message_reports_langgraph_adapter_when_workflow_is_forced(self) -> None:
        os.environ["RETRIFLOW_WORKFLOW_ADAPTER"] = "langgraph"
        from core.config import get_settings
        from main import create_app

        get_settings.cache_clear()
        self.client.close()
        self.client = TestClient(create_app())

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "LangGraph runtime note",
                "source_type": "manual",
                "content": "RetriFlow can switch between fallback and LangGraph-backed workflow adapters.",
            },
        )

        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": "session-demo-1", "message": "workflow adapter status"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["adapter"], "langgraph")

    def test_chat_message_uses_llm_service_output_when_langgraph_generation_succeeds(self) -> None:
        os.environ["RETRIFLOW_WORKFLOW_ADAPTER"] = "langgraph"
        from core.config import get_settings
        from main import create_app

        get_settings.cache_clear()
        self.client.close()
        self.client = TestClient(create_app())

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
            return_value="这是来自模型服务的回答。",
        ) as generate_answer:
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "请总结一下生成链路"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assistant_message"], "这是来自模型服务的回答。")
        self.assertEqual(payload["workflow"]["adapter"], "langgraph")
        generate_answer.assert_called_once()

    def test_chat_message_falls_back_when_llm_service_generation_fails(self) -> None:
        os.environ["RETRIFLOW_WORKFLOW_ADAPTER"] = "langgraph"
        from core.config import get_settings
        from main import create_app

        get_settings.cache_clear()
        self.client.close()
        self.client = TestClient(create_app())

        self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            json={
                "title": "Fallback workflow note",
                "source_type": "manual",
                "content": "RetriFlow should degrade gracefully when the LLM provider is unavailable.",
            },
        )

        with patch(
            "domain.workflow_adapter.RetriFlowLLMService.generate_answer",
            side_effect=RuntimeError("provider unavailable"),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={"session_id": "session-demo-1", "message": "provider unavailable workflow"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["adapter"], "langgraph")
        self.assertIn("Fallback workflow note", payload["assistant_message"])
        self.assertIn("provider unavailable", payload["assistant_message"])

    def test_stream_chat_returns_sse_events_with_workflow_and_delta(self) -> None:
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
        self.assertIn("retriflow_langgraph_ready", body)

    def test_stream_chat_uses_llm_stream_deltas_and_persists_full_reply(self) -> None:
        os.environ["RETRIFLOW_WORKFLOW_ADAPTER"] = "langgraph"
        from core.config import get_settings
        from main import create_app

        get_settings.cache_clear()
        self.client.close()
        self.client = TestClient(create_app())

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
        stream_answer.assert_called_once()

        messages_response = self.client.get("/api/v1/sessions/session-demo-1/messages")
        self.assertEqual(messages_response.status_code, 200)
        items = messages_response.json()["items"]
        self.assertEqual(items[-1]["role"], "assistant")
        self.assertEqual(items[-1]["content"], "第一段。第二段。第三段。")


if __name__ == "__main__":
    unittest.main()
