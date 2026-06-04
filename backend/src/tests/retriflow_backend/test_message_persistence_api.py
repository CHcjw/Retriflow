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


class RetriFlowMessagePersistenceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)

        from core.config import get_settings

        get_settings.cache_clear()
        from main import create_app

        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_chat_message_is_persisted_with_assistant_reply(self) -> None:
        response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": "session-demo-1", "message": "请说明 RetriFlow 当前能力"},
        )
        self.assertEqual(response.status_code, 200)

        messages_response = self.client.get("/api/v1/sessions/session-demo-1/messages")
        self.assertEqual(messages_response.status_code, 200)
        payload = messages_response.json()

        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["role"], "user")
        self.assertEqual(payload["items"][1]["role"], "assistant")
        self.assertIn("RetriFlow", payload["items"][1]["content"])


if __name__ == "__main__":
    unittest.main()
