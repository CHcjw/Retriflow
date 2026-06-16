import os
import shutil
import sys
import tempfile
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowKnowledgeDocumentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"
        os.environ["RETRIFLOW_SEED_DEMO_CONTENT"] = "true"

        from core.config import get_settings

        get_settings.cache_clear()
        from main import create_app

        self.client = TestClient(create_app())
        self.admin_token = self._login("admin", "admin")
        self.user_token = self._register_and_login("knowledge-user")

    def tearDown(self) -> None:
        self.client.close()
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)
        os.environ.pop("RETRIFLOW_SEED_DEMO_CONTENT", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _login(self, username: str, password: str) -> str:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _register_and_login(self, username: str) -> str:
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "Password123", "role": "user"},
        )
        self.assertEqual(register_response.status_code, 201)
        return self._login(username, "Password123")

    def test_list_documents_returns_seed_documents_for_demo_knowledge_base(self) -> None:
        response = self.client.get(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["knowledge_base_id"], "kb-demo-1")
        self.assertIn("title", payload["items"][0])
        self.assertIn("status", payload["items"][0])

    def test_create_document_persists_item_and_updates_knowledge_base_count(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
            json={
                "title": "RetriFlow rollout notes",
                "source_type": "manual",
                "content": "RetriFlow needs document ingestion before retrieval.",
            },
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["title"], "RetriFlow rollout notes")
        self.assertEqual(created["knowledge_base_id"], "kb-demo-1")
        self.assertEqual(created["status"], "indexed")

        list_response = self.client.get(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
        )
        items = list_response.json()["items"]
        self.assertTrue(any(item["title"] == "RetriFlow rollout notes" for item in items))

        knowledge_response = self.client.get("/api/v1/knowledge-bases", headers=self._auth_headers(self.admin_token))
        knowledge_items = knowledge_response.json()["items"]
        demo_item = next(item for item in knowledge_items if item["id"] == "kb-demo-1")
        self.assertEqual(demo_item["document_count"], len(items))

    def test_create_document_returns_vector_index_status(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
            json={
                "title": "RetriFlow vector status notes",
                "source_type": "manual",
                "content": "RetriFlow should expose whether vector indexing succeeded after ingestion.",
            },
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["vector_index_status"], "indexed")
        self.assertGreaterEqual(created["vector_chunk_count"], 1)
        self.assertTrue(created["vector_indexed_at"])

        list_response = self.client.get(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(list_response.status_code, 200)
        matching = next(item for item in list_response.json()["items"] if item["id"] == created["id"])
        self.assertEqual(matching["vector_index_status"], "indexed")
        self.assertGreaterEqual(matching["vector_chunk_count"], 1)

    def test_create_document_generates_chunks_and_ingestion_task(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
            json={
                "title": "RetriFlow architecture",
                "source_type": "manual",
                "content": (
                    "RetriFlow uses FastAPI for backend APIs. "
                    "RetriFlow uses Vue for frontend delivery. "
                    "RetriFlow will adopt LangGraph for orchestration."
                ),
            },
        )
        self.assertEqual(create_response.status_code, 201)
        document_id = create_response.json()["id"]

        chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(chunks_response.status_code, 200)
        chunks_payload = chunks_response.json()
        self.assertGreaterEqual(len(chunks_payload["items"]), 1)
        self.assertEqual(chunks_payload["items"][0]["document_id"], document_id)
        self.assertIn("content", chunks_payload["items"][0])

        tasks_response = self.client.get("/api/v1/ingestion/tasks", headers=self._auth_headers(self.admin_token))
        self.assertEqual(tasks_response.status_code, 200)
        tasks_payload = tasks_response.json()
        matching_tasks = [item for item in tasks_payload["items"] if item["document_id"] == document_id]
        self.assertEqual(len(matching_tasks), 1)
        self.assertEqual(matching_tasks[0]["status"], "completed")

        task_id = matching_tasks[0]["id"]
        nodes_response = self.client.get(
            f"/api/v1/ingestion/tasks/{task_id}/nodes",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(nodes_response.status_code, 200)
        node_types = [item["node_type"] for item in nodes_response.json()["items"]]
        self.assertEqual(node_types, ["normalize", "segment", "chunk", "index"])

    def test_create_document_can_persist_chunk_strategy_and_metadata(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
            json={
                "title": "RetriFlow contract notes",
                "source_type": "manual",
                "document_type": "contract",
                "chunk_strategy": "semantic_embedding",
                "content": (
                    "Clause 1 payment obligations.\n\n"
                    "Clause 2 liability allocation.\n\n"
                    "Clause 3 dispute resolution."
                ),
            },
        )
        self.assertEqual(create_response.status_code, 201)
        document_id = create_response.json()["id"]

        chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(chunks_response.status_code, 200)
        chunk = chunks_response.json()["items"][0]
        self.assertEqual(chunk["strategy"], "semantic_embedding")
        self.assertEqual(chunk["document_type"], "contract")
        self.assertIn("semantic_group", chunk["metadata"])

    def test_create_document_accepts_custom_chunk_size_and_overlap(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
            json={
                "title": "RetriFlow fixed chunk notes",
                "source_type": "manual",
                "document_type": "manual",
                "chunk_strategy": "fixed",
                "chunk_size": 80,
                "chunk_overlap": 16,
                "content": (
                    "RetriFlow fixed chunking should produce predictable chunk boundaries for testing. "
                    "RetriFlow fixed chunking should produce predictable chunk boundaries for testing."
                ),
            },
        )
        self.assertEqual(create_response.status_code, 201)
        document_id = create_response.json()["id"]

        chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(chunks_response.status_code, 200)
        chunk = chunks_response.json()["items"][0]
        self.assertEqual(chunk["strategy"], "fixed")
        self.assertEqual(chunk["metadata"]["chunk_count"], len(chunks_response.json()["items"]))

    def test_create_document_accepts_recursive_separators(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        captured: dict[str, object] = {}

        def fake_build_pipeline(
            strategy: str,
            chunk_size: int,
            chunk_overlap: int,
            recursive_separators: list[str] | None = None,
        ) -> RetriFlowIngestionPipeline:
            captured["strategy"] = strategy
            captured["chunk_size"] = chunk_size
            captured["chunk_overlap"] = chunk_overlap
            captured["recursive_separators"] = recursive_separators
            return RetriFlowIngestionPipeline(
                strategy=strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                recursive_separators=recursive_separators,
            )

        with patch("modules.knowledge.service.RetriFlowKnowledgeService._build_ingestion_pipeline", side_effect=fake_build_pipeline):
            create_response = self.client.post(
                "/api/v1/knowledge-bases/kb-demo-1/documents",
                headers=self._auth_headers(self.admin_token),
                json={
                    "title": "RetriFlow recursive separator notes",
                    "source_type": "manual",
                    "document_type": "manual",
                    "chunk_strategy": "recursive",
                    "chunk_size": 12,
                    "chunk_overlap": 0,
                    "recursive_separators": ["###", " "],
                    "content": "alpha###beta###gamma",
                },
            )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(captured["strategy"], "recursive")
        self.assertEqual(captured["recursive_separators"], ["###", " "])

    def test_create_document_normalizes_blank_lines_and_creates_multiple_chunks(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
            json={
                "title": "RetriFlow chunking details",
                "source_type": "manual",
                "content": (
                    "First paragraph introduces RetriFlow.\n\n"
                    "Second paragraph explains ingestion and chunk overlap.\n\n"
                    "Third paragraph covers retrieval ranking and source fusion."
                ),
            },
        )
        self.assertEqual(create_response.status_code, 201)
        document_id = create_response.json()["id"]

        chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(chunks_response.status_code, 200)
        chunks = chunks_response.json()["items"]
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk["content"].strip() for chunk in chunks))

    def test_upload_text_file_creates_document_chunks_and_ingestion_task(self) -> None:
        upload_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents/upload",
            headers=self._auth_headers(self.admin_token),
            files={
                "file": ("retriflow.txt", b"RetriFlow upload ingestion should create chunks from file content.", "text/plain")
            },
        )
        self.assertEqual(upload_response.status_code, 201)
        created = upload_response.json()
        self.assertEqual(created["knowledge_base_id"], "kb-demo-1")
        self.assertEqual(created["source_type"], "local")

        chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{created['id']}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(chunks_response.status_code, 200)
        self.assertGreaterEqual(len(chunks_response.json()["items"]), 1)

    def test_upload_docx_uses_structured_parsing_pipeline(self) -> None:
        from infra.document_parser import ParsedUploadDocumentResult
        from modules.ingestion import IngestionPipelineNodeResult
        from schemas.document_structure import ParagraphBlock, StructuredDocument, TableBlock, TableCell, TableRow

        parsed_result = ParsedUploadDocumentResult(
            title="RetriFlow Parsed Spec",
            structured_document=StructuredDocument(
                file_name="retriflow-spec.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                title="RetriFlow Parsed Spec",
                metadata={"dc:title": "RetriFlow Parsed Spec"},
                blocks=[
                    ParagraphBlock(
                        block_index=0,
                        page_number=1,
                        text="RetriFlow parsed a structured upload.",
                    ),
                    TableBlock(
                        block_index=1,
                        page_number=1,
                        headers=["Field", "Value"],
                        rows=[
                            TableRow(
                                row_index=0,
                                cells=[
                                    TableCell(row_index=0, column_index=0, text="Owner"),
                                    TableCell(row_index=0, column_index=1, text="RetriFlow"),
                                ],
                            )
                        ],
                        row_count=1,
                        column_count=2,
                    ),
                ],
                text_content="RetriFlow parsed a structured upload.",
            ),
            ingestion_text="RetriFlow parsed a structured upload.",
            node_results=[
                IngestionPipelineNodeResult("parse", 1, True, "Parsed document via Tika-compatible pipeline.", 1),
                IngestionPipelineNodeResult("extract", 2, True, "Extracted structured blocks.", 1),
                IngestionPipelineNodeResult("clean", 3, True, "Normalized structured fields.", 1),
                IngestionPipelineNodeResult("validate", 4, True, "Validated structured schema.", 1),
            ],
        )

        with patch("modules.knowledge.service.RetriFlowDocumentParserService.parse_upload", return_value=parsed_result):
            upload_response = self.client.post(
                "/api/v1/knowledge-bases/kb-demo-1/documents/upload",
                headers=self._auth_headers(self.admin_token),
                files={
                    "file": (
                        "retriflow-spec.docx",
                        b"fake-docx-binary",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )

        self.assertEqual(upload_response.status_code, 201)
        created = upload_response.json()
        self.assertEqual(created["title"], "RetriFlow Parsed Spec")
        self.assertEqual(created["source_type"], "local")

        chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{created['id']}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(chunks_response.status_code, 200)
        self.assertGreaterEqual(len(chunks_response.json()["items"]), 1)

        blocks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{created['id']}/structured-blocks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(blocks_response.status_code, 200)
        block_items = blocks_response.json()["items"]
        self.assertEqual(block_items[0]["block_type"], "paragraph")
        self.assertEqual(block_items[0]["text"], "RetriFlow parsed a structured upload.")
        self.assertEqual(block_items[1]["block_type"], "table")
        self.assertEqual(block_items[1]["headers"], ["Field", "Value"])
        self.assertEqual(block_items[1]["rows"][0]["cells"][1]["text"], "RetriFlow")

        chunk_item = chunks_response.json()["items"][0]
        self.assertIn("metadata", chunk_item)
        self.assertIn("block_type", chunk_item["metadata"])
        self.assertIn("page_number", chunk_item["metadata"])

    def test_upload_document_accepts_chunk_controls(self) -> None:
        from infra.document_parser import ParsedUploadDocumentResult
        from modules.ingestion import IngestionPipelineNodeResult
        from schemas.document_structure import ParagraphBlock, StructuredDocument

        parsed_result = ParsedUploadDocumentResult(
            title="RetriFlow Upload Controls",
            structured_document=StructuredDocument(
                file_name="upload.txt",
                content_type="text/plain",
                title="RetriFlow Upload Controls",
                metadata={},
                blocks=[
                    ParagraphBlock(
                        block_index=0,
                        page_number=1,
                        text="RetriFlow upload chunk controls should reach the ingestion pipeline.",
                    )
                ],
                text_content="RetriFlow upload chunk controls should reach the ingestion pipeline.",
            ),
            ingestion_text="RetriFlow upload chunk controls should reach the ingestion pipeline.",
            node_results=[
                IngestionPipelineNodeResult("parse", 1, True, "Parsed document via Tika-compatible pipeline.", 1),
                IngestionPipelineNodeResult("extract", 2, True, "Extracted structured blocks.", 1),
                IngestionPipelineNodeResult("clean", 3, True, "Normalized structured fields.", 1),
                IngestionPipelineNodeResult("validate", 4, True, "Validated structured schema.", 1),
            ],
        )

        with patch("modules.knowledge.service.RetriFlowDocumentParserService.parse_upload", return_value=parsed_result):
            upload_response = self.client.post(
                "/api/v1/knowledge-bases/kb-demo-1/documents/upload",
                headers=self._auth_headers(self.admin_token),
                files={"file": ("upload.txt", b"fake-upload", "text/plain")},
                data={
                    "document_type": "faq",
                    "chunk_strategy": "fixed",
                    "chunk_size": "80",
                    "chunk_overlap": "16",
                },
            )

        self.assertEqual(upload_response.status_code, 201)
        document_id = upload_response.json()["id"]
        chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(chunks_response.status_code, 200)
        chunk = chunks_response.json()["items"][0]
        self.assertEqual(chunk["strategy"], "fixed")
        self.assertEqual(chunk["document_type"], "faq")

    def test_upload_document_accepts_recursive_separators(self) -> None:
        from infra.document_parser import ParsedUploadDocumentResult
        from modules.ingestion import IngestionPipelineNodeResult
        from modules.ingestion import RetriFlowIngestionPipeline
        from schemas.document_structure import ParagraphBlock, StructuredDocument

        parsed_result = ParsedUploadDocumentResult(
            title="RetriFlow Upload Recursive Separators",
            structured_document=StructuredDocument(
                file_name="upload.txt",
                content_type="text/plain",
                title="RetriFlow Upload Recursive Separators",
                metadata={},
                blocks=[
                    ParagraphBlock(
                        block_index=0,
                        page_number=1,
                        text="alpha###beta###gamma",
                    )
                ],
                text_content="alpha###beta###gamma",
            ),
            ingestion_text="alpha###beta###gamma",
            node_results=[
                IngestionPipelineNodeResult("parse", 1, True, "Parsed document via Tika-compatible pipeline.", 1),
                IngestionPipelineNodeResult("extract", 2, True, "Extracted structured blocks.", 1),
                IngestionPipelineNodeResult("clean", 3, True, "Normalized structured fields.", 1),
                IngestionPipelineNodeResult("validate", 4, True, "Validated structured schema.", 1),
            ],
        )

        captured: dict[str, object] = {}

        def fake_build_pipeline(
            strategy: str,
            chunk_size: int,
            chunk_overlap: int,
            recursive_separators: list[str] | None = None,
        ) -> RetriFlowIngestionPipeline:
            captured["strategy"] = strategy
            captured["chunk_size"] = chunk_size
            captured["chunk_overlap"] = chunk_overlap
            captured["recursive_separators"] = recursive_separators
            return RetriFlowIngestionPipeline(
                strategy=strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                recursive_separators=recursive_separators,
            )

        with patch("modules.knowledge.service.RetriFlowDocumentParserService.parse_upload", return_value=parsed_result):
            with patch("modules.knowledge.service.RetriFlowKnowledgeService._build_ingestion_pipeline", side_effect=fake_build_pipeline):
                upload_response = self.client.post(
                    "/api/v1/knowledge-bases/kb-demo-1/documents/upload",
                    headers=self._auth_headers(self.admin_token),
                    files={"file": ("upload.txt", b"fake-upload", "text/plain")},
                    data={
                        "document_type": "manual",
                        "chunk_strategy": "recursive",
                        "chunk_size": "12",
                        "chunk_overlap": "0",
                        "recursive_separators_text": "###\n ",
                    },
                )

        self.assertEqual(upload_response.status_code, 201)
        self.assertEqual(captured["strategy"], "recursive")
        self.assertEqual(captured["recursive_separators"], ["###", " "])

    def test_upload_uses_tika_detected_mime_when_form_header_is_generic(self) -> None:
        from infra.document_parser import ParsedUploadDocumentResult
        from modules.ingestion import IngestionPipelineNodeResult
        from schemas.document_structure import ParagraphBlock, StructuredDocument

        parsed_result = ParsedUploadDocumentResult(
            title="Detected PDF",
            structured_document=StructuredDocument(
                file_name="retriflow.pdf",
                content_type="application/pdf",
                title="Detected PDF",
                metadata={"Content-Type": "application/pdf"},
                blocks=[
                    ParagraphBlock(
                        block_index=0,
                        page_number=1,
                        text="RetriFlow detected the actual MIME type.",
                    )
                ],
                text_content="RetriFlow detected the actual MIME type.",
            ),
            ingestion_text="RetriFlow detected the actual MIME type.",
            node_results=[
                IngestionPipelineNodeResult("parse", 1, True, "Parsed document via Tika-compatible pipeline.", 1),
                IngestionPipelineNodeResult("extract", 2, True, "Extracted structured blocks.", 1),
                IngestionPipelineNodeResult("clean", 3, True, "Normalized structured fields.", 1),
                IngestionPipelineNodeResult("validate", 4, True, "Validated structured schema.", 1),
            ],
        )

        with patch("modules.knowledge.service.RetriFlowDocumentParserService.parse_upload", return_value=parsed_result) as parse_mock:
            upload_response = self.client.post(
                "/api/v1/knowledge-bases/kb-demo-1/documents/upload",
                headers=self._auth_headers(self.admin_token),
                files={
                    "file": (
                        "retriflow.pdf",
                        b"%PDF-1.4 fake-binary",
                        "application/octet-stream",
                    )
                },
            )

        self.assertEqual(upload_response.status_code, 201)
        self.assertEqual(parse_mock.call_args.args[2], "application/octet-stream")

    def test_reindex_document_rebuilds_chunks_with_new_strategy(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
            json={
                "title": "RetriFlow reindex target",
                "source_type": "manual",
                "document_type": "manual",
                "chunk_strategy": "recursive",
                "chunk_size": 200,
                "chunk_overlap": 20,
                "content": (
                    "Alpha section introduces RetriFlow retrieval.\n\n"
                    "Beta section covers hybrid recall and RRF fusion.\n\n"
                    "Gamma section explains rerank and answer generation.\n\n"
                    "Delta section captures citations and source metadata."
                ),
            },
        )
        self.assertEqual(create_response.status_code, 201)
        document_id = create_response.json()["id"]

        initial_chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(initial_chunks_response.status_code, 200)
        initial_chunks = initial_chunks_response.json()["items"]
        self.assertGreaterEqual(len(initial_chunks), 1)
        initial_chunk_ids = [chunk["id"] for chunk in initial_chunks]

        reindex_response = self.client.post(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/reindex",
            headers=self._auth_headers(self.admin_token),
            json={
                "document_type": "manual",
                "chunk_strategy": "fixed",
                "chunk_size": 60,
                "chunk_overlap": 12,
            },
        )
        self.assertEqual(reindex_response.status_code, 200)
        reindexed = reindex_response.json()
        self.assertEqual(reindexed["id"], document_id)
        self.assertEqual(reindexed["vector_index_status"], "indexed")
        self.assertGreaterEqual(reindexed["vector_chunk_count"], 1)
        self.assertTrue(reindexed["vector_indexed_at"])

        chunks_response = self.client.get(
            f"/api/v1/knowledge-bases/kb-demo-1/documents/{document_id}/chunks",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(chunks_response.status_code, 200)
        chunks = chunks_response.json()["items"]
        self.assertGreaterEqual(len(chunks), 1)
        self.assertTrue(all(chunk["strategy"] == "fixed" for chunk in chunks))
        self.assertEqual([chunk["chunk_index"] for chunk in chunks], list(range(len(chunks))))
        self.assertNotEqual([chunk["id"] for chunk in chunks], initial_chunk_ids)
        self.assertTrue(all("start_index" in chunk["metadata"] for chunk in chunks))

        tasks_response = self.client.get("/api/v1/ingestion/tasks", headers=self._auth_headers(self.admin_token))
        self.assertEqual(tasks_response.status_code, 200)
        matching_tasks = [item for item in tasks_response.json()["items"] if item["document_id"] == document_id]
        self.assertEqual(len(matching_tasks), 2)

    def test_import_sample_knowledge_directory_creates_documents(self) -> None:
        sample_source = PROJECT_ROOT / "ragent" / "resources" / "docs" / "knowledge"
        sample_target = Path(self.temp_dir.name) / "sample_knowledge"
        shutil.copytree(sample_source, sample_target)
        os.environ["RETRIFLOW_SAMPLE_KNOWLEDGE_DIR"] = str(sample_target)

        before_response = self.client.get(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(before_response.status_code, 200)
        before_count = len(before_response.json()["items"])

        from core.config import get_settings
        from modules.knowledge import RetriFlowKnowledgeService

        get_settings.cache_clear()
        service = RetriFlowKnowledgeService()
        imported = service.import_sample_directory("kb-demo-1")

        self.assertGreater(imported, 0)

        response = self.client.get(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertGreaterEqual(len(items), before_count + imported)

    def test_knowledge_write_endpoints_require_admin_role(self) -> None:
        create_response = self.client.post(
            "/api/v1/knowledge-bases/kb-demo-1/documents",
            headers=self._auth_headers(self.user_token),
            json={
                "title": "Forbidden document",
                "source_type": "manual",
                "content": "A non-admin user should not write knowledge data.",
            },
        )

        self.assertEqual(create_response.status_code, 403)

        ingestion_response = self.client.get("/api/v1/ingestion/tasks", headers=self._auth_headers(self.user_token))
        self.assertEqual(ingestion_response.status_code, 403)

    def test_knowledge_read_endpoints_require_auth(self) -> None:
        documents_response = self.client.get("/api/v1/knowledge-bases/kb-demo-1/documents")
        chunks_response = self.client.get("/api/v1/knowledge-bases/kb-demo-1/documents/1/chunks")

        self.assertEqual(documents_response.status_code, 401)
        self.assertEqual(chunks_response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
