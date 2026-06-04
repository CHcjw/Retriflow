import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowRetrievalEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)

        from core.config import get_settings
        from core.state import initialize_database
        from domain.knowledge import RetriFlowKnowledgeService
        from schemas.knowledge import KnowledgeDocumentCreateRequest

        get_settings.cache_clear()
        initialize_database()

        RetriFlowKnowledgeService().create_document(
            "kb-demo-1",
            KnowledgeDocumentCreateRequest(
                title="LangChain retrieval notes",
                source_type="manual",
                content=(
                    "RetriFlow uses LangChain retrievers to bridge hybrid recall and downstream RAG flows. "
                    "RetriFlow keeps metadata for chunk identifiers and source attribution."
                ),
            ),
        )

    def tearDown(self) -> None:
        os.environ.pop("RETRIFLOW_DATABASE_BACKEND", None)
        os.environ.pop("RETRIFLOW_DB_PATH", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_langchain_hybrid_retriever_returns_documents(self) -> None:
        from domain.retrieval import RetriFlowHybridRetriever

        documents = RetriFlowHybridRetriever().invoke("How does RetriFlow use LangChain retrievers?")

        self.assertGreaterEqual(len(documents), 1)
        self.assertTrue(all(isinstance(item, Document) for item in documents))
        self.assertEqual(documents[0].metadata["document_title"], "LangChain retrieval notes")
        self.assertIn("chunk_id", documents[0].metadata)
        self.assertIn("score", documents[0].metadata)
        self.assertIn("channel", documents[0].metadata)

    def test_retrieval_engine_uses_vector_store_for_semantic_channel(self) -> None:
        from domain.retrieval import RetriFlowRetrievalEngine
        from domain.retrieval_channels import RetrievedChunkRecord

        class FakeVectorStore:
            def similarity_search(self, query: str, k: int = 4) -> list[RetrievedChunkRecord]:
                return [
                    RetrievedChunkRecord(
                        chunk_id=1,
                        knowledge_base_id="kb-demo-1",
                        document_id=1,
                        document_title="LangChain retrieval notes",
                        content="RetriFlow uses LangChain retrievers to bridge hybrid recall and downstream RAG flows.",
                        score=0.88,
                        channel="semantic",
                    )
                ]

            def upsert_chunk_records(self, records) -> None:
                _ = records

        with patch("domain.retrieval.resolve_vector_store", return_value=FakeVectorStore()) as resolve_store:
            result = RetriFlowRetrievalEngine().retrieve("hybrid LangChain retriever")

        resolve_store.assert_called()
        self.assertGreaterEqual(len(result.sources), 1)
        self.assertEqual(result.sources[0].document_title, "LangChain retrieval notes")


if __name__ == "__main__":
    unittest.main()
