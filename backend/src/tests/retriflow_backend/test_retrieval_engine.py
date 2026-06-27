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
        os.environ["RETRIFLOW_SEED_DEMO_CONTENT"] = "true"

        from core.config import get_settings
        from core.state import initialize_database
        from modules.knowledge import RetriFlowKnowledgeService
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
        os.environ.pop("RETRIFLOW_SEED_DEMO_CONTENT", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_BM25_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_VECTOR_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_RRF_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_RERANK_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_FINAL_TOP_K", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_CROSS_REQUEST_CACHE_ENABLED", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_CROSS_REQUEST_CACHE_TTL_SECONDS", None)
        os.environ.pop("RETRIFLOW_RETRIEVAL_CROSS_REQUEST_CACHE_MAX_ENTRIES", None)
        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_langchain_hybrid_retriever_returns_documents(self) -> None:
        from modules.rag.retrieval.engine import RetriFlowHybridRetriever

        documents = RetriFlowHybridRetriever().invoke("How does RetriFlow use LangChain retrievers?")

        self.assertGreaterEqual(len(documents), 1)
        self.assertTrue(all(isinstance(item, Document) for item in documents))
        self.assertEqual(documents[0].metadata["document_title"], "LangChain retrieval notes")
        self.assertIn("chunk_id", documents[0].metadata)
        self.assertIn("score", documents[0].metadata)
        self.assertIn("channel", documents[0].metadata)

    def test_retrieval_engine_uses_vector_store_for_semantic_channel(self) -> None:
        from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
        from modules.rag.retrieval.channels import RetrievedChunkRecord

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

        with patch("modules.rag.retrieval.engine.resolve_vector_store", return_value=FakeVectorStore()) as resolve_store:
            result = RetriFlowRetrievalEngine().retrieve("hybrid LangChain retriever")

        resolve_store.assert_called()
        self.assertGreaterEqual(len(result.sources), 1)
        self.assertEqual(result.sources[0].document_title, "LangChain retrieval notes")

    def test_bm25_channel_excludes_disabled_chunks(self) -> None:
        from core.state import get_connection
        from modules.rag.retrieval.channels import BM25SearchChannel

        with get_connection() as connection:
            connection.execute(
                """
                update knowledge_chunks
                set enabled = 0
                where knowledge_base_id = ?
                """,
                ("kb-demo-1",),
            )
            connection.commit()

        records = BM25SearchChannel().retrieve(
            "RetriFlow LangChain retrievers",
            knowledge_base_ids=["kb-demo-1"],
        )

        self.assertEqual(records, [])

    def test_bm25_channel_prefers_vector_indexed_at_as_source_version(self) -> None:
        from core.state import get_connection
        from modules.rag.retrieval.channels import BM25SearchChannel

        with get_connection() as connection:
            connection.execute(
                """
                update knowledge_documents
                set vector_indexed_at = ?
                where knowledge_base_id = ?
                """,
                ("2026-06-25 12:34:56", "kb-demo-1"),
            )
            connection.commit()

        records = BM25SearchChannel().retrieve(
            "RetriFlow LangChain retrievers",
            knowledge_base_ids=["kb-demo-1"],
        )

        self.assertTrue(records)
        self.assertIn("2026-06-25 12:34:56", records[0].source_updated_at)

    def test_vector_search_channel_uses_search_context_and_returns_channel_result(self) -> None:
        from modules.rag.retrieval.channels import RetrievedChunkRecord, SearchContext, VectorSearchChannel

        semantic_records = [
            RetrievedChunkRecord(
                chunk_id=1,
                knowledge_base_id="kb-demo-1",
                document_id=1,
                document_title="LangChain retrieval notes",
                content="RetriFlow uses vector search through a channel.",
                score=0.91,
                channel="semantic",
            )
        ]

        class FakeVectorStore:
            def similarity_search(self, query: str, k: int = 80, knowledge_base_ids=None):
                self.last_query = query
                self.last_k = k
                self.last_knowledge_base_ids = knowledge_base_ids
                return semantic_records

        fake_vector_store = FakeVectorStore()
        channel = VectorSearchChannel(vector_store_factory=lambda: fake_vector_store)
        result = channel.search(
            SearchContext(
                original_question="original question",
                rewritten_question="rewritten question",
                queries=["rewritten question"],
                knowledge_base_ids=["kb-demo-1"],
                top_k=7,
            )
        )

        self.assertEqual(result.channel_name, "semantic")
        self.assertEqual(result.records, semantic_records)
        self.assertGreaterEqual(result.latency_ms, 0)
        self.assertEqual(fake_vector_store.last_query, "rewritten question")
        self.assertEqual(fake_vector_store.last_k, 7)
        self.assertEqual(fake_vector_store.last_knowledge_base_ids, ["kb-demo-1"])

    def test_rrf_fusion_prefers_chunks_hit_by_multiple_retrievers(self) -> None:
        from modules.rag.retrieval.channels import RetrievedChunkRecord
        from modules.rag.retrieval.postprocessors import reciprocal_rank_fusion

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

    def test_hybrid_retriever_executes_enabled_channel_registry(self) -> None:
        from modules.rag.retrieval.channels import RetrievedChunkRecord, SearchChannelResult
        from modules.rag.retrieval.engine import RetriFlowHybridRetriever

        class FakeChannel:
            name = "bm25"

            def __init__(self) -> None:
                self.seen_context = None

            def is_enabled(self, context) -> bool:
                self.seen_context = context
                return True

            def search(self, context) -> SearchChannelResult:
                self.seen_context = context
                return SearchChannelResult(
                    channel_name=self.name,
                    records=[
                        RetrievedChunkRecord(
                            chunk_id=1,
                            knowledge_base_id="kb-demo-1",
                            document_id=1,
                            document_title="Doc A",
                            content="registry hit",
                            score=1.0,
                            channel=self.name,
                        )
                    ],
                    latency_ms=1,
                )

            def retrieve(self, question: str, knowledge_base_ids=None, top_k: int = 80):
                raise AssertionError("engine should use search(context), not legacy retrieve()")

        fake_channel = FakeChannel()

        class FakeReranker:
            def rerank(self, question: str, records: list[RetrievedChunkRecord], limit: int = 10) -> list[RetrievedChunkRecord]:
                return records[:limit]

        with patch("modules.rag.retrieval.engine.RetriFlowRerankService", return_value=FakeReranker()):
            ranked, stage_counts = RetriFlowHybridRetriever(channels=[fake_channel]).retrieve_ranked_records(
                "original question",
                queries=["rewritten query"],
            )

        self.assertEqual([item.chunk_id for item in ranked], [1])
        self.assertEqual(stage_counts["bm25"], 1)
        self.assertEqual(fake_channel.seen_context.original_question, "original question")
        self.assertEqual(fake_channel.seen_context.queries, ["rewritten query"])

    def test_hybrid_retriever_keeps_results_when_one_channel_fails(self) -> None:
        from modules.rag.retrieval.channels import RetrievedChunkRecord, SearchChannelResult
        from modules.rag.retrieval.engine import RetriFlowHybridRetriever

        class FailingChannel:
            name = "bm25"

            def is_enabled(self, context) -> bool:
                return True

            def search(self, context) -> SearchChannelResult:
                raise RuntimeError("bm25 unavailable")

            def retrieve(self, question: str, knowledge_base_ids=None, top_k: int = 80):
                raise AssertionError("engine should use search(context)")

        class WorkingChannel:
            name = "semantic"

            def is_enabled(self, context) -> bool:
                return True

            def search(self, context) -> SearchChannelResult:
                return SearchChannelResult(
                    channel_name=self.name,
                    records=[
                        RetrievedChunkRecord(
                            chunk_id=2,
                            knowledge_base_id="kb-demo-1",
                            document_id=1,
                            document_title="Doc B",
                            content="semantic fallback",
                            score=0.9,
                            channel=self.name,
                        )
                    ],
                    latency_ms=3,
                    metadata={"query_count": len(context.effective_queries)},
                )

            def retrieve(self, question: str, knowledge_base_ids=None, top_k: int = 80):
                raise AssertionError("engine should use search(context)")

        retriever = RetriFlowHybridRetriever(
            channels=[FailingChannel(), WorkingChannel()],
        )
        ranked, stage_counts = retriever.retrieve_ranked_records("fallback retrieval")

        self.assertEqual([item.chunk_id for item in ranked], [2])
        self.assertEqual(stage_counts["bm25"], 0)
        self.assertEqual(stage_counts["semantic"], 1)
        self.assertEqual(retriever._last_stage_metrics["bm25"]["error"], "bm25 unavailable")
        self.assertEqual(retriever._last_stage_metrics["semantic"]["latency_ms"], 3)

    def test_hybrid_retriever_executes_enabled_postprocessor_chain_in_order(self) -> None:
        from modules.rag.retrieval.channels import RetrievedChunkRecord, SearchChannelResult
        from modules.rag.retrieval.engine import RetriFlowHybridRetriever

        class FakeChannel:
            name = "bm25"

            def is_enabled(self, context) -> bool:
                return True

            def search(self, context) -> SearchChannelResult:
                return SearchChannelResult(
                    channel_name=self.name,
                    records=[
                        RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "first", 1.0, self.name),
                        RetrievedChunkRecord(2, "kb-demo-1", 2, "Doc B", "second", 0.9, self.name),
                    ],
                )

            def retrieve(self, question: str, knowledge_base_ids=None, top_k: int = 80):
                raise AssertionError("engine should use search(context)")

        calls: list[str] = []

        class FirstPostProcessor:
            name = "first"
            order = 20

            def is_enabled(self, context) -> bool:
                return True

            def process(self, records, channel_results, context):
                calls.append(self.name)
                return list(reversed(records))

        class SecondPostProcessor:
            name = "second"
            order = 10

            def is_enabled(self, context) -> bool:
                return True

            def process(self, records, channel_results, context):
                calls.append(self.name)
                return records[:1]

        ranked, stage_counts = RetriFlowHybridRetriever(
            channels=[FakeChannel()],
            postprocessors=[FirstPostProcessor(), SecondPostProcessor()],
        ).retrieve_ranked_records("postprocessor order")

        self.assertEqual(calls, ["second", "first"])
        self.assertEqual([item.chunk_id for item in ranked], [1])
        self.assertEqual(stage_counts["second"], 1)
        self.assertEqual(stage_counts["first"], 1)
        self.assertEqual(stage_counts["final"], 1)

    def test_hybrid_retriever_skips_failing_postprocessor_and_continues(self) -> None:
        from modules.rag.retrieval.channels import RetrievedChunkRecord, SearchChannelResult
        from modules.rag.retrieval.engine import RetriFlowHybridRetriever

        class FakeChannel:
            name = "bm25"

            def is_enabled(self, context) -> bool:
                return True

            def search(self, context) -> SearchChannelResult:
                return SearchChannelResult(
                    channel_name=self.name,
                    records=[
                        RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "first", 1.0, self.name),
                        RetrievedChunkRecord(2, "kb-demo-1", 2, "Doc B", "second", 0.9, self.name),
                    ],
                )

            def retrieve(self, question: str, knowledge_base_ids=None, top_k: int = 80):
                raise AssertionError("engine should use search(context)")

        class FailingPostProcessor:
            name = "failing"
            order = 10

            def is_enabled(self, context) -> bool:
                return True

            def process(self, records, channel_results, context):
                raise RuntimeError("postprocessor unavailable")

        class FinalPostProcessor:
            name = "after_failure"
            order = 20

            def is_enabled(self, context) -> bool:
                return True

            def process(self, records, channel_results, context):
                return records[:1]

        retriever = RetriFlowHybridRetriever(
            channels=[FakeChannel()],
            postprocessors=[FailingPostProcessor(), FinalPostProcessor()],
        )
        ranked, stage_counts = retriever.retrieve_ranked_records("postprocessor failure")

        self.assertEqual([item.chunk_id for item in ranked], [1])
        self.assertEqual(stage_counts["failing"], 2)
        self.assertEqual(stage_counts["after_failure"], 1)
        self.assertEqual(retriever._last_stage_metrics["failing"]["error"], "postprocessor unavailable")

    def test_retrieval_engine_uses_bm25_rrf_and_rerank_pipeline(self) -> None:
        from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
        from modules.rag.retrieval.channels import RetrievedChunkRecord

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
            patch("modules.rag.retrieval.engine.resolve_vector_store", return_value=FakeVectorStore()) as resolve_store,
            patch("modules.rag.retrieval.engine.BM25SearchChannel.retrieve", return_value=bm25_records) as bm25_retrieve,
            patch("modules.rag.retrieval.engine.RetriFlowRerankService", return_value=FakeReranker()),
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
        from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
        from modules.rag.retrieval.channels import RetrievedChunkRecord

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
            patch("modules.rag.retrieval.engine.resolve_vector_store", return_value=FakeVectorStore()),
            patch("modules.rag.retrieval.engine.BM25SearchChannel.retrieve", side_effect=lambda query, knowledge_base_ids=None, top_k=80: bm25_by_query[query]) as bm25_retrieve,
            patch("modules.rag.retrieval.engine.RetriFlowRerankService", return_value=FakeReranker()),
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

    def test_retrieval_engine_adds_assessment_count_context(self) -> None:
        from modules.knowledge import RetriFlowKnowledgeService
        from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
        from schemas.knowledge import KnowledgeDocumentCreateRequest

        RetriFlowKnowledgeService().create_document(
            "kb-demo-1",
            KnowledgeDocumentCreateRequest(
                title="软件工程复习材料",
                source_type="manual",
                content=(
                    "第一部分 复习提纲:\n"
                    "一、名词解释(本题共4小题,每小题5分,共20分)\n"
                    "二、单选题(本题共20小题,每小题1分,共20分)\n"
                    "三、问答题(本题共2小题,每题10分,共20分)\n"
                    "四、应用题(第1小题20分,第2小题10分,第3小题10分,共40分)\n"
                    "第二部分 选择题练习\n"
                    "1、软件工程管理的具体内容不包括对_______管理。"
                ),
            ),
        )

        result = RetriFlowRetrievalEngine().retrieve(
            "软件工程复习题有多少道",
            knowledge_base_ids=["kb-demo-1"],
        )

        count_contexts = [source for source in result.sources if "题目统计线索" in source.content]
        self.assertTrue(count_contexts)
        self.assertIn("名词解释：4小题", count_contexts[0].content)
        self.assertIn("单选题：20小题", count_contexts[0].content)
        self.assertIn("问答题：2小题", count_contexts[0].content)
        self.assertIn("应用题：3小题", count_contexts[0].content)
        self.assertIn("合计：29小题", count_contexts[0].content)

    def test_retrieval_engine_uses_configured_hybrid_top_k_pipeline(self) -> None:
        os.environ["RETRIFLOW_RETRIEVAL_BM25_TOP_K"] = "7"
        os.environ["RETRIFLOW_RETRIEVAL_VECTOR_TOP_K"] = "9"
        os.environ["RETRIFLOW_RETRIEVAL_RRF_TOP_K"] = "4"
        os.environ["RETRIFLOW_RETRIEVAL_RERANK_TOP_K"] = "3"
        os.environ["RETRIFLOW_RETRIEVAL_FINAL_TOP_K"] = "2"

        from core.config import get_settings
        from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
        from modules.rag.retrieval.channels import RetrievedChunkRecord

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
            patch("modules.rag.retrieval.engine.resolve_vector_store", return_value=fake_vector_store),
            patch("modules.rag.retrieval.engine.BM25SearchChannel.retrieve", return_value=bm25_records) as bm25_retrieve,
            patch("modules.rag.retrieval.engine.RetriFlowRerankService", return_value=fake_reranker),
        ):
            result = RetriFlowRetrievalEngine().retrieve("configured top k query")

        self.assertEqual(bm25_retrieve.call_args.kwargs["top_k"], 7)
        self.assertEqual(fake_vector_store.last_k, 9)
        self.assertEqual(fake_reranker.last_limit, 3)
        self.assertEqual(result.stage_counts["hybrid_rrf"], 4)
        self.assertEqual(result.stage_counts["rerank"], 3)
        self.assertEqual(result.stage_counts["final"], 2)
        self.assertEqual(len(result.sources), 2)

    def test_retrieval_engine_uses_intent_route_top_k_override(self) -> None:
        from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
        from modules.rag.retrieval.channels import RetrievedChunkRecord

        bm25_records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "intent bm25 hit", 12.0, "bm25"),
        ]
        semantic_records = [
            RetrievedChunkRecord(2, "kb-demo-1", 1, "Doc A", "intent vector hit", 0.91, "semantic"),
        ]

        class FakeVectorStore:
            def similarity_search(self, query: str, k: int = 80, knowledge_base_ids=None):
                self.last_query = query
                self.last_k = k
                self.last_knowledge_base_ids = knowledge_base_ids
                return semantic_records

            def upsert_chunk_records(self, records) -> None:
                _ = records

        class FakeReranker:
            def rerank(self, question: str, records: list[RetrievedChunkRecord], limit: int = 10) -> list[RetrievedChunkRecord]:
                return records[:limit]

        fake_vector_store = FakeVectorStore()
        with (
            patch("modules.rag.retrieval.engine.resolve_vector_store", return_value=fake_vector_store),
            patch("modules.rag.retrieval.engine.BM25SearchChannel.retrieve", return_value=bm25_records) as bm25_retrieve,
            patch("modules.rag.retrieval.engine.RetriFlowRerankService", return_value=FakeReranker()),
        ):
            result = RetriFlowRetrievalEngine().retrieve(
                "intent routed query",
                knowledge_base_ids=["kb-demo-1"],
                top_k_override=6,
            )

        self.assertEqual(bm25_retrieve.call_args.kwargs["top_k"], 6)
        self.assertEqual(fake_vector_store.last_k, 6)
        self.assertEqual(fake_vector_store.last_knowledge_base_ids, ["kb-demo-1"])
        self.assertEqual(result.stage_metrics["bm25"]["top_k"], 6)
        self.assertEqual(result.stage_metrics["semantic"]["top_k"], 6)

    def test_retrieval_engine_applies_per_knowledge_base_top_k(self) -> None:
        from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
        from modules.rag.retrieval.channels import RetrievedChunkRecord

        bm25_records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "kb1 best", 12.0, "bm25"),
            RetrievedChunkRecord(2, "kb-demo-1", 1, "Doc A", "kb1 second", 11.0, "bm25"),
            RetrievedChunkRecord(3, "kb-demo-2", 2, "Doc B", "kb2 best", 10.0, "bm25"),
            RetrievedChunkRecord(4, "kb-demo-2", 2, "Doc B", "kb2 second", 9.0, "bm25"),
            RetrievedChunkRecord(5, "kb-demo-2", 2, "Doc B", "kb2 third", 8.0, "bm25"),
        ]

        class FakeChannel:
            name = "bm25"

            def is_enabled(self, context) -> bool:
                return True

            def search(self, context):
                from modules.rag.retrieval.channels import SearchChannelResult

                self.last_context = context
                return SearchChannelResult(channel_name=self.name, records=list(bm25_records), metadata={"query_count": 1})

        fake_channel = FakeChannel()
        retriever = RetriFlowRetrievalEngine(
            retriever_factory=lambda **kwargs: __import__(
                "modules.rag.retrieval.engine",
                fromlist=["RetriFlowHybridRetriever"],
            ).RetriFlowHybridRetriever(
                channels=[fake_channel],
                postprocessors=[],
                **kwargs,
            )
        )
        result = retriever.retrieve(
            "per kb top k",
            knowledge_base_ids=["kb-demo-1", "kb-demo-2"],
            top_k_by_knowledge_base={"kb-demo-1": 1, "kb-demo-2": 2},
        )

        self.assertEqual([source.chunk_id for source in result.sources], [1, 3, 4])
        self.assertEqual(result.stage_metrics["bm25"]["top_k_by_knowledge_base"], {"kb-demo-1": 1, "kb-demo-2": 2})

    def test_retrieval_engine_applies_per_knowledge_base_min_score(self) -> None:
        from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
        from modules.rag.retrieval.channels import RetrievedChunkRecord

        records = [
            RetrievedChunkRecord(1, "kb-demo-1", 1, "Doc A", "strong", 0.8, "bm25"),
            RetrievedChunkRecord(2, "kb-demo-1", 1, "Doc A", "weak", 0.2, "bm25"),
            RetrievedChunkRecord(3, "kb-demo-2", 2, "Doc B", "other", 0.3, "bm25"),
        ]

        class FakeChannel:
            name = "bm25"

            def is_enabled(self, context) -> bool:
                return True

            def search(self, context):
                from modules.rag.retrieval.channels import SearchChannelResult

                return SearchChannelResult(channel_name=self.name, records=list(records), metadata={"query_count": 1})

        result = RetriFlowRetrievalEngine(
            retriever_factory=lambda **kwargs: __import__(
                "modules.rag.retrieval.engine",
                fromlist=["RetriFlowHybridRetriever"],
            ).RetriFlowHybridRetriever(channels=[FakeChannel()], postprocessors=[], **kwargs)
        ).retrieve(
            "per kb min score",
            knowledge_base_ids=["kb-demo-1", "kb-demo-2"],
            min_score_by_knowledge_base={"kb-demo-1": 0.5},
        )

        self.assertEqual([source.chunk_id for source in result.sources], [1, 3])
        self.assertEqual(result.stage_metrics["bm25"]["min_score_by_knowledge_base"], {"kb-demo-1": 0.5})

    def test_bm25_channel_caches_duplicate_queries_within_request(self) -> None:
        from modules.rag.retrieval.channels import BM25SearchChannel, RetrievedChunkRecord, SearchContext

        class CountingBM25Channel(BM25SearchChannel):
            def __init__(self) -> None:
                self.calls = 0

            def retrieve(self, question: str, knowledge_base_ids=None, top_k: int = 80):
                self.calls += 1
                return [
                    RetrievedChunkRecord(
                        self.calls,
                        "kb-demo-1",
                        1,
                        "Doc A",
                        f"hit {question}",
                        1.0,
                        self.name,
                    )
                ]

        channel = CountingBM25Channel()
        result = channel.search(
            SearchContext(
                original_question="claim",
                queries=["claim", "claim", "policy"],
                knowledge_base_ids=["kb-demo-1"],
                top_k=5,
            )
        )

        self.assertEqual(channel.calls, 2)
        self.assertEqual(len(result.records), 3)
        self.assertEqual(result.metadata["query_count"], 3)
        self.assertEqual(result.metadata["cache_hits"], 1)

    def test_bm25_channel_can_cache_queries_across_requests_when_enabled(self) -> None:
        os.environ["RETRIFLOW_RETRIEVAL_CROSS_REQUEST_CACHE_ENABLED"] = "true"
        os.environ["RETRIFLOW_RETRIEVAL_CROSS_REQUEST_CACHE_TTL_SECONDS"] = "60"
        from core.config import get_settings
        from modules.rag.retrieval.channels import BM25SearchChannel, RetrievedChunkRecord, SearchContext

        get_settings.cache_clear()
        BM25SearchChannel.clear_cross_request_cache()

        class CountingBM25Channel(BM25SearchChannel):
            calls = 0

            def retrieve(self, question: str, knowledge_base_ids=None, top_k: int = 80):
                type(self).calls += 1
                return [
                    RetrievedChunkRecord(
                        type(self).calls,
                        "kb-demo-1",
                        1,
                        "Doc A",
                        f"hit {question}",
                        1.0,
                        self.name,
                    )
                ]

        first = CountingBM25Channel().search(SearchContext(original_question="claim", knowledge_base_ids=["kb-demo-1"], top_k=5))
        second = CountingBM25Channel().search(SearchContext(original_question="claim", knowledge_base_ids=["kb-demo-1"], top_k=5))

        self.assertEqual(CountingBM25Channel.calls, 1)
        self.assertEqual(first.metadata["cache_hits"], 0)
        self.assertEqual(second.metadata["cache_hits"], 1)
        self.assertEqual(second.metadata["cache_scope"], "cross_request")


if __name__ == "__main__":
    unittest.main()
