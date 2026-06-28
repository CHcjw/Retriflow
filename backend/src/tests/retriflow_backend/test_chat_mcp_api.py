import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from urllib.parse import unquote_plus
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
        os.environ["RETRIFLOW_SEED_DEMO_CONTENT"] = "true"
        os.environ["RETRIFLOW_WORKFLOW_ADAPTER"] = "langgraph"
        os.environ["RETRIFLOW_MCP_REMOTE_ENABLED"] = "true"
        os.environ["RETRIFLOW_MCP_REMOTE_SERVERS_JSON"] = (
            '[{"name":"baidu-ai-search","url":"https://qianfan.baidubce.com/v2/ai_search/mcp"},'
            '{"name":"china-weather","command":"node","args":["backend/vendor/mcp-China-weather-server/build/index.js"]}]'
        )

        from modules.mcp.models import McpToolCallResult, McpToolDefinition

        def fake_list_tools(client_self):
            server_name = client_self.server_config.name
            if server_name == "baidu-ai-search":
                return [
                    McpToolDefinition(
                        tool_id="AIsearch",
                        description="搜索实时信息，支持使用大模型进行总结回复。",
                        parameter_schema={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "model": {"type": "string"},
                            },
                            "required": ["query"],
                        },
                        server_name=server_name,
                        transport="remote_http",
                    )
                ]
            if server_name == "china-weather":
                return [
                    McpToolDefinition(
                        tool_id="get-weather-forecast",
                        description="获取指定中国城市的实时天气和天气预报。",
                        parameter_schema={
                            "type": "object",
                            "properties": {
                                "cityName": {"type": "string"},
                                "date": {"type": "string"},
                                "forecastType": {"type": "string", "enum": ["current", "forecast"]},
                            },
                            "required": ["cityName"],
                        },
                        server_name=server_name,
                        transport="stdio",
                    )
                ]
            return []

        def fake_call_tool(client_self, tool_id, arguments):
            content = (
                "广州实时天气：多云，28°C，湿度70%。"
                if tool_id == "get-weather-forecast"
                else "RAG 通常由问题理解、检索、重排和生成回答组成。"
            )
            return McpToolCallResult(
                tool_id=tool_id,
                arguments=dict(arguments),
                content=content,
            )

        self.remote_list_patcher = patch("modules.mcp.registry.RetriFlowRemoteMcpClient.list_tools", new=fake_list_tools)
        self.remote_call_patcher = patch("modules.mcp.client.RetriFlowRemoteMcpClient.call_tool", new=fake_call_tool)
        self.remote_list_patcher.start()
        self.remote_call_patcher.start()

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
        os.environ.pop("RETRIFLOW_SEED_DEMO_CONTENT", None)
        os.environ.pop("RETRIFLOW_WORKFLOW_ADAPTER", None)
        os.environ.pop("RETRIFLOW_MCP_REMOTE_ENABLED", None)
        os.environ.pop("RETRIFLOW_MCP_REMOTE_SERVERS_JSON", None)
        self.remote_call_patcher.stop()
        self.remote_list_patcher.stop()
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
        self.assertIn("get-weather-forecast", tool_ids)
        self.assertIn("sales_query", tool_ids)

    def test_local_date_question_uses_local_answer_without_mcp(self) -> None:
        response = self.client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "session-demo-1",
                "message": "今天是几号？",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "local")
        self.assertEqual(payload["workflow"]["mcp_tool_count"], 0)
        self.assertEqual(payload["mcp_calls"], [])
        self.assertIn("今天是", payload["assistant_message"])

    def test_explicit_web_search_survives_query_rewrite_that_removes_search_words(self) -> None:
        with patch(
            "modules.rag.workflow_adapter.RetriFlowQueryRewriteService.rewrite",
            return_value=["怎么实现 rag"],
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={
                    "session_id": "session-demo-1",
                    "message": "上网搜索怎么实现rag",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "mcp_only")
        tool_ids = [item["tool_id"] for item in payload["mcp_calls"]]
        self.assertIn("AIsearch", tool_ids)

    def test_smart_search_prefers_search_mcp_over_builtin_sales_tool(self) -> None:
        response = self.client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "session-demo-1",
                "message": "所有地区销售额，以及销售占比分析",
                "smart_search": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "mcp_only")
        self.assertTrue(payload["workflow"]["smart_search"])
        self.assertEqual([item["tool_id"] for item in payload["mcp_calls"]], ["AIsearch"])

    def test_chat_message_returns_mcp_error_items_without_raising_500(self) -> None:
        from modules.mcp.models import McpExecutionResult, McpRouteDecision, McpToolCallResult

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
            "modules.rag.workflow_adapter.RetriFlowMcpService.execute_question",
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

    def test_weather_follow_up_uses_previous_city_and_weather_tool(self) -> None:
        first_response = self.client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "session-demo-1",
                "message": "北京今天天气怎么样？",
            },
        )
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["mcp_calls"][0]["tool_id"], "get-weather-forecast")

        follow_up_response = self.client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "session-demo-1",
                "message": "未来三天呢",
            },
        )

        self.assertEqual(follow_up_response.status_code, 200)
        payload = follow_up_response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "mcp_only")
        self.assertEqual(payload["mcp_calls"][0]["tool_id"], "get-weather-forecast")
        self.assertEqual(payload["mcp_calls"][0]["arguments"]["forecastType"], "forecast")
        self.assertIn("市", payload["mcp_calls"][0]["arguments"]["cityName"])
        self.assertEqual(payload["workflow"]["rewritten_queries"], ["北京未来三天天气怎么样？"])

    def test_mcp_intent_tree_node_routes_to_tool_call(self) -> None:
        from modules.admin import RetriFlowAdminService
        from schemas.admin import AdminIntentNodeCreateRequest

        parent = RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Revenue Domain",
                code="chat_mcp_revenue_domain",
                level="DOMAIN",
                node_type="MCP",
                description="revenue analytics domain",
                sort_order=1,
            )
        )
        RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Revenue Analytics",
                code="chat_mcp_revenue_analytics",
                level="CATEGORY",
                node_type="MCP",
                parent_id=parent.id,
                mcp_tool_id="sales_query",
                description="revenue analytics by region and period",
                rule_snippet="revenue analytics",
                sort_order=1,
            )
        )

        with patch(
            "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
            return_value={
                "intent": "knowledge_retrieval",
                "confidence": 0.95,
                "reason": "forced route test",
                "source": "rule",
                "clarification_question": "",
            },
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={
                    "session_id": "session-demo-1",
                    "message": "revenue analytics for 华东 this month",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"]["route_mode"], "mcp_only")
        self.assertEqual(payload["mcp_calls"][0]["tool_id"], "sales_query")
        self.assertEqual(payload["workflow"]["route_candidates"][0]["mcp_tool_id"], "sales_query")

    def test_mcp_intent_tree_node_passes_param_prompt_template_to_extractor(self) -> None:
        from modules.admin import RetriFlowAdminService
        from schemas.admin import AdminIntentNodeCreateRequest

        parent = RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Sales Tools",
                code="chat_mcp_param_sales",
                level="DOMAIN",
                node_type="MCP",
                description="sales revenue tools",
                sort_order=1,
            )
        )
        RetriFlowAdminService().create_intent_node(
            AdminIntentNodeCreateRequest(
                name="Sales Region Query",
                code="chat_mcp_param_sales_region",
                level="CATEGORY",
                node_type="MCP",
                parent_id=parent.id,
                mcp_tool_id="sales_query",
                description="sales revenue by region",
                rule_snippet="sales revenue",
                param_prompt_template="always prefer region from user query",
                sort_order=1,
            )
        )

        captured_templates: list[str] = []

        def fake_extract(self, *, question, tool_definition, param_prompt_template=""):
            captured_templates.append(param_prompt_template)
            return {"region": "华东", "period": "this_month"}

        with (
            patch(
                "modules.rag.workflow_adapter.RetriFlowIntentClassifier.classify",
                return_value={
                    "intent": "knowledge_retrieval",
                    "confidence": 0.95,
                    "reason": "forced route test",
                    "source": "rule",
                    "clarification_question": "",
                },
            ),
            patch(
                "modules.mcp.parameter_extractor.RetriFlowMcpParameterExtractor.extract",
                new=fake_extract,
            ),
        ):
            response = self.client.post(
                "/api/v1/chat/messages",
                json={
                    "session_id": "session-demo-1",
                    "message": "sales revenue for 华东 this month",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("always prefer region from user query", captured_templates)
        self.assertEqual(response.json()["mcp_calls"][0]["arguments"]["region"], "华东")


if __name__ == "__main__":
    unittest.main()
