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


class RetriFlowChatMcpApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"
        os.environ["RETRIFLOW_WORKFLOW_ADAPTER"] = "langgraph"

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
        os.environ.pop("RETRIFLOW_WORKFLOW_ADAPTER", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_chat_message_supports_multiple_mcp_calls(self) -> None:
        response = self.client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "session-demo-1",
                "message": "请同时告诉我北京今天天气和华东本月销售额情况",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "mcp_only")
        self.assertEqual(payload["workflow"]["mcp_tool_count"], 2)
        self.assertEqual(len(payload["mcp_calls"]), 2)
        tool_ids = [item["tool_id"] for item in payload["mcp_calls"]]
        self.assertIn("weather_query", tool_ids)
        self.assertIn("sales_query", tool_ids)

    def test_chat_message_returns_mcp_error_items_without_raising_500(self) -> None:
        from domain.mcp.models import McpExecutionResult, McpRouteDecision, McpToolCallResult

        fake_result = McpExecutionResult(
            route=McpRouteDecision(
                mode="mcp",
                tool_ids=["weather_query"],
                confidence=0.91,
                reason="matched weather intent",
            ),
            calls=[
                McpToolCallResult(
                    tool_id="weather_query",
                    arguments={"city": "北京", "query_type": "current"},
                    content="Tool execution failed: remote weather service timeout",
                    is_error=True,
                )
            ],
        )

        with patch(
            "domain.workflow_adapter.RetriFlowMcpService.execute_question",
            return_value=fake_result,
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={
                    "session_id": "session-demo-1",
                    "message": "北京今天天气怎么样？",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "mcp_only")
        self.assertEqual(payload["workflow"]["mcp_tool_count"], 1)
        self.assertEqual(len(payload["mcp_calls"]), 1)
        self.assertTrue(payload["mcp_calls"][0]["is_error"])
        self.assertIn("timeout", payload["mcp_calls"][0]["content"])


if __name__ == "__main__":
    unittest.main()
