import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))

from main import create_app


class RetriFlowMutationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_meta_endpoint_returns_frontend_targets(self) -> None:
        response = self.client.get("/api/v1/meta")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["frontend_name"], "RetriFlow Web")
        self.assertIn("chat", payload["primary_routes"])

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
        response = self.client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "session-demo-1",
                "message": "RetriFlow 下一步做什么？",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session_id"], "session-demo-1")
        self.assertIn("RetriFlow", payload["assistant_message"])

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
