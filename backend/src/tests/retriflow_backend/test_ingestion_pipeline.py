import sys
import unittest
from pathlib import Path

from langchain_core.documents import Document


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowIngestionPipelineTests(unittest.TestCase):
    def test_pipeline_exposes_langchain_segment_documents(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline()
        result = pipeline.run(
            "First paragraph introduces RetriFlow.\n\n"
            "Second paragraph explains LangChain document splitting.\n\n"
            "Third paragraph covers retrieval metadata."
        )

        self.assertEqual(len(result.source_documents), 3)
        self.assertTrue(all(isinstance(item, Document) for item in result.source_documents))
        self.assertEqual(result.source_documents[0].page_content, "First paragraph introduces RetriFlow.")
        self.assertEqual(result.source_documents[1].metadata["segment_index"], 1)
        self.assertEqual(result.source_documents[2].metadata["segment_count"], 3)

    def test_pipeline_exposes_langchain_chunk_documents_with_metadata(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline()
        result = pipeline.run(
            "RetriFlow uses LangChain documents for chunk metadata and retrieval alignment. "
            "RetriFlow uses LangChain documents for chunk metadata and retrieval alignment. "
            "RetriFlow uses LangChain documents for chunk metadata and retrieval alignment."
        )

        self.assertGreaterEqual(len(result.chunk_documents), 2)
        self.assertTrue(all(isinstance(item, Document) for item in result.chunk_documents))
        self.assertEqual(
            [document.page_content for document in result.chunk_documents],
            result.chunks,
        )
        self.assertEqual(result.chunk_documents[0].metadata["chunk_index"], 0)
        self.assertEqual(result.chunk_documents[0].metadata["segment_index"], 0)
        self.assertEqual(
            result.chunk_documents[-1].metadata["chunk_count"],
            len(result.chunk_documents),
        )

    def test_fixed_strategy_produces_predictable_small_chunks(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(chunk_size=40, chunk_overlap=0, strategy="fixed")
        result = pipeline.run(
            "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron."
        )

        self.assertGreaterEqual(len(result.chunk_documents), 2)
        self.assertTrue(all(document.metadata["strategy"] == "fixed" for document in result.chunk_documents))

    def test_recursive_strategy_respects_custom_separator_order(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(
            chunk_size=32,
            chunk_overlap=0,
            strategy="recursive",
            recursive_separators=["||", "|", " ", ""],
        )
        result = pipeline.run("SectionA||SectionB|SectionC|SectionD")

        self.assertGreaterEqual(len(result.chunk_documents), 2)
        self.assertTrue(all(document.metadata["strategy"] == "recursive" for document in result.chunk_documents))

    def test_auto_strategy_selects_recursive_for_manual_style_knowledge_docs(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(strategy="auto")
        result = pipeline.run(
            "Chapter 1\n\nRetriFlow handbook content.\n\nChapter 2\n\nMore knowledge base material.",
            document_type="knowledge_base",
        )

        self.assertEqual(result.chunk_documents[0].metadata["strategy"], "recursive")
        self.assertEqual(result.chunk_documents[0].metadata["document_type"], "knowledge_base")

    def test_semantic_strategy_marks_chunks_with_semantic_metadata(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(strategy="semantic_embedding")
        result = pipeline.run(
            "Clause 1 payment obligations.\n\nClause 2 liability allocation.\n\nClause 3 dispute resolution.",
            document_type="contract",
        )

        self.assertGreaterEqual(len(result.chunk_documents), 1)
        self.assertTrue(all(document.metadata["strategy"] == "semantic_embedding" for document in result.chunk_documents))
        self.assertTrue(all("semantic_group" in document.metadata for document in result.chunk_documents))

    def test_semantic_strategy_uses_embedding_service(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        class StubEmbeddingService:
            def __init__(self) -> None:
                self.calls: list[list[str]] = []

            def embed_texts(self, texts: list[str]) -> list[list[float]]:
                self.calls.append(list(texts))
                return [[float(index + 1), 0.0, 0.0] for index, _ in enumerate(texts)]

        embedding_service = StubEmbeddingService()
        pipeline = RetriFlowIngestionPipeline(strategy="semantic_embedding", embedding_service=embedding_service)
        result = pipeline.run(
            "Clause 1 payment obligations.\n\nClause 2 liability allocation.\n\nClause 3 dispute resolution.",
            document_type="contract",
        )

        self.assertGreaterEqual(len(result.chunk_documents), 1)
        self.assertGreaterEqual(len(embedding_service.calls), 1)
        self.assertGreaterEqual(sum(len(batch) for batch in embedding_service.calls), 3)

    def test_hybrid_recursive_semantic_strategy_preserves_parent_segment_metadata(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(strategy="hybrid_recursive_semantic")
        result = pipeline.run(
            "Title A\n\nSentence one. Sentence two. Sentence three.\n\nTitle B\n\nSentence four. Sentence five.",
            document_type="mixed_knowledge",
        )

        self.assertGreaterEqual(len(result.chunk_documents), 2)
        self.assertTrue(all(document.metadata["strategy"] == "hybrid_recursive_semantic" for document in result.chunk_documents))
        self.assertTrue(all("parent_segment_index" in document.metadata for document in result.chunk_documents))

    def test_postprocessing_merges_tiny_chunks_and_preserves_flags(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(chunk_size=24, chunk_overlap=0, strategy="fixed")
        result = pipeline.run(
            "Tiny.\n\nThis is a sufficiently long paragraph for chunking.\n\nMini.\n\nAnother sufficiently long paragraph."
        )

        self.assertTrue(all(document.metadata.get("postprocessed") is True for document in result.chunk_documents))
        self.assertTrue(all(len(document.page_content.strip()) >= 8 for document in result.chunk_documents))


if __name__ == "__main__":
    unittest.main()
