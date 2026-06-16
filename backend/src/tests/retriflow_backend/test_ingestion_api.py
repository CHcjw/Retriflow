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


class RetriFlowIngestionApiTests(unittest.TestCase):
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
        from main import create_app

        self.client = TestClient(create_app())
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.client.headers.update({"Authorization": f"Bearer {login_response.json()['access_token']}"})

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

    def _create_knowledge_base(self) -> str:
        response = self.client.post("/api/v1/knowledge-bases", json={"name": "Ingestion API KB"})
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_ingestion_task_exposes_default_pipeline_node_logs(self) -> None:
        knowledge_base_id = self._create_knowledge_base()
        create_response = self.client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            json={
                "title": "RetriFlow workflow",
                "source_type": "manual",
                "content": "RetriFlow normalizes text, chunks text, and indexes chunks for retrieval.",
            },
        )
        self.assertEqual(create_response.status_code, 201)
        document_id = create_response.json()["id"]

        tasks_response = self.client.get("/api/v1/ingestion/tasks")
        self.assertEqual(tasks_response.status_code, 200)
        task = next(item for item in tasks_response.json()["items"] if item["document_id"] == document_id)

        nodes_response = self.client.get(f"/api/v1/ingestion/tasks/{task['id']}/nodes")
        self.assertEqual(nodes_response.status_code, 200)
        payload = nodes_response.json()
        self.assertEqual([item["node_type"] for item in payload["items"]], ["normalize", "segment", "chunk", "index"])
        self.assertTrue(all(item["success"] for item in payload["items"]))
        self.assertIn("segments", payload["items"][1]["message"])

    def test_admin_can_list_default_ingestion_pipeline(self) -> None:
        response = self.client.get("/api/v1/ingestion/pipelines")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        names = [item["name"] for item in payload["items"]]
        self.assertIn("retriflow-ingestion-pipeline", names)
        default_pipeline = next(item for item in payload["items"] if item["name"] == "retriflow-ingestion-pipeline")
        self.assertGreaterEqual(default_pipeline["node_count"], 5)
        self.assertTrue(default_pipeline["nodes"])

    def test_admin_can_create_ingestion_pipeline(self) -> None:
        response = self.client.post(
            "/api/v1/ingestion/pipelines",
            json={
                "name": "retriflow-custom-pipeline",
                "description": "Custom RetriFlow ingestion pipeline",
                "owner": "admin",
                "nodes": [
                    {
                        "node_id": "parse",
                        "node_type": "parser",
                        "next_node_id": "index",
                        "condition": "",
                        "config": {"parser": "apache-tika"},
                    },
                    {
                        "node_id": "index",
                        "node_type": "indexer",
                        "next_node_id": "",
                        "condition": "",
                        "config": {"vector_store": "pgvector"},
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["name"], "retriflow-custom-pipeline")
        self.assertEqual(payload["node_count"], 2)

        list_response = self.client.get("/api/v1/ingestion/pipelines")
        self.assertEqual(list_response.status_code, 200)
        self.assertIn("retriflow-custom-pipeline", [item["name"] for item in list_response.json()["items"]])

    def test_pipeline_node_ids_must_be_unique(self) -> None:
        response = self.client.post(
            "/api/v1/ingestion/pipelines",
            json={
                "name": "retriflow-invalid-pipeline",
                "description": "",
                "nodes": [
                    {"node_id": "parse", "node_type": "parser", "next_node_id": "", "condition": "", "config": {}},
                    {"node_id": "parse", "node_type": "indexer", "next_node_id": "", "condition": "", "config": {}},
                ],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_upload_ingestion_task_includes_parse_and_extract_nodes(self) -> None:
        from infra.document_parser import ParsedUploadDocumentResult
        from modules.ingestion import IngestionPipelineNodeResult
        from schemas.document_structure import ParagraphBlock, StructuredDocument

        parsed_result = ParsedUploadDocumentResult(
            title="RetriFlow Upload Pipeline",
            structured_document=StructuredDocument(
                file_name="upload.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                title="RetriFlow Upload Pipeline",
                metadata={},
                blocks=[
                    ParagraphBlock(
                        block_index=0,
                        page_number=1,
                        text="RetriFlow upload structured parsing.",
                    )
                ],
                text_content="RetriFlow upload structured parsing.",
            ),
            ingestion_text="RetriFlow upload structured parsing.",
            node_results=[
                IngestionPipelineNodeResult("parse", 1, True, "Parsed document via Tika-compatible pipeline.", 1),
                IngestionPipelineNodeResult("extract", 2, True, "Extracted structured blocks.", 1),
                IngestionPipelineNodeResult("clean", 3, True, "Normalized structured fields.", 1),
                IngestionPipelineNodeResult("validate", 4, True, "Validated structured schema.", 1),
            ],
        )

        with patch("modules.knowledge.service.RetriFlowDocumentParserService.parse_upload", return_value=parsed_result):
            knowledge_base_id = self._create_knowledge_base()
            upload_response = self.client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/upload",
                files={
                    "file": (
                        "upload.docx",
                        b"fake-docx-binary",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )

        self.assertEqual(upload_response.status_code, 201)
        document_id = upload_response.json()["id"]

        tasks_response = self.client.get("/api/v1/ingestion/tasks")
        self.assertEqual(tasks_response.status_code, 200)
        task = next(item for item in tasks_response.json()["items"] if item["document_id"] == document_id)

        nodes_response = self.client.get(f"/api/v1/ingestion/tasks/{task['id']}/nodes")
        self.assertEqual(nodes_response.status_code, 200)
        node_types = [item["node_type"] for item in nodes_response.json()["items"]]
        self.assertEqual(node_types, ["parse", "extract", "clean", "validate", "normalize", "segment", "chunk", "index"])


if __name__ == "__main__":
    unittest.main()
