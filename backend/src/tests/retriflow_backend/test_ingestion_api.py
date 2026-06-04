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

    def test_ingestion_task_exposes_default_pipeline_node_logs(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
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

    def test_upload_ingestion_task_includes_parse_and_extract_nodes(self) -> None:
        from domain.document_parser import ParsedUploadDocumentResult
        from domain.ingestion import IngestionPipelineNodeResult
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

        with patch("domain.knowledge.RetriFlowDocumentParserService.parse_upload", return_value=parsed_result):
            upload_response = self.client.post(
                "/api/v1/knowledge-bases/kb-demo-1/documents/upload",
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
