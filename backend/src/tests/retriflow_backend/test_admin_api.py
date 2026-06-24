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
        from infra.llm.health import get_model_health_service

        get_settings.cache_clear()
        get_model_health_service().reset()
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

    def test_admin_can_page_filter_update_and_delete_users(self) -> None:
        token = self._register_and_login("admin-owner", "admin")
        created_ids: list[str] = []
        for index in range(12):
            response = self.client.post(
                "/api/v1/admin/users",
                json={"username": f"staff-{index:02d}", "password": "Password123", "role": "user"},
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(response.status_code, 201)
            created_ids.append(response.json()["id"])

        page_response = self.client.get(
            "/api/v1/admin/users?page=1&page_size=5&q=staff",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(page_response.status_code, 200)
        page_payload = page_response.json()
        self.assertEqual(page_payload["total"], 12)
        self.assertEqual(page_payload["page"], 1)
        self.assertEqual(page_payload["page_size"], 5)
        self.assertEqual(len(page_payload["items"]), 5)

        update_response = self.client.patch(
            f"/api/v1/admin/users/{created_ids[0]}",
            json={"username": "staff-renamed", "role": "admin", "avatar_url": "https://example.test/avatar.png"},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["username"], "staff-renamed")
        self.assertEqual(updated["role"], "admin")
        self.assertEqual(updated["avatar_url"], "https://example.test/avatar.png")

        delete_response = self.client.delete(
            f"/api/v1/admin/users/{created_ids[1]}",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(delete_response.status_code, 204)
        filtered_response = self.client.get(
            "/api/v1/admin/users?q=staff-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual(filtered_response.json()["total"], 0)

    def test_admin_user_can_change_own_password(self) -> None:
        token = self._register_and_login("password-admin", "admin")

        response = self.client.patch(
            "/api/v1/admin/users/me/password",
            json={"old_password": "Password123", "new_password": "NewPassword123"},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 204)
        old_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "password-admin", "password": "Password123"},
        )
        self.assertEqual(old_login.status_code, 401)
        new_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "password-admin", "password": "NewPassword123"},
        )
        self.assertEqual(new_login.status_code, 200)

    def test_admin_cannot_delete_self(self) -> None:
        token = self._register_and_login("self-delete-admin", "admin")
        users_response = self.client.get(
            "/api/v1/admin/users?q=self-delete-admin",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = users_response.json()["items"][0]["id"]

        response = self.client.delete(
            f"/api/v1/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 400)

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

    def test_admin_can_get_trace_memory_diagnostics(self) -> None:
        token = self._register_and_login("memory-admin", "admin")
        session_response = self.client.post(
            "/api/v1/sessions",
            json={"title": "Memory diagnostic session"},
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = session_response.json()["id"]

        from core.state import get_connection

        with get_connection() as connection:
            connection.execute(
                """
                insert into conversation_memory_summaries (session_id, content, last_message_id, updated_at, expires_at)
                values (?, ?, ?, ?, ?)
                """,
                (session_id, "memory summary", 1, "2026-06-17 10:00:00", "2026-07-17 10:00:00"),
            )
            connection.execute(
                "insert into conversation_messages (session_id, role, content) values (?, ?, ?)",
                (session_id, "user", "remember this preference"),
            )
            connection.commit()

        response = self.client.get(
            f"/api/v1/admin/traces/{session_id}/memory",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session_id"], session_id)
        self.assertTrue(payload["has_summary"])
        self.assertEqual(payload["summary_preview"], "memory summary")
        self.assertGreaterEqual(payload["recent_message_count"], 1)
        self.assertGreaterEqual(payload["prompt_message_count"], 1)

    def test_admin_can_get_trace_nodes(self) -> None:
        token = self._register_and_login("trace-node-admin", "admin")
        session_response = self.client.post(
            "/api/v1/sessions",
            json={"title": "Trace node session"},
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = session_response.json()["id"]

        from modules.rag.trace import RetriFlowTraceService

        trace_service = RetriFlowTraceService()
        with trace_service.start_root(session_id=session_id, task_id="task-node", name="chat") as root:
            with trace_service.span(name="retrieve", node_type="RETRIEVAL") as child:
                child.finish_success(output_summary="chunks")
            root.finish_success(output_summary="done")

        response = self.client.get(
            f"/api/v1/admin/traces/{session_id}/nodes",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["name"], "chat")
        self.assertEqual(payload["items"][1]["parent_id"], payload["items"][0]["id"])
        self.assertEqual(payload["items"][1]["node_type"], "RETRIEVAL")

    def test_admin_can_filter_trace_runs_by_root_trace_fields(self) -> None:
        token = self._register_and_login("trace-filter-admin", "admin")
        first_session = self.client.post(
            "/api/v1/sessions",
            json={"title": "Trace filter success"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()["id"]
        second_session = self.client.post(
            "/api/v1/sessions",
            json={"title": "Trace filter error"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()["id"]

        from core.state import get_connection
        from modules.rag.trace import RetriFlowTraceService

        trace_service = RetriFlowTraceService()
        with trace_service.start_root(session_id=first_session, task_id="task-filter-ok", name="chat") as root:
            root.finish_success(output_summary="ok")
        with trace_service.start_root(session_id=second_session, task_id="task-filter-fail", name="chat") as root:
            root.finish_error("failed")

        with get_connection() as connection:
            success_trace = connection.execute(
                """
                select id, started_at
                from rag_trace_nodes
                where session_id = ? and task_id = ? and parent_id = ''
                """,
                (first_session, "task-filter-ok"),
            ).fetchone()
            error_trace = connection.execute(
                """
                select id, started_at
                from rag_trace_nodes
                where session_id = ? and task_id = ? and parent_id = ''
                """,
                (second_session, "task-filter-fail"),
            ).fetchone()

        by_task = self.client.get(
            "/api/v1/admin/traces?task_id=task-filter-ok",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(by_task.status_code, 200)
        self.assertEqual([item["id"] for item in by_task.json()["items"]], [first_session])
        self.assertEqual(by_task.json()["items"][0]["status"], "success")

        by_status = self.client.get(
            "/api/v1/admin/traces?status=error",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(by_status.status_code, 200)
        self.assertEqual([item["id"] for item in by_status.json()["items"]], [second_session])

        by_trace = self.client.get(
            f"/api/v1/admin/traces?trace_id={success_trace['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(by_trace.status_code, 200)
        self.assertEqual([item["id"] for item in by_trace.json()["items"]], [first_session])

        invalid_trace = self.client.get(
            "/api/v1/admin/traces?trace_id=trace-abc",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(invalid_trace.status_code, 422)

        by_time = self.client.get(
            "/api/v1/admin/traces",
            params={"started_from": success_trace["started_at"], "started_to": error_trace["started_at"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(by_time.status_code, 200)
        self.assertEqual(by_time.json()["total"], 2)

    def test_admin_can_list_model_health_snapshots(self) -> None:
        token = self._register_and_login("model-health-admin", "admin")

        from infra.llm.health import get_model_health_service

        get_model_health_service().record_failure(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
            error="timeout",
        )

        response = self.client.get(
            "/api/v1/admin/model-health",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["capability"], "chat")
        self.assertEqual(item["provider_name"], "bailian")
        self.assertEqual(item["model"], "qwen3-max")
        self.assertEqual(item["state"], "healthy")
        self.assertEqual(item["failure_count"], 1)
        self.assertEqual(item["last_error"], "timeout")

    def test_admin_model_health_survives_memory_reset(self) -> None:
        token = self._register_and_login("model-health-persist-admin", "admin")

        from infra.llm.health import get_model_health_service

        health_service = get_model_health_service()
        health_service.record_failure(
            capability="chat",
            provider_name="bailian",
            model="qwen3-max",
            error="timeout",
        )
        health_service.reset()

        response = self.client.get(
            "/api/v1/admin/model-health",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["provider_name"], "bailian")
        self.assertEqual(payload["items"][0]["failure_count"], 1)
        self.assertEqual(payload["items"][0]["last_error"], "timeout")

    def test_admin_can_probe_model_health(self) -> None:
        token = self._register_and_login("model-health-probe-admin", "admin")

        from infra.llm.health import ModelHealthSnapshot

        with patch(
            "modules.admin.service.RetriFlowLLMService.probe_model_health",
            return_value=ModelHealthSnapshot(
                capability="chat",
                provider_name="bailian",
                model="qwen3-max",
                state="healthy",
                success_count=1,
                last_success_duration_ms=12,
            ),
        ):
            response = self.client.post(
                "/api/v1/admin/model-health/probe",
                json={"capability": "chat", "provider_name": "bailian", "model": "qwen3-max"},
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider_name"], "bailian")
        self.assertEqual(payload["model"], "qwen3-max")
        self.assertEqual(payload["success_count"], 1)
        self.assertEqual(payload["last_success_duration_ms"], 12)

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

    def test_admin_can_manage_welcome_sample_questions(self) -> None:
        token = self._register_and_login("sample-admin", "admin")

        create_response = self.client.post(
            "/api/v1/admin/sample-questions",
            json={
                "title": "系统交互",
                "description": "关于助手",
                "question": "询问助手是做什么的、是谁、能做什么等",
                "sort_order": 10,
                "enabled": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["title"], "系统交互")
        self.assertEqual(created["question"], "询问助手是做什么的、是谁、能做什么等")

        list_response = self.client.get(
            "/api/v1/admin/sample-questions",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(item["id"] == created["id"] for item in list_response.json()["items"]))

        update_response = self.client.patch(
            f"/api/v1/admin/sample-questions/{created['id']}",
            json={"description": "关于助手能力", "enabled": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["description"], "关于助手能力")
        self.assertFalse(update_response.json()["enabled"])

        delete_response = self.client.delete(
            f"/api/v1/admin/sample-questions/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(delete_response.status_code, 204)

    def test_admin_sample_question_rejects_duplicate_question(self) -> None:
        token = self._register_and_login("sample-duplicate-admin", "admin")
        payload = {
            "title": "系统交互",
            "description": "关于助手",
            "question": "询问助手是做什么的、是谁、能做什么等",
            "sort_order": 10,
            "enabled": True,
        }

        first_response = self.client.post(
            "/api/v1/admin/sample-questions",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(first_response.status_code, 201)

        duplicate_response = self.client.post(
            "/api/v1/admin/sample-questions",
            json={**payload, "title": "重复问题"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertIn("示例问题已存在", duplicate_response.json()["detail"])

        second_response = self.client.post(
            "/api/v1/admin/sample-questions",
            json={**payload, "title": "业务系统", "question": "数据权限、访问控制、安全审计等相关说明"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(second_response.status_code, 201)

        update_duplicate_response = self.client.patch(
            f"/api/v1/admin/sample-questions/{second_response.json()['id']}",
            json={"question": payload["question"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(update_duplicate_response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
