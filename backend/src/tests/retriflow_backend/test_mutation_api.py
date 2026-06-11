import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))

from main import create_app


class RetriFlowMutationApiTests(unittest.TestCase):
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
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.token = login_response.json()["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_meta_endpoint_returns_frontend_targets(self) -> None:
        response = self.client.get("/api/v1/meta")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["frontend_name"], "RetriFlow Web")
        self.assertIn("chat", payload["primary_routes"])
        self.assertEqual(payload["database_backend"], "sqlite")
        self.assertEqual(payload["runtime_database_backend"], "sqlite")

    def test_create_session_returns_new_session(self) -> None:
        response = self.client.post(
            "/api/v1/sessions",
            json={"title": "新的 RetriFlow 会话"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["title"], "新的 RetriFlow 会话")
        self.assertEqual(payload["message_count"], 0)

    def test_send_chat_message_returns_assistant_reply(self) -> None:
        session_response = self.client.post(
            "/api/v1/sessions",
            json={"title": "RetriFlow chat session"},
        )
        self.assertEqual(session_response.status_code, 201)
        session_id = session_response.json()["id"]

        response = self.client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": session_id,
                "message": "RetriFlow 下一步做什么？",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session_id"], session_id)
        self.assertIsInstance(payload["assistant_message"], str)
        self.assertTrue(payload["assistant_message"].strip())

    def test_create_knowledge_base_returns_new_item(self) -> None:
        response = self.client.post(
            "/api/v1/knowledge-bases",
            json={"name": "新知识库"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["name"], "新知识库")
        self.assertEqual(payload["product"], "RetriFlow")


if __name__ == "__main__":
    unittest.main()
