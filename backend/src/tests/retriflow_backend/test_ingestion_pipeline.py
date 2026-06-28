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

    def test_fixed_size_alias_accepts_camel_case_config_names(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(
            strategy="fixed_size",
            chunk_config={"chunkSize": 16, "overlapSize": 4},
        )
        result = pipeline.run("0123456789abcdefghijklmnopqrstuvwxyz")

        self.assertGreaterEqual(len(result.chunk_documents), 2)
        self.assertTrue(all(document.metadata["strategy"] == "fixed" for document in result.chunk_documents))
        self.assertEqual(result.chunk_documents[1].metadata["start_index"], 12)

    def test_structure_aware_strategy_preserves_markdown_boundaries(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(
            strategy="structure_aware",
            chunk_config={"targetChars": 80, "overlapChars": 0, "maxChars": 120, "minChars": 40},
        )
        result = pipeline.run(
            "# Heading A\n\n"
            "Paragraph A explains the first section with enough text to form a chunk.\n\n"
            "```python\nprint('kept together')\n```\n\n"
            "# Heading B\n\n"
            "Paragraph B explains the second section with enough text to form another chunk."
        )

        self.assertGreaterEqual(len(result.chunk_documents), 2)
        self.assertTrue(all(document.metadata["strategy"] == "structure_aware" for document in result.chunk_documents))
        self.assertTrue(any("```python\nprint('kept together')\n```" in document.page_content for document in result.chunk_documents))

    def test_structure_aware_strategy_splits_long_paragraphs_on_natural_boundaries(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(
            strategy="structure_aware",
            chunk_config={"targetChars": 80, "overlapChars": 0, "maxChars": 120, "minChars": 40},
        )
        text = "# Long Section\n\n" + "A long paragraph keeps its semantic unit. " * 12

        result = pipeline.run(text)

        self.assertGreater(len(result.chunk_documents), 1)
        self.assertTrue(all(len(document.page_content) <= 120 for document in result.chunk_documents))
        self.assertFalse(any(len(document.page_content) == 120 for document in result.chunk_documents))
        self.assertTrue(all(document.page_content.endswith((".", "# Long Section")) for document in result.chunk_documents))

    def test_structure_aware_strategy_splits_chinese_sentences_without_spaces(self) -> None:
        from modules.ingestion import RetriFlowIngestionPipeline

        pipeline = RetriFlowIngestionPipeline(
            strategy="structure_aware",
            chunk_config={"targetChars": 1400, "overlapChars": 0, "maxChars": 1800, "minChars": 600},
        )
        sentence = "互联网保险平台承载投保、承保、核保、理赔、续保、退保、保全、资金结算、风控反欺诈、渠道分销、合作共保与再保等全流程业务，贯穿大量敏感个人信息、健康医疗信息、金融交易信息与业务规则。"
        text = "# 互联网保险系统数据安全规范\n\n" + sentence * 36

        result = pipeline.run(text)

        lengths = [len(document.page_content) for document in result.chunk_documents]
        self.assertGreater(len(lengths), 1)
        self.assertTrue(all(length <= 1800 for length in lengths), lengths)
        self.assertFalse(any(length == 1800 for length in lengths), lengths)

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

    def test_stored_pipeline_nodes_drive_chunking_configuration(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parser",
                node_type="parser",
                next_node_id="cleaner",
                config={"preserve_structure": True},
            ),
            IngestionPipelineNodeConfig(
                node_id="cleaner",
                node_type="cleaner",
                next_node_id="chunker",
                config={"normalize_whitespace": True},
            ),
            IngestionPipelineNodeConfig(
                node_id="chunker",
                node_type="chunker",
                next_node_id="embedder",
                config={"strategy": "fixed_size", "chunkSize": 12, "overlapSize": 3},
            ),
            IngestionPipelineNodeConfig(
                node_id="embedder",
                node_type="embedder",
                next_node_id="indexer",
                config={"provider": "ollama", "model": "qwen3-embedding:8b"},
            ),
            IngestionPipelineNodeConfig(
                node_id="indexer",
                node_type="indexer",
                config={"store": "pgvector"},
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run("0123456789abcdefghijklmnopqrstuvwxyz")

        self.assertGreaterEqual(len(result.chunk_documents), 3)
        self.assertEqual(result.chunk_documents[0].metadata["strategy"], "fixed")
        self.assertEqual(result.chunk_documents[1].metadata["start_index"], 9)
        self.assertEqual(
            [node.node_type for node in result.node_results],
            ["parser", "cleaner", "chunker", "embedder", "indexer"],
        )
        self.assertTrue(any("qwen3-embedding:8b" in node.message for node in result.node_results))

    def test_pipeline_node_results_include_runtime_fields_and_output(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="chunk",
                config={"engine": "plain-text"},
            ),
            IngestionPipelineNodeConfig(
                node_id="chunk",
                node_type="chunker",
                next_node_id="index",
                config={"strategy": "fixed_size", "chunkSize": 16, "overlapSize": 4},
            ),
            IngestionPipelineNodeConfig(
                node_id="index",
                node_type="indexer",
                config={"store": "pgvector"},
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run("0123456789abcdefghijklmnopqrstuvwxyz")

        chunk_node = next(node for node in result.node_results if node.node_id == "chunk")
        index_node = next(node for node in result.node_results if node.node_id == "index")

        self.assertEqual(chunk_node.status, "success")
        self.assertEqual(chunk_node.error_message, "")
        self.assertEqual(chunk_node.output["chunkCount"], len(result.chunks))
        self.assertEqual(index_node.output["settings"], {"store": "pgvector"})
        self.assertEqual(index_node.output["chunkCount"], len(result.chunks))

    def test_pipeline_node_condition_false_records_skipped_status(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="chunk",
                config={"engine": "plain-text"},
            ),
            IngestionPipelineNodeConfig(
                node_id="chunk",
                node_type="chunker",
                condition='{"field":"document_type","operator":"eq","value":"contract"}',
                config={"strategy": "fixed_size", "chunkSize": 16, "overlapSize": 4},
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run("0123456789abcdefghijklmnopqrstuvwxyz", document_type="manual")

        chunk_node = next(node for node in result.node_results if node.node_id == "chunk")
        self.assertTrue(chunk_node.success)
        self.assertEqual(chunk_node.status, "skipped")
        self.assertTrue(chunk_node.message.startswith("Skipped:"))

    def test_pipeline_node_condition_reads_nested_metadata_fields(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="enhance",
                config={"engine": "plain-text"},
            ),
            IngestionPipelineNodeConfig(
                node_id="enhance",
                node_type="enhancer",
                condition='{"field":"metadata.department","operator":"eq","value":"finance"}',
                config={"extract_keywords": True},
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run(
            "Quarterly revenue policy.",
            metadata={
                "department": "finance",
                "keywords": ["revenue", "policy"],
                "questions": ["What is the policy?"],
                "enhancedText": "Quarterly revenue policy with generated metadata.",
            },
        )

        enhance_node = next(node for node in result.node_results if node.node_id == "enhance")
        self.assertEqual(enhance_node.status, "success")
        self.assertEqual(enhance_node.output["keywords"], ["revenue", "policy"])
        self.assertEqual(enhance_node.output["questions"], ["What is the policy?"])
        self.assertEqual(enhance_node.output["enhancedText"], "Quarterly revenue policy with generated metadata.")

    def test_pipeline_node_condition_reads_context_identity_fields(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="index",
            ),
            IngestionPipelineNodeConfig(
                node_id="index",
                node_type="indexer",
                condition=(
                    '{"all":['
                    '{"field":"taskId","operator":"eq","value":"task-100"},'
                    '{"field":"pipelineId","operator":"eq","value":"pipeline-main"},'
                    '{"field":"vectorSpaceId","operator":"eq","value":"insurance"}'
                    ']}'
                ),
                config={"store": "pgvector"},
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run(
            "Context identity should drive ingestion conditions.",
            metadata={
                "taskId": "task-100",
                "pipelineId": "pipeline-main",
                "vectorSpaceId": "insurance",
            },
        )

        index_node = next(node for node in result.node_results if node.node_id == "index")
        self.assertEqual(index_node.status, "success")

    def test_pipeline_node_output_matches_fetcher_parser_shape(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="fetch",
                node_type="fetcher",
                next_node_id="parse",
                config={"source": "upload"},
            ),
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                config={"engine": "tika"},
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run(
            "Uploaded document body.",
            metadata={
                "source_type": "upload",
                "source_location": "documents/report.md",
                "file_name": "report.md",
                "mime_type": "text/markdown",
                "rawBytesLength": 23,
                "rawBytesBase64": "VXBsb2FkZWQgZG9jdW1lbnQgYm9keS4=",
                "document": {"title": "report"},
            },
        )

        fetch_node = next(node for node in result.node_results if node.node_id == "fetch")
        parse_node = next(node for node in result.node_results if node.node_id == "parse")

        self.assertEqual(fetch_node.output["source"]["type"], "upload")
        self.assertEqual(fetch_node.output["source"]["location"], "documents/report.md")
        self.assertEqual(fetch_node.output["source"]["fileName"], "report.md")
        self.assertEqual(fetch_node.output["mimeType"], "text/markdown")
        self.assertEqual(fetch_node.output["rawBytesLength"], 23)
        self.assertEqual(parse_node.output["mimeType"], "text/markdown")
        self.assertEqual(parse_node.output["rawText"], "Uploaded document body.")
        self.assertEqual(parse_node.output["document"], {"title": "report"})

    def test_pipeline_executes_only_start_node_chain(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="chunk",
            ),
            IngestionPipelineNodeConfig(
                node_id="chunk",
                node_type="chunker",
                config={"strategy": "fixed_size", "chunkSize": 16, "overlapSize": 4},
            ),
            IngestionPipelineNodeConfig(
                node_id="orphan",
                node_type="indexer",
                config={"store": "pgvector"},
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run("0123456789abcdefghijklmnopqrstuvwxyz")

        self.assertEqual([node.node_id for node in result.node_results], ["parse", "chunk"])

    def test_pipeline_rejects_missing_next_node(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="missing",
            )
        ]

        with self.assertRaisesRegex(ValueError, "missing next node"):
            RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)

    def test_pipeline_rejects_cycle(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="chunk",
            ),
            IngestionPipelineNodeConfig(
                node_id="chunk",
                node_type="chunker",
                next_node_id="parse",
            ),
        ]

        with self.assertRaisesRegex(ValueError, "cycle"):
            RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)

    def test_pipeline_unknown_node_type_fails_and_stops_chain(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="custom",
            ),
            IngestionPipelineNodeConfig(
                node_id="custom",
                node_type="custom_missing",
                next_node_id="index",
            ),
            IngestionPipelineNodeConfig(
                node_id="index",
                node_type="indexer",
                config={"store": "pgvector"},
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run("Unknown node types should fail in the ingestion runtime.")

        self.assertEqual([node.node_id for node in result.node_results], ["parse", "custom"])
        custom_node = result.node_results[-1]
        self.assertFalse(custom_node.success)
        self.assertEqual(custom_node.status, "failed")
        self.assertIn("Unknown ingestion node type", custom_node.error_message)

    def test_pipeline_uses_registered_node_executor_by_type(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion.service import IngestionNodeExecutionResult, RetriFlowIngestionNodeExecutor, RetriFlowIngestionPipeline

        class CustomAuditExecutor(RetriFlowIngestionNodeExecutor):
            node_types = ("audit",)

            def execute(self, *, node, context, pipeline):
                context.metadata["audit_node"] = node.node_id
                return IngestionNodeExecutionResult.ok("Audit node executed.")

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="audit",
            ),
            IngestionPipelineNodeConfig(
                node_id="audit",
                node_type="audit",
            ),
        ]

        pipeline = RetriFlowIngestionPipeline(
            pipeline_nodes=RetriFlowIngestionPipeline._order_pipeline_nodes(nodes),
            node_executors=[CustomAuditExecutor()],
        )
        result = pipeline.run("Custom node registry should be extensible.")

        audit_node = result.node_results[-1]
        self.assertTrue(audit_node.success)
        self.assertEqual(audit_node.message, "Audit node executed.")
        self.assertEqual(audit_node.output["metadata"]["audit_node"], "audit")

    def test_enhancer_tasks_update_runtime_context(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="enhance",
            ),
            IngestionPipelineNodeConfig(
                node_id="enhance",
                node_type="enhancer",
                config={
                    "tasks": [
                        {"type": "context_enhance", "value": "增强: {{text}}"},
                        {"type": "keywords", "value": '["保险", "理赔"]'},
                        {"type": "questions", "value": "怎么理赔？\n需要哪些材料？"},
                        {"type": "metadata", "value": '{"department":"claims","category":"policy"}'},
                    ]
                },
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run("保险理赔资料说明")

        enhance_node = next(node for node in result.node_results if node.node_id == "enhance")
        self.assertEqual(enhance_node.message, "Enhancer completed 4 tasks.")
        self.assertEqual(enhance_node.output["enhancedText"], "增强: 保险理赔资料说明")
        self.assertEqual(enhance_node.output["keywords"], ["保险", "理赔"])
        self.assertEqual(enhance_node.output["questions"], ["怎么理赔？", "需要哪些材料？"])
        self.assertEqual(enhance_node.output["metadata"]["department"], "claims")
        self.assertEqual(enhance_node.output["metadata"]["category"], "policy")

    def test_enricher_tasks_attach_document_metadata_and_chunk_metadata(self) -> None:
        from schemas.knowledge import IngestionPipelineNodeConfig
        from modules.ingestion import RetriFlowIngestionPipeline

        nodes = [
            IngestionPipelineNodeConfig(
                node_id="parse",
                node_type="parser",
                next_node_id="chunk",
            ),
            IngestionPipelineNodeConfig(
                node_id="chunk",
                node_type="chunker",
                next_node_id="enrich",
                config={"strategy": "fixed_size", "chunkSize": 12, "overlapSize": 0},
            ),
            IngestionPipelineNodeConfig(
                node_id="enrich",
                node_type="enricher",
                config={
                    "tasks": [
                        {"type": "keywords", "value": "chunk, metadata"},
                        {"type": "summary", "value": "摘要 {{chunkIndex}}: {{text}}"},
                        {"type": "metadata", "value": '{"riskLevel":"low"}'},
                    ]
                },
            ),
        ]

        pipeline = RetriFlowIngestionPipeline.from_pipeline_nodes(nodes)
        result = pipeline.run("abcdefghijklmno", metadata={"department": "claims"})

        enrich_node = next(node for node in result.node_results if node.node_id == "enrich")
        first_metadata = enrich_node.output["chunkMetadata"][0]
        self.assertEqual(enrich_node.message, f"Enricher completed {len(result.chunk_documents) * 3} tasks for {len(result.chunk_documents)} chunks.")
        self.assertEqual(first_metadata["department"], "claims")
        self.assertEqual(first_metadata["keywords"], ["chunk", "metadata"])
        self.assertTrue(first_metadata["summary"].startswith("摘要 0:"))
        self.assertEqual(first_metadata["riskLevel"], "low")
        self.assertEqual(result.chunk_documents[0].metadata["riskLevel"], "low")

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
