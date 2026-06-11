import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowVectorStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)

        from core.config import get_settings
        from core.state import initialize_database

        get_settings.cache_clear()
        initialize_database()

    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_resolve_vector_store_returns_postgres_store_when_dsn_is_configured(self) -> None:
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = "postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow"

        from core.config import get_settings
        from domain.vector_store import PostgresRetriFlowVectorStore, resolve_vector_store

        get_settings.cache_clear()
        store = resolve_vector_store()

        self.assertIsInstance(store, PostgresRetriFlowVectorStore)

    def test_knowledge_service_upserts_chunks_into_vector_store(self) -> None:
        from domain.knowledge import RetriFlowKnowledgeService
        from schemas.knowledge import KnowledgeDocumentCreateRequest

        captured_records: list[object] = []

        class FakeVectorStore:
            def upsert_chunk_records(self, records) -> None:
                captured_records.extend(records)

            def similarity_search(self, query: str, k: int = 4):
                return []

        with patch("domain.knowledge.resolve_vector_store", return_value=FakeVectorStore()):
            RetriFlowKnowledgeService().create_document(
                "kb-demo-1",
                KnowledgeDocumentCreateRequest(
                    title="Vector sync notes",
                    source_type="manual",
                    content="RetriFlow should persist chunk vectors after ingestion.",
                ),
            )

        self.assertGreaterEqual(len(captured_records), 1)
        first_record = captured_records[0]
        self.assertEqual(first_record.document_title, "Vector sync notes")
        self.assertEqual(first_record.knowledge_base_id, "kb-demo-1")
        self.assertIn("RetriFlow should persist chunk vectors", first_record.content)

    def test_knowledge_service_reindex_replaces_document_vectors(self) -> None:
        from domain.knowledge import RetriFlowKnowledgeService
        from schemas.knowledge import KnowledgeDocumentCreateRequest, KnowledgeDocumentReindexRequest

        operation_log: list[tuple[str, object]] = []

        class FakeVectorStore:
            def upsert_chunk_records(self, records) -> None:
                operation_log.append(("upsert", [record.chunk_id for record in records]))

            def delete_document_records(self, document_id: int) -> None:
                operation_log.append(("delete", document_id))

            def similarity_search(self, query: str, k: int = 4):
                return []

        with patch("domain.knowledge.resolve_vector_store", return_value=FakeVectorStore()):
            service = RetriFlowKnowledgeService()
            created = service.create_document(
                "kb-demo-1",
                KnowledgeDocumentCreateRequest(
                    title="Vector reindex target",
                    source_type="manual",
                    content=(
                        "RetriFlow should remove stale vectors before writing the fresh chunk embeddings. "
                        "This keeps hybrid retrieval aligned with the latest chunk strategy."
                    ),
                ),
            )
            operation_log.clear()
            service.reindex_document(
                "kb-demo-1",
                created.id,
                KnowledgeDocumentReindexRequest(
                    chunk_strategy="fixed",
                    chunk_size=48,
                    chunk_overlap=8,
                ),
            )

        self.assertGreaterEqual(len(operation_log), 2)
        self.assertEqual(operation_log[0], ("delete", created.id))
        self.assertEqual(operation_log[1][0], "upsert")
        self.assertGreaterEqual(len(operation_log[1][1]), 1)


if __name__ == "__main__":
    unittest.main()
