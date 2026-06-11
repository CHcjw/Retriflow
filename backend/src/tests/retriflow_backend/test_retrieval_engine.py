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
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"

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
        os.environ.pop("RETRIFLOW_DATABASE_DSN", None)
        os.environ.pop("RETRIFLOW_PGVECTOR_DSN", None)
        os.environ.pop("RETRIFLOW_VECTOR_STORE_TYPE", None)
        os.environ.pop("RETRIFLOW_LLM_PROVIDER", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_BM25_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_VECTOR_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_RRF_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_RERANK_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_FINAL_TOP_K", None)
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

    def test_rrf_fusion_prefers_chunks_hit_by_multiple_retrievers(self) -> None:
        from domain.retrieval_channels import RetrievedChunkRecord
        from domain.retrieval_postprocessors import reciprocal_rank_fusion

        bm25_records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "shared hit", 12.0, "bm25"),
            RetrievedChunkRecord(2, "kb-demo-1", 2, "Doc B", "bm25 only", 11.0, "bm25"),
        ]
        vector_records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "shared hit", 0.91, "semantic"),
            RetrievedChunkRecord(3, "kb-demo-1", 3, "Doc C", "vector only", 0.89, "semantic"),
        ]

        fused = reciprocal_rank_fusion(
            ranked_lists=[bm25_records, vector_records],
            top_k=50,
        )

        self.assertGreaterEqual(len(fused), 3)
        self.assertEqual(fused[0].chunk_id, 1)
        self.assertEqual(fused[0].channel, "hybrid_rrf")

    def test_retrieval_engine_uses_bm25_rrf_and_rerank_pipeline(self) -> None:
        from domain.retrieval import RetriFlowRetrievalEngine
        from domain.retrieval_channels import RetrievedChunkRecord

        bm25_records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "shared hit", 12.0, "bm25"),
            RetrievedChunkRecord(2, "kb-demo-1", 2, "Doc B", "bm25 only", 11.0, "bm25"),
        ]
        semantic_records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "shared hit", 0.91, "semantic"),
            RetrievedChunkRecord(3, "kb-demo-1", 3, "Doc C", "vector only", 0.89, "semantic"),
        ]

        class FakeVectorStore:
            def similarity_search(self, query: str, k: int = 80):
                self.last_query = query
                self.last_k = k
                return semantic_records

            def upsert_chunk_records(self, records) -> None:
                _ = records

        class FakeReranker:
            def rerank(self, question: str, records: list[RetrievedChunkRecord], limit: int = 10) -> list[RetrievedChunkRecord]:
                self.last_question = question
                self.last_limit = limit
                preferred_order = {3: 0, 1: 1, 2: 2}
                ranked = sorted(records, key=lambda item: preferred_order[item.chunk_id])
                return ranked[:limit]

        with (
            patch("domain.retrieval.resolve_vector_store", return_value=FakeVectorStore()) as resolve_store,
            patch("domain.retrieval.BM25SearchChannel.retrieve", return_value=bm25_records) as bm25_retrieve,
            patch("domain.retrieval.RetriFlowRerankService", return_value=FakeReranker()),
        ):
            result = RetriFlowRetrievalEngine().retrieve("hybrid LangChain retriever")

        resolve_store.assert_called_once()
        bm25_retrieve.assert_called_once()
        self.assertEqual(len(result.sources), 3)
        self.assertEqual(result.sources[0].chunk_id, 3)
        self.assertIn("bm25", result.channels)
        self.assertIn("semantic", result.channels)
        self.assertEqual(result.stage_counts["bm25"], 2)
        self.assertEqual(result.stage_counts["semantic"], 2)
        self.assertEqual(result.stage_counts["hybrid_rrf"], 3)
        self.assertEqual(result.stage_counts["rerank"], 3)
        self.assertEqual(result.stage_counts["final"], 3)

    def test_retrieval_engine_supports_multi_queries_before_rerank(self) -> None:
        from domain.retrieval import RetriFlowRetrievalEngine
        from domain.retrieval_channels import RetrievedChunkRecord

        bm25_by_query = {
            "insurance claim process": [
                RetrievedChunkRecord(1, "kb-demo-1", 1, "Claim Doc", "claim content", 12.0, "bm25"),
            ],
            "underwriting policy rules": [
                RetrievedChunkRecord(2, "kb-demo-1", 2, "Underwriting Doc", "underwriting content", 11.0, "bm25"),
            ],
        }
        semantic_by_query = {
            "insurance claim process": [
                RetrievedChunkRecord(1, "kb-demo-1", 1, "Claim Doc", "claim content", 0.91, "semantic"),
            ],
            "underwriting policy rules": [
                RetrievedChunkRecord(2, "kb-demo-1", 2, "Underwriting Doc", "underwriting content", 0.89, "semantic"),
            ],
        }

        class FakeVectorStore:
            def similarity_search(self, query: str, k: int = 80):
                return semantic_by_query[query]

            def upsert_chunk_records(self, records) -> None:
                _ = records

        class FakeReranker:
            def rerank(self, question: str, records: list[RetrievedChunkRecord], limit: int = 10) -> list[RetrievedChunkRecord]:
                self.last_question = question
                self.last_limit = limit
                return records[:limit]

        with (
            patch("domain.retrieval.resolve_vector_store", return_value=FakeVectorStore()),
            patch("domain.retrieval.BM25SearchChannel.retrieve", side_effect=lambda query, knowledge_base_ids=None, top_k=80: bm25_by_query[query]) as bm25_retrieve,
            patch("domain.retrieval.RetriFlowRerankService", return_value=FakeReranker()),
        ):
            result = RetriFlowRetrievalEngine().retrieve(
                "原始问题",
                queries=["insurance claim process", "underwriting policy rules"],
            )

        self.assertEqual(bm25_retrieve.call_count, 2)
        self.assertEqual(len(result.sources), 2)
        self.assertEqual({item.document_title for item in result.sources}, {"Claim Doc", "Underwriting Doc"})
        self.assertEqual(result.stage_counts["bm25"], 2)
        self.assertEqual(result.stage_counts["semantic"], 2)
        self.assertEqual(result.stage_counts["final"], 2)

    def test_retrieval_engine_uses_configured_hybrid_top_k_pipeline(self) -> None:
        os.environ["RETRIFLOW_RETRIEVAL_BM25_TOP_K"] = "7"
        os.environ["RETRIFLOW_RETRIEVAL_VECTOR_TOP_K"] = "9"
        os.environ["RETRIFLOW_RETRIEVAL_RRF_TOP_K"] = "4"
        os.environ["RETRIFLOW_RETRIEVAL_RERANK_TOP_K"] = "3"
        os.environ["RETRIFLOW_RETRIEVAL_FINAL_TOP_K"] = "2"

        from core.config import get_settings
        from domain.retrieval import RetriFlowRetrievalEngine
        from domain.retrieval_channels import RetrievedChunkRecord

        get_settings.cache_clear()

        bm25_records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "shared hit", 12.0, "bm25"),
            RetrievedChunkRecord(2, "kb-demo-1", 2, "Doc B", "bm25 only", 11.0, "bm25"),
            RetrievedChunkRecord(3, "kb-demo-1", 3, "Doc C", "another hit", 10.0, "bm25"),
        ]
        semantic_records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "shared hit", 0.91, "semantic"),
            RetrievedChunkRecord(4, "kb-demo-1", 4, "Doc D", "vector only", 0.89, "semantic"),
            RetrievedChunkRecord(5, "kb-demo-1", 5, "Doc E", "vector extra", 0.87, "semantic"),
        ]

        class FakeVectorStore:
            def similarity_search(self, query: str, k: int = 80):
                self.last_query = query
                self.last_k = k
                return semantic_records

            def upsert_chunk_records(self, records) -> None:
                _ = records

        class FakeReranker:
            def rerank(self, question: str, records: list[RetrievedChunkRecord], limit: int = 10) -> list[RetrievedChunkRecord]:
                self.last_question = question
                self.last_limit = limit
                return records[:limit]

        fake_vector_store = FakeVectorStore()
        fake_reranker = FakeReranker()

        with (
            patch("domain.retrieval.resolve_vector_store", return_value=fake_vector_store),
            patch("domain.retrieval.BM25SearchChannel.retrieve", return_value=bm25_records) as bm25_retrieve,
            patch("domain.retrieval.RetriFlowRerankService", return_value=fake_reranker),
        ):
            result = RetriFlowRetrievalEngine().retrieve("configured top k query")

        self.assertEqual(bm25_retrieve.call_args.kwargs["top_k"], 7)
        self.assertEqual(fake_vector_store.last_k, 9)
        self.assertEqual(fake_reranker.last_limit, 3)
        self.assertEqual(result.stage_counts["hybrid_rrf"], 4)
        self.assertEqual(result.stage_counts["rerank"], 3)
        self.assertEqual(result.stage_counts["final"], 2)
        self.assertEqual(len(result.sources), 2)


if __name__ == "__main__":
    unittest.main()
