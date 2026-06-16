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


class RetriFlowAdminApiTests(unittest.TestCase):
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

    def _register_and_login(self, username: str, role: str) -> str:
        self.client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "Password123", "role": role},
        )
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Password123"},
        )
        return response.json()["access_token"]

    def test_admin_can_create_user(self) -> None:
        token = self._register_and_login("admin-user", "admin")

        response = self.client.post(
            "/api/v1/admin/users",
            json={"username": "created-user", "password": "Password123", "role": "user"},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["username"], "created-user")
        self.assertEqual(payload["role"], "user")
        self.assertTrue(payload["created_at"])

    def test_seed_admin_password_hash_matches_default_password(self) -> None:
        from modules.auth import RetriFlowAuthService

        password_hash = "retriflow-seed-salt$3dcb8cd47f903b433a8eb58c95de902033e5a86d8956a4ddc51020965710a67d"

        self.assertTrue(RetriFlowAuthService._verify_password("admin", password_hash))

    def test_non_admin_cannot_create_user(self) -> None:
        token = self._register_and_login("normal-user", "user")

        response = self.client.post(
            "/api/v1/admin/users",
            json={"username": "blocked-user", "password": "Password123", "role": "user"},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_get_trace_detail(self) -> None:
        token = self._register_and_login("trace-admin", "admin")
        session_response = self.client.post(
            "/api/v1/sessions",
            json={"title": "Trace detail session"},
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = session_response.json()["id"]

        from core.state import get_connection

        with get_connection() as connection:
            connection.execute(
                "insert into conversation_messages (session_id, role, content, duration_ms) values (?, ?, ?, ?)",
                (session_id, "user", "hello trace", 0),
            )
            connection.execute(
                "insert into conversation_messages (session_id, role, content, duration_ms) values (?, ?, ?, ?)",
                (session_id, "assistant", "trace answer", 1234),
            )
            connection.execute("update sessions set message_count = 2 where id = ?", (session_id,))
            connection.commit()

        response = self.client.get(
            f"/api/v1/admin/traces/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], session_id)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["duration_ms"], 1234)
        self.assertEqual(payload["messages"][0]["duration_ms"], 0)
        self.assertEqual(payload["messages"][1]["duration_ms"], 1234)

        list_response = self.client.get(
            "/api/v1/admin/traces",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(list_response.status_code, 200)
        trace_item = next(item for item in list_response.json()["items"] if item["id"] == session_id)
        self.assertEqual(trace_item["duration_ms"], 1234)

    def test_admin_dashboard_is_backed_by_database(self) -> None:
        token = self._register_and_login("dashboard-admin", "admin")

        response = self.client.get(
            "/api/v1/admin/dashboard?range=7d",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["range"], "7d")
        self.assertIn("core", payload)
        self.assertIn("ai_performance", payload)
        self.assertIn("quality_snapshot", payload)
        self.assertIn("traffic_overview", payload)
        self.assertIn("trend_panels", payload)
        self.assertIn("ops_efficiency", payload)
        self.assertIn("ops_insights", payload)
        self.assertGreaterEqual(len(payload["core"]), 1)
        self.assertEqual(len(payload["traffic_overview"]["labels"]), 7)
        self.assertEqual(len(payload["trend_panels"]), 4)

    def test_admin_can_manage_intent_nodes(self) -> None:
        token = self._register_and_login("intent-admin", "admin")

        create_response = self.client.post(
            "/api/v1/admin/intent-nodes",
            json={
                "name": "售后咨询",
                "code": "after_sales",
                "level": "DOMAIN",
                "node_type": "KB",
                "parent_id": "ROOT",
                "description": "处理售后政策类问题",
                "sample_questions": ["可以退货吗？"],
                "rule_snippet": "命中退货、换货、保修等问题",
                "prompt_template": "只基于售后知识回答。",
                "top_k": 5,
                "sort_order": 10,
                "enabled": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["code"], "after_sales")
        self.assertEqual(created["sample_questions"], ["可以退货吗？"])

        update_response = self.client.patch(
            f"/api/v1/admin/intent-nodes/{created['id']}",
            json={"name": "售后政策", "enabled": False, "top_k": 8},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["name"], "售后政策")
        self.assertFalse(updated["enabled"])
        self.assertEqual(updated["top_k"], 8)

        list_response = self.client.get(
            "/api/v1/admin/intent-nodes",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(item["id"] == created["id"] for item in list_response.json()["items"]))

        delete_response = self.client.delete(
            f"/api/v1/admin/intent-nodes/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(delete_response.status_code, 204)

    def test_admin_can_manage_keyword_mappings(self) -> None:
        token = self._register_and_login("keyword-admin", "admin")

        create_response = self.client.post(
            "/api/v1/admin/keyword-mappings",
            json={
                "raw_keyword": "退钱",
                "target_keyword": "退款",
                "match_type": "contains",
                "priority": 20,
                "enabled": True,
                "remark": "口语归一化",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["target_keyword"], "退款")

        update_response = self.client.patch(
            f"/api/v1/admin/keyword-mappings/{created['id']}",
            json={"priority": 30, "enabled": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["priority"], 30)
        self.assertFalse(updated["enabled"])

        delete_response = self.client.delete(
            f"/api/v1/admin/keyword-mappings/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(delete_response.status_code, 204)


if __name__ == "__main__":
    unittest.main()
