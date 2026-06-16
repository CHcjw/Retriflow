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


class RetriFlowSessionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"
        from core.config import get_settings

        get_settings.cache_clear()
        self.client = TestClient(create_app())
        self.token = self._register_and_login("session-user")

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def _register_and_login(self, username: str) -> str:
        self.client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "Password123", "role": "user"},
        )
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Password123"},
        )
        return response.json()["access_token"]

    def test_sessions_endpoint_returns_only_current_user_sessions(self) -> None:
        response = self.client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"], [])

    def test_create_session_accepts_owner_id(self) -> None:
        response = self.client.post(
            "/api/v1/sessions",
            json={"title": "Owner scoped session", "owner_id": "user-42"},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["owner_id"])

    def test_delete_session_removes_owned_session(self) -> None:
        created = self.client.post(
            "/api/v1/sessions",
            json={"title": "Delete me"},
            headers={"Authorization": f"Bearer {self.token}"},
        ).json()

        response = self.client.delete(
            f"/api/v1/sessions/{created['id']}",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 204)
        listed = self.client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {self.token}"},
        ).json()
        self.assertEqual(listed["items"], [])

    def test_delete_session_removes_legacy_unowned_session(self) -> None:
        from core.state import get_connection

        with get_connection() as connection:
            connection.execute(
                "insert into sessions (id, title, message_count, owner_id) values (?, ?, ?, ?)",
                ("session-legacy", "Legacy session", 0, ""),
            )
            connection.commit()

        response = self.client.delete(
            "/api/v1/sessions/session-legacy",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 204)
        with get_connection() as connection:
            session_row = connection.execute(
                "select count(*) as c from sessions where id = ?",
                ("session-legacy",),
            ).fetchone()
        self.assertEqual(session_row["c"], 0)

    def test_delete_session_removes_messages_for_owned_session(self) -> None:
        created = self.client.post(
            "/api/v1/sessions",
            json={"title": "Delete with messages"},
            headers={"Authorization": f"Bearer {self.token}"},
        ).json()

        chat_response = self.client.post(
            "/api/v1/chat/messages",
            json={"session_id": created["id"], "message": "请说明删除会话后的消息清理行为"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(chat_response.status_code, 200)

        before_delete = self.client.get(
            f"/api/v1/sessions/{created['id']}/messages",
            headers={"Authorization": f"Bearer {self.token}"},
        ).json()
        self.assertEqual(len(before_delete["items"]), 2)

        response = self.client.delete(
            f"/api/v1/sessions/{created['id']}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 204)

        from core.state import get_connection

        with get_connection() as connection:
            session_row = connection.execute(
                "select count(*) as c from sessions where id = ?",
                (created["id"],),
            ).fetchone()
            message_row = connection.execute(
                "select count(*) as c from conversation_messages where session_id = ?",
                (created["id"],),
            ).fetchone()

        self.assertEqual(session_row["c"], 0)
        self.assertEqual(message_row["c"], 0)

    def test_update_session_title_renames_owned_session(self) -> None:
        created = self.client.post(
            "/api/v1/sessions",
            json={"title": "Original Title"},
            headers={"Authorization": f"Bearer {self.token}"},
        ).json()

        response = self.client.patch(
            f"/api/v1/sessions/{created['id']}",
            json={"title": "Updated Title"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Updated Title")

        # Verify list returns the new title
        listed = self.client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {self.token}"},
        ).json()
        self.assertEqual(listed["items"][0]["title"], "Updated Title")


if __name__ == "__main__":
    unittest.main()
