import json
import re
from dataclasses import dataclass, field
from math import sqrt
from typing import Any

from fastapi import HTTPException, status
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.state import get_connection
from infra.embeddings import RetriFlowEmbeddingService
from schemas.knowledge import (
    IngestionPipelineCreateRequest,
    IngestionPipelineItem,
    IngestionPipelineListResponse,
    IngestionPipelineNodeConfig,
    IngestionPipelineUpdateRequest,
    IngestionTaskItem,
    IngestionTaskListResponse,
    IngestionTaskNodeItem,
    IngestionTaskNodeListResponse,
)


@dataclass
class IngestionPipelineNodeResult:
    node_type: str
    node_order: int
    success: bool
    message: str
    duration_ms: int
    node_id: str = ""
    status: str = "success"
    error_message: str = ""
    output: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionPipelineResult:
    normalized_text: str
    segments: list[str]
    chunks: list[str]
    source_documents: list[Document]
    chunk_documents: list[Document]
    node_results: list[IngestionPipelineNodeResult]


@dataclass
class IngestionRuntimeContext:
    document_type: str
    strategy: str
    segment_count: int
    chunk_count: int
    raw_text: str
    chunks: list[str]
    metadata: dict[str, Any]
    mime_type: str | None = None
    source: dict[str, Any] = field(default_factory=dict)
    enhanced_text: str | None = None
    keywords: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)

    def to_condition_context(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type,
            "documentType": self.document_type,
            "strategy": self.strategy,
            "segment_count": self.segment_count,
            "segmentCount": self.segment_count,
            "chunk_count": self.chunk_count,
            "chunkCount": self.chunk_count,
            "raw_text": self.raw_text,
            "rawText": self.raw_text,
            "mime_type": self.mime_type,
            "mimeType": self.mime_type,
            "source": self.source,
            "enhanced_text": self.enhanced_text,
            "enhancedText": self.enhanced_text,
            "keywords": self.keywords,
            "questions": self.questions,
            "metadata": self.metadata,
        }


class RetriFlowIngestionPipeline:
    DEFAULT_RECURSIVE_SEPARATORS = ["\n\n", "\n", "。 ", "！ ", "？ ", ". ", "! ", "? ", " ", ""]
    AUTO_STRATEGY_MAP = {
        "knowledge_base": "recursive",
        "manual": "recursive",
        "faq": "recursive",
        "qa": "recursive",
        "contract": "semantic_embedding",
        "legal": "semantic_embedding",
        "ocr": "overlap",
        "log": "fixed",
        "html": "recursive",
        "mixed_knowledge": "hybrid_recursive_semantic",
    }

    def __init__(
        self,
        chunk_size: int = 120,
        chunk_overlap: int = 10,
        strategy: str = "auto",
        recursive_separators: list[str] | None = None,
        chunk_config: dict | None = None,
        min_chunk_size: int = 8,
        embedding_service: RetriFlowEmbeddingService | None = None,
        pipeline_nodes: list[IngestionPipelineNodeConfig] | None = None,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self.chunk_config = chunk_config or {}
        normalized_strategy = "fixed" if strategy == "fixed_size" else strategy
        self.requested_strategy = strategy
        self.strategy = normalized_strategy
        self.chunk_size = self._config_int("chunkSize", self._config_int("chunk_size", chunk_size))
        self.chunk_overlap = self._config_int("overlapSize", self._config_int("overlapChars", self._config_int("chunk_overlap", chunk_overlap)))
        self.recursive_separators = recursive_separators or list(self.DEFAULT_RECURSIVE_SEPARATORS)
        self.min_chunk_size = min_chunk_size
        base_embedding_service = embedding_service or RetriFlowEmbeddingService()
        if embedding_provider or embedding_model:
            self.embedding_service = base_embedding_service.with_runtime_defaults(
                provider_name=embedding_provider,
                model_name=embedding_model,
            )
        else:
            self.embedding_service = base_embedding_service
        self.pipeline_nodes = pipeline_nodes or []
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model

    @classmethod
    def from_pipeline_nodes(
        cls,
        nodes: list[IngestionPipelineNodeConfig],
        *,
        fallback_strategy: str = "structure_aware",
        fallback_chunk_size: int = 512,
        fallback_chunk_overlap: int = 0,
        embedding_service: RetriFlowEmbeddingService | None = None,
    ) -> "RetriFlowIngestionPipeline":
        cls._validate_pipeline_nodes(nodes)
        ordered_nodes = cls._order_pipeline_nodes(nodes)
        chunker_config = cls._first_node_config(ordered_nodes, {"chunker", "splitter"})
        embedder_config = cls._first_node_config(ordered_nodes, {"embedder", "embedding"})
        strategy = str(chunker_config.get("strategy") or fallback_strategy)
        chunk_size = cls._extract_config_int(
            chunker_config,
            keys=("chunkSize", "chunk_size", "targetChars", "target_chars"),
            default=fallback_chunk_size,
        )
        chunk_overlap = cls._extract_config_int(
            chunker_config,
            keys=("overlapSize", "chunk_overlap", "overlapChars", "overlap_chars"),
            default=fallback_chunk_overlap,
        )
        return cls(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strategy=strategy,
            chunk_config=dict(chunker_config),
            embedding_service=embedding_service,
            pipeline_nodes=ordered_nodes,
            embedding_provider=str(embedder_config.get("provider") or "") or None,
            embedding_model=str(embedder_config.get("model") or "") or None,
        )

    def run(
        self,
        content: str,
        document_type: str | None = None,
        metadata: dict | None = None,
        source_documents: list[Document] | None = None,
    ) -> IngestionPipelineResult:
        resolved_document_type = (document_type or "manual").strip().lower() or "manual"
        resolved_strategy = self._resolve_strategy(resolved_document_type)
        normalized_text = (
            self._normalize_structure_text(content)
            if resolved_strategy == "structure_aware"
            else self._normalize_text(content)
        )

        if source_documents is not None:
            normalized_source_documents = self._normalize_source_documents(
                source_documents=source_documents,
                document_type=resolved_document_type,
                metadata=metadata or {},
                preserve_structure=resolved_strategy == "structure_aware",
            )
            segments = [document.page_content for document in normalized_source_documents]
        else:
            segments = self._segment_text(normalized_text)
            if resolved_strategy == "structure_aware":
                normalized_source_documents = [
                    Document(
                        page_content=normalized_text,
                        metadata={
                            **(metadata or {}),
                            "document_type": resolved_document_type,
                            "segment_index": 0,
                            "segment_count": len(segments) or 1,
                        },
                    )
                ]
            else:
                normalized_source_documents = self._build_source_documents(
                    segments=segments,
                    document_type=resolved_document_type,
                    metadata=metadata or {},
                )

        chunk_documents = self._chunk_documents(
            source_documents=normalized_source_documents,
            strategy=resolved_strategy,
            document_type=resolved_document_type,
        )
        chunk_documents = self._postprocess_chunks(
            chunk_documents=chunk_documents,
            strategy=resolved_strategy,
            document_type=resolved_document_type,
        )
        chunks = [document.page_content for document in chunk_documents]

        return IngestionPipelineResult(
            normalized_text=normalized_text,
            segments=segments,
            chunks=chunks,
            source_documents=normalized_source_documents,
            chunk_documents=chunk_documents,
            node_results=self._build_node_results(
                segment_count=len(segments),
                chunk_count=len(chunks),
                strategy=resolved_strategy,
                document_type=resolved_document_type,
                normalized_text=normalized_text,
                chunks=chunks,
                metadata=metadata or {},
            ),
        )

    def _build_node_results(
        self,
        *,
        segment_count: int,
        chunk_count: int,
        strategy: str,
        document_type: str,
        normalized_text: str,
        chunks: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> list[IngestionPipelineNodeResult]:
        if self.pipeline_nodes:
            results: list[IngestionPipelineNodeResult] = []
            runtime_context = self._build_runtime_context(
                document_type=document_type,
                strategy=strategy,
                segment_count=segment_count,
                chunk_count=chunk_count,
                normalized_text=normalized_text,
                chunks=chunks,
                metadata=metadata or {},
            )
            condition_context = runtime_context.to_condition_context()
            for node_order, node in enumerate(self.pipeline_nodes, start=1):
                condition_passed = self._evaluate_node_condition(node.condition, condition_context)
                status = "success" if condition_passed else "skipped"
                message = (
                    self._pipeline_node_message(
                        node=node,
                        segment_count=segment_count,
                        chunk_count=chunk_count,
                        strategy=strategy,
                    )
                    if condition_passed
                    else "Skipped: condition not satisfied"
                )
                results.append(
                    IngestionPipelineNodeResult(
                        node_type=node.node_type,
                        node_order=node_order,
                        success=True,
                        message=message,
                        duration_ms=1 if condition_passed else 0,
                        node_id=node.node_id,
                        status=status,
                        output=self._pipeline_node_output(
                            node=node,
                            context=runtime_context,
                        ),
                    )
                )
            return results

        return [
            IngestionPipelineNodeResult(
                node_type="normalize",
                node_order=1,
                success=True,
                message="Normalized source text and preserved paragraph boundaries.",
                duration_ms=1,
                node_id="normalize",
                output={"rawText": normalized_text, "metadata": metadata or {}},
            ),
            IngestionPipelineNodeResult(
                node_type="segment",
                node_order=2,
                success=True,
                message=f"Derived {segment_count} semantic segments from source text.",
                duration_ms=1,
                node_id="segment",
                output={"segmentCount": segment_count},
            ),
            IngestionPipelineNodeResult(
                node_type="chunk",
                node_order=3,
                success=True,
                message=f"Generated {chunk_count} chunks using {strategy} strategy.",
                duration_ms=1,
                node_id="chunk",
                output={"chunkCount": chunk_count, "chunks": chunks},
            ),
            IngestionPipelineNodeResult(
                node_type="index",
                node_order=4,
                success=True,
                message="Indexed chunks into the local retrieval store.",
                duration_ms=1,
                node_id="index",
                output={"settings": {"store": "local"}, "chunkCount": chunk_count, "chunks": chunks},
            ),
        ]

    @staticmethod
    def _build_runtime_context(
        *,
        document_type: str,
        strategy: str,
        segment_count: int,
        chunk_count: int,
        normalized_text: str,
        chunks: list[str],
        metadata: dict[str, Any],
    ) -> IngestionRuntimeContext:
        source = {
            "type": metadata.get("source_type") or metadata.get("sourceType"),
            "location": metadata.get("source_location") or metadata.get("sourceLocation") or metadata.get("path"),
            "fileName": metadata.get("file_name") or metadata.get("fileName") or metadata.get("filename"),
        }
        source = {key: value for key, value in source.items() if value not in (None, "")}
        keywords = metadata.get("keywords") if isinstance(metadata.get("keywords"), list) else []
        questions = metadata.get("questions") if isinstance(metadata.get("questions"), list) else []
        return IngestionRuntimeContext(
            document_type=document_type,
            strategy=strategy,
            segment_count=segment_count,
            chunk_count=chunk_count,
            raw_text=normalized_text,
            chunks=chunks,
            metadata=dict(metadata),
            mime_type=metadata.get("mime_type") or metadata.get("mimeType"),
            source=source,
            enhanced_text=metadata.get("enhanced_text") or metadata.get("enhancedText"),
            keywords=list(keywords),
            questions=list(questions),
        )

    def _pipeline_node_message(
        self,
        *,
        node: IngestionPipelineNodeConfig,
        segment_count: int,
        chunk_count: int,
        strategy: str,
    ) -> str:
        node_type = node.node_type.strip().lower()
        if node_type in {"parser", "parse", "fetcher"}:
            return f"Parsed source content through node {node.node_id}."
        if node_type in {"cleaner", "extractor", "normalize", "normalizer"}:
            return f"Prepared {segment_count} source segments through node {node.node_id}."
        if node_type in {"chunker", "splitter"}:
            return f"Generated {chunk_count} chunks using {strategy} strategy through node {node.node_id}."
        if node_type in {"embedder", "embedding"}:
            model = self.embedding_model or str(node.config.get("model") or "default")
            provider = self.embedding_provider or str(node.config.get("provider") or "default")
            return f"Prepared embedding step with {provider}/{model} through node {node.node_id}."
        if node_type in {"indexer", "index"}:
            store = str(node.config.get("store") or "local")
            return f"Prepared index step for {store} through node {node.node_id}."
        return f"Executed pipeline node {node.node_id}."

    @staticmethod
    def _pipeline_node_output(
        *,
        node: IngestionPipelineNodeConfig,
        context: IngestionRuntimeContext,
    ) -> dict[str, Any]:
        node_type = node.node_type.strip().lower()
        if node_type in {"fetcher"}:
            output: dict[str, Any] = {"source": context.source, "mimeType": context.mime_type}
            raw_bytes_base64 = context.metadata.get("rawBytesBase64")
            raw_bytes_length = context.metadata.get("rawBytesLength")
            if raw_bytes_length is not None:
                output["rawBytesLength"] = raw_bytes_length
            if raw_bytes_base64 is not None:
                output["rawBytesBase64"] = raw_bytes_base64
            return output
        if node_type in {"parser", "parse"}:
            return {
                "mimeType": context.mime_type,
                "rawText": context.raw_text,
                "document": context.metadata.get("document"),
            }
        if node_type in {"cleaner", "extractor", "normalize", "normalizer"}:
            return {"segmentCount": context.segment_count, "metadata": context.metadata}
        if node_type in {"enhancer"}:
            return {
                "enhancedText": context.enhanced_text,
                "keywords": context.keywords,
                "questions": context.questions,
                "metadata": context.metadata,
            }
        if node_type in {"chunker", "splitter", "enricher"}:
            return {"chunkCount": len(context.chunks), "chunks": context.chunks}
        if node_type in {"indexer", "index"}:
            return {"settings": dict(node.config), "chunkCount": len(context.chunks), "chunks": context.chunks}
        if node_type in {"embedder", "embedding"}:
            return {"settings": dict(node.config), "chunkCount": len(context.chunks)}
        return {
            "mimeType": context.mime_type,
            "rawText": context.raw_text,
            "enhancedText": context.enhanced_text,
            "keywords": context.keywords,
            "questions": context.questions,
            "metadata": context.metadata,
            "chunks": context.chunks,
        }

    @classmethod
    def _evaluate_node_condition(cls, condition: str, context: dict[str, Any]) -> bool:
        raw_condition = (condition or "").strip()
        if not raw_condition:
            return True
        try:
            parsed_condition = json.loads(raw_condition)
        except json.JSONDecodeError:
            lowered = raw_condition.lower()
            if lowered in {"true", "false"}:
                return lowered == "true"
            return True
        return cls._evaluate_condition_node(parsed_condition, context)

    @classmethod
    def _evaluate_condition_node(cls, node: Any, context: dict[str, Any]) -> bool:
        if node is None:
            return True
        if isinstance(node, bool):
            return node
        if isinstance(node, str):
            lowered = node.strip().lower()
            if lowered in {"true", "false"}:
                return lowered == "true"
            return True
        if not isinstance(node, dict):
            return True
        if "all" in node:
            rules = node.get("all")
            return all(cls._evaluate_condition_node(item, context) for item in rules) if isinstance(rules, list) else True
        if "any" in node:
            rules = node.get("any")
            return any(cls._evaluate_condition_node(item, context) for item in rules) if isinstance(rules, list) else True
        if "not" in node:
            return not cls._evaluate_condition_node(node.get("not"), context)
        if "field" in node:
            left = cls._read_context_path(context, str(node.get("field") or ""))
            right = node.get("value")
            operator = str(node.get("operator") or "eq").lower()
            return cls._compare_condition_values(left, right, operator)
        return True

    @staticmethod
    def _read_context_path(context: dict[str, Any], path: str) -> Any:
        if not path:
            return None
        if path in context:
            return context[path]
        current: Any = context
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
                continue
            current = getattr(current, part, None)
            if current is None:
                return None
        return current

    @staticmethod
    def _compare_condition_values(left: Any, right: Any, operator: str) -> bool:
        normalized_left = left.strip() if isinstance(left, str) else left
        normalized_right = right.strip() if isinstance(right, str) else right
        if operator == "ne":
            return normalized_left != normalized_right
        if operator == "in":
            if isinstance(normalized_right, list):
                return normalized_left in normalized_right
            if isinstance(normalized_left, list):
                return normalized_right in normalized_left
            return normalized_left == normalized_right
        if operator == "contains":
            if isinstance(normalized_left, str):
                return str(normalized_right) in normalized_left
            if isinstance(normalized_left, list):
                return normalized_right in normalized_left
            return False
        if operator == "exists":
            return normalized_left is not None
        if operator == "not_exists":
            return normalized_left is None
        if operator in {"gt", "gte", "lt", "lte"}:
            try:
                left_number = float(normalized_left)
                right_number = float(normalized_right)
            except (TypeError, ValueError):
                return False
            if operator == "gt":
                return left_number > right_number
            if operator == "gte":
                return left_number >= right_number
            if operator == "lt":
                return left_number < right_number
            return left_number <= right_number
        if operator == "regex":
            if normalized_left is None or normalized_right is None:
                return False
            return re.fullmatch(str(normalized_right), str(normalized_left)) is not None
        return normalized_left == normalized_right

    @staticmethod
    def _order_pipeline_nodes(nodes: list[IngestionPipelineNodeConfig]) -> list[IngestionPipelineNodeConfig]:
        if not nodes:
            return []

        by_id = {node.node_id: node for node in nodes if node.node_id}
        pointed_to = {node.next_node_id for node in nodes if node.next_node_id}
        start = next((node for node in nodes if node.node_id not in pointed_to), nodes[0])
        ordered: list[IngestionPipelineNodeConfig] = []
        seen: set[str] = set()
        current: IngestionPipelineNodeConfig | None = start
        while current is not None and current.node_id not in seen:
            ordered.append(current)
            seen.add(current.node_id)
            current = by_id.get(current.next_node_id)
        return ordered

    @staticmethod
    def _validate_pipeline_nodes(nodes: list[IngestionPipelineNodeConfig]) -> None:
        by_id = {node.node_id: node for node in nodes if node.node_id}
        for node in nodes:
            next_node_id = (node.next_node_id or "").strip()
            if next_node_id and next_node_id not in by_id:
                raise ValueError(f"pipeline node {node.node_id} references missing next node {next_node_id}")

        visited: set[str] = set()
        for node_id in by_id:
            if node_id in visited:
                continue
            path: set[str] = set()
            current = node_id
            while current:
                if current in path:
                    raise ValueError(f"pipeline contains a cycle at node {current}")
                path.add(current)
                visited.add(current)
                node = by_id.get(current)
                if node is None:
                    break
                current = (node.next_node_id or "").strip()

    @staticmethod
    def _first_node_config(
        nodes: list[IngestionPipelineNodeConfig],
        node_types: set[str],
    ) -> dict:
        for node in nodes:
            if node.node_type.strip().lower() in node_types:
                return dict(node.config)
        return {}

    @staticmethod
    def _extract_config_int(
        config: dict,
        *,
        keys: tuple[str, ...],
        default: int,
    ) -> int:
        for key in keys:
            if key not in config:
                continue
            try:
                return int(config[key])
            except (TypeError, ValueError):
                continue
        return default

    def _resolve_strategy(self, document_type: str) -> str:
        if self.strategy != "auto":
            return self.strategy
        return self.AUTO_STRATEGY_MAP.get(document_type, "recursive")

    @staticmethod
    def _normalize_text(content: str) -> str:
        raw = content.replace("\r\n", "\n").replace("\r", "\n")
        paragraphs = []
        for paragraph in raw.split("\n\n"):
            merged = " ".join(line.strip() for line in paragraph.splitlines() if line.strip()).strip()
            if merged:
                paragraphs.append(merged)

        if paragraphs:
            return "\n\n".join(paragraphs)

        return " ".join(raw.split())

    @staticmethod
    def _normalize_structure_text(content: str) -> str:
        raw = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in raw.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

    @staticmethod
    def _segment_text(content: str) -> list[str]:
        if not content:
            return [""]

        segments = [segment.strip() for segment in content.split("\n\n") if segment.strip()]
        return segments or [content]

    @staticmethod
    def _build_source_documents(
        segments: list[str],
        document_type: str,
        metadata: dict,
    ) -> list[Document]:
        segment_count = len(segments)
        base_metadata = dict(metadata)
        base_metadata["document_type"] = document_type

        documents = [
            Document(
                page_content=segment,
                metadata={
                    **base_metadata,
                    "segment_index": index,
                    "segment_count": segment_count,
                },
            )
            for index, segment in enumerate(segments)
        ]
        return documents or [
            Document(
                page_content="",
                metadata={
                    **base_metadata,
                    "segment_index": 0,
                    "segment_count": 1,
                },
            )
        ]

    @classmethod
    def _normalize_source_documents(
        cls,
        source_documents: list[Document],
        document_type: str,
        metadata: dict,
        preserve_structure: bool = False,
    ) -> list[Document]:
        normalized_documents: list[Document] = []
        segment_count = len(source_documents) or 1
        for index, source_document in enumerate(source_documents):
            page_content = (
                cls._normalize_structure_text(source_document.page_content)
                if preserve_structure
                else cls._normalize_text(source_document.page_content)
            )
            if not page_content:
                continue
            normalized_metadata = {
                **metadata,
                **dict(source_document.metadata),
                "document_type": document_type,
                "segment_index": dict(source_document.metadata).get("segment_index", index),
                "segment_count": segment_count,
            }
            normalized_documents.append(
                Document(
                    page_content=page_content,
                    metadata=normalized_metadata,
                )
            )

        return normalized_documents or cls._build_source_documents(
            segments=[""],
            document_type=document_type,
            metadata=metadata,
        )

    def _chunk_documents(
        self,
        source_documents: list[Document],
        strategy: str,
        document_type: str,
    ) -> list[Document]:
        if strategy == "fixed":
            fixed_overlap = self.chunk_overlap if self.requested_strategy == "fixed_size" or "overlapSize" in self.chunk_config else 0
            chunk_documents = self._fixed_chunk_documents(source_documents, overlap=fixed_overlap)
        elif strategy == "structure_aware":
            chunk_documents = self._structure_aware_chunk_documents(source_documents)
        elif strategy == "overlap":
            chunk_documents = self._fixed_chunk_documents(source_documents, overlap=self.chunk_overlap)
        elif strategy == "semantic_embedding":
            chunk_documents = self._semantic_chunk_documents(source_documents)
        elif strategy == "hybrid_recursive_semantic":
            chunk_documents = self._hybrid_recursive_semantic_chunk_documents(source_documents)
        else:
            chunk_documents = self._recursive_chunk_documents(source_documents)

        if not chunk_documents:
            chunk_documents = [
                Document(
                    page_content="",
                    metadata={
                        "segment_index": 0,
                        "segment_count": 1,
                        "document_type": document_type,
                    },
                )
            ]

        for chunk_index, document in enumerate(chunk_documents):
            document.metadata["chunk_index"] = chunk_index
            document.metadata["chunk_count"] = len(chunk_documents)
            document.metadata["strategy"] = strategy
            document.metadata["document_type"] = document_type

        return chunk_documents

    def _recursive_chunk_documents(self, source_documents: list[Document]) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.recursive_separators,
            keep_separator=False,
            add_start_index=True,
        )
        return [
            Document(page_content=document.page_content.strip(), metadata=dict(document.metadata))
            for document in splitter.split_documents(source_documents)
            if document.page_content.strip()
        ]

    def _fixed_chunk_documents(self, source_documents: list[Document], overlap: int) -> list[Document]:
        documents: list[Document] = []
        if self.chunk_size == -1:
            return [
                Document(page_content=document.page_content.strip(), metadata={**dict(document.metadata), "start_index": 0})
                for document in source_documents
                if document.page_content.strip()
            ]
        step = max(1, self.chunk_size - overlap)
        for source_document in source_documents:
            text = source_document.page_content.strip()
            if not text:
                continue
            start = 0
            while start < len(text):
                chunk_text = text[start : start + self.chunk_size].strip()
                if chunk_text:
                    metadata = dict(source_document.metadata)
                    metadata["start_index"] = start
                    documents.append(Document(page_content=chunk_text, metadata=metadata))
                start += step
        return documents

    def _structure_aware_chunk_documents(self, source_documents: list[Document]) -> list[Document]:
        target_chars = self._config_int("targetChars", 1400)
        overlap_chars = self._config_int("overlapChars", 0)
        max_chars = self._config_int("maxChars", 1800)
        min_chars = self._config_int("minChars", 600)
        documents: list[Document] = []
        chunk_index = 0

        for source_document in source_documents:
            blocks = self._expand_long_structure_blocks(
                self._markdown_blocks(source_document.page_content),
                target_chars=target_chars,
                max_chars=max_chars,
            )
            current_blocks: list[str] = []
            current_length = 0
            block_start = 0

            for block_index, block in enumerate(blocks):
                candidate_length = len("\n\n".join([*current_blocks, block])) if current_blocks else len(block)
                should_flush = (
                    current_blocks
                    and candidate_length > max_chars
                )
                if should_flush:
                    chunk_text = "\n\n".join(current_blocks).strip()
                    documents.append(
                        Document(
                            page_content=chunk_text,
                            metadata={
                                **dict(source_document.metadata),
                                "block_start": block_start,
                                "block_end": block_index - 1,
                                "structure_chunk": chunk_index,
                            },
                        )
                    )
                    chunk_index += 1
                    current_blocks = self._overlap_tail(current_blocks, overlap_chars)
                    block_start = max(0, block_index - len(current_blocks))
                    current_length = len("\n\n".join(current_blocks))

                current_blocks.append(block)
                current_length = len("\n\n".join(current_blocks))

            if current_blocks:
                documents.append(
                    Document(
                        page_content="\n\n".join(current_blocks).strip(),
                        metadata={
                            **dict(source_document.metadata),
                            "block_start": block_start,
                            "block_end": len(blocks) - 1,
                            "structure_chunk": chunk_index,
                        },
                    )
                )
                chunk_index += 1

        return documents

    def _semantic_chunk_documents(self, source_documents: list[Document]) -> list[Document]:
        semantic_documents: list[Document] = []
        group_index = 0
        for source_document in source_documents:
            units = self._semantic_units(source_document.page_content)
            if not units:
                continue

            unit_vectors = self.embedding_service.embed_texts(units)
            current_group = [units[0]]
            current_vector = unit_vectors[0] if unit_vectors else []

            for unit_index, unit in enumerate(units[1:], start=1):
                unit_vector = unit_vectors[unit_index] if unit_index < len(unit_vectors) else []
                if self._vector_similarity(current_vector, unit_vector) >= 0.72:
                    current_group.append(unit)
                    current_vector = self._merge_vectors(current_vector, unit_vector)
                    continue

                semantic_documents.append(
                    Document(
                        page_content=" ".join(current_group).strip(),
                        metadata={
                            **dict(source_document.metadata),
                            "semantic_group": group_index,
                        },
                    )
                )
                group_index += 1
                current_group = [unit]
                current_vector = unit_vector

            if current_group:
                semantic_documents.append(
                    Document(
                        page_content=" ".join(current_group).strip(),
                        metadata={
                            **dict(source_document.metadata),
                            "semantic_group": group_index,
                        },
                    )
                )
                group_index += 1

        return semantic_documents

    def _hybrid_recursive_semantic_chunk_documents(self, source_documents: list[Document]) -> list[Document]:
        coarse_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(self.chunk_size * 2, self.chunk_size + 1),
            chunk_overlap=self.chunk_overlap,
            separators=self.recursive_separators,
            keep_separator=False,
            add_start_index=True,
        )
        coarse_documents = coarse_splitter.split_documents(source_documents)
        results: list[Document] = []
        for parent_index, coarse_document in enumerate(coarse_documents):
            semantic_docs = self._semantic_chunk_documents(
                [Document(page_content=coarse_document.page_content, metadata=dict(coarse_document.metadata))]
            )
            for semantic_doc in semantic_docs:
                semantic_doc.metadata["parent_segment_index"] = parent_index
                results.append(semantic_doc)
        return results

    def _postprocess_chunks(
        self,
        chunk_documents: list[Document],
        strategy: str,
        document_type: str,
    ) -> list[Document]:
        if not chunk_documents:
            return []

        processed: list[Document] = []
        buffer_document: Document | None = None
        for document in chunk_documents:
            text = document.page_content.strip()
            metadata = dict(document.metadata)
            metadata["postprocessed"] = True
            candidate = Document(page_content=text, metadata=metadata)

            if len(text) < self.min_chunk_size and processed:
                previous = processed.pop()
                merged_text = f"{previous.page_content} {text}".strip()
                processed.append(
                    Document(
                        page_content=merged_text,
                        metadata={**dict(previous.metadata), "postprocessed": True},
                    )
                )
                continue

            if len(text) < self.min_chunk_size and buffer_document is None:
                buffer_document = candidate
                continue

            if buffer_document is not None:
                merged_text = f"{buffer_document.page_content} {text}".strip()
                processed.append(
                    Document(
                        page_content=merged_text,
                        metadata={
                            **metadata,
                            "postprocessed": True,
                            "document_type": document_type,
                            "strategy": strategy,
                        },
                    )
                )
                buffer_document = None
                continue

            if strategy != "structure_aware" and self.chunk_size > 0 and len(text) > self.chunk_size * 2:
                processed.extend(self._fixed_chunk_documents([candidate], overlap=self.chunk_overlap))
                continue

            processed.append(candidate)

        if buffer_document is not None:
            processed.append(buffer_document)

        normalized = [document for document in processed if document.page_content.strip()]
        if strategy == "structure_aware":
            normalized = self._merge_small_structure_chunks(normalized)
        for chunk_index, document in enumerate(normalized):
            document.metadata["postprocessed"] = True
            document.metadata["strategy"] = strategy
            document.metadata["document_type"] = document_type
            document.metadata["chunk_index"] = chunk_index
            document.metadata["chunk_count"] = len(normalized)
        return normalized

    def _merge_small_structure_chunks(self, chunk_documents: list[Document]) -> list[Document]:
        if not chunk_documents:
            return []
        max_chars = self._config_int("maxChars", 1800)
        min_chars = self._config_int("minChars", 600)
        merged: list[Document] = []
        for document in chunk_documents:
            if (
                merged
                and len(document.page_content) < min_chars
                and len(f"{merged[-1].page_content}\n\n{document.page_content}") <= max_chars
            ):
                previous = merged.pop()
                merged.append(
                    Document(
                        page_content=f"{previous.page_content}\n\n{document.page_content}".strip(),
                        metadata={**dict(previous.metadata), "merged_small_structure_chunk": True},
                    )
                )
                continue
            if (
                len(document.page_content) < min_chars
                and len(chunk_documents) > 1
                and not merged
            ):
                merged.append(document)
                continue
            merged.append(document)

        if len(merged) >= 2 and len(merged[0].page_content) < min_chars:
            combined = f"{merged[0].page_content}\n\n{merged[1].page_content}".strip()
            if len(combined) <= max_chars:
                first = merged.pop(0)
                second = merged.pop(0)
                merged.insert(
                    0,
                    Document(
                        page_content=combined,
                        metadata={**dict(first.metadata), **dict(second.metadata), "merged_small_structure_chunk": True},
                    ),
                )
        return merged

    @staticmethod
    def _semantic_units(content: str) -> list[str]:
        paragraphs = [paragraph.strip() for paragraph in content.split("\n\n") if paragraph.strip()]
        if len(paragraphs) > 1:
            return paragraphs

        sentences = re.split(r"(?<=[。！？!?\.])\s*", content.strip())
        cleaned = [sentence.strip() for sentence in sentences if sentence.strip()]
        return cleaned or ([content.strip()] if content.strip() else [])

    @staticmethod
    def _vector_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0

        numerator = sum(left_item * right_item for left_item, right_item in zip(left, right, strict=False))
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _merge_vectors(left: list[float], right: list[float]) -> list[float]:
        if not left:
            return list(right)
        if not right:
            return list(left)
        return [(left_item + right_item) / 2.0 for left_item, right_item in zip(left, right, strict=False)]

    def _config_int(self, key: str, default: int) -> int:
        value = self.chunk_config.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _markdown_blocks(content: str) -> list[str]:
        blocks: list[str] = []
        current: list[str] = []
        in_code_fence = False

        for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            stripped = line.strip()
            if stripped.startswith("```"):
                current.append(line)
                in_code_fence = not in_code_fence
                if not in_code_fence:
                    blocks.append("\n".join(current).strip())
                    current = []
                continue
            if in_code_fence:
                current.append(line)
                continue
            if stripped.startswith("#"):
                if current:
                    blocks.append("\n".join(current).strip())
                    current = []
                blocks.append(line.strip())
                continue
            if not stripped:
                if current:
                    blocks.append("\n".join(current).strip())
                    current = []
                continue
            current.append(line)

        if current:
            blocks.append("\n".join(current).strip())
        return [block for block in blocks if block]

    @classmethod
    def _expand_long_structure_blocks(cls, blocks: list[str], *, target_chars: int, max_chars: int) -> list[str]:
        if max_chars <= 0:
            return blocks
        expanded: list[str] = []
        for block in blocks:
            if len(block) <= max_chars or block.lstrip().startswith("```"):
                expanded.append(block)
                continue
            expanded.extend(cls._split_block_on_natural_boundaries(block, target_chars=target_chars, max_chars=max_chars))
        return [block for block in expanded if block.strip()]

    @classmethod
    def _split_block_on_natural_boundaries(cls, block: str, *, target_chars: int, max_chars: int) -> list[str]:
        units = cls._natural_boundary_units(block)
        if len(units) <= 1 and len(block) > max_chars:
            units = cls._recursive_boundary_units(block, max_chars=max_chars)

        pieces: list[str] = []
        current: list[str] = []
        target = max(1, min(target_chars, max_chars))
        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            candidate = " ".join([*current, unit]).strip()
            if current and len(candidate) > target:
                pieces.append(" ".join(current).strip())
                if len(unit) > max_chars:
                    pieces.extend(cls._recursive_boundary_units(unit, max_chars=max_chars))
                    current = []
                else:
                    current = [unit]
                continue
            if not current and len(unit) > max_chars:
                pieces.extend(cls._recursive_boundary_units(unit, max_chars=max_chars))
                current = []
                continue
            current.append(unit)

        if current:
            pieces.append(" ".join(current).strip())
        return pieces or [block]

    @staticmethod
    def _natural_boundary_units(block: str) -> list[str]:
        normalized = block.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip() for line in normalized.split("\n") if line.strip()]
        if len(lines) > 1:
            return lines
        units = re.findall(r".+?(?:[。！？!?\.；;]+|$)", normalized.strip(), flags=re.S)
        return [unit.strip() for unit in units if unit.strip()]

    @classmethod
    def _recursive_boundary_units(cls, text: str, *, max_chars: int) -> list[str]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chars,
            chunk_overlap=0,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", "，", ",", " ", ""],
            keep_separator=True,
        )
        return [document.page_content.strip() for document in splitter.create_documents([text]) if document.page_content.strip()]

    @staticmethod
    def _overlap_tail(blocks: list[str], overlap_chars: int) -> list[str]:
        if overlap_chars <= 0:
            return []
        tail: list[str] = []
        total = 0
        for block in reversed(blocks):
            if total >= overlap_chars:
                break
            tail.insert(0, block)
            total += len(block)
        return tail

    @staticmethod
    def _split_long_block(block: str, *, max_chars: int, overlap_chars: int) -> list[str]:
        if max_chars <= 0:
            return [block]
        parts: list[str] = []
        step = max(1, max_chars - max(0, overlap_chars))
        start = 0
        while start < len(block):
            part = block[start : start + max_chars].strip()
            if part:
                parts.append(part)
            start += step
        return parts


class RetriFlowIngestionService:
    def list_pipelines(self) -> IngestionPipelineListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, name, description, nodes_json, owner, created_at, updated_at
                from ingestion_pipelines
                order by id asc
                """
            ).fetchall()

        return IngestionPipelineListResponse(items=[self._to_pipeline(row) for row in rows])

    def create_pipeline(self, request: IngestionPipelineCreateRequest) -> IngestionPipelineItem:
        nodes_json = json.dumps([node.model_dump() for node in request.nodes], ensure_ascii=False)
        with get_connection() as connection:
            row = connection.execute(
                """
                insert into ingestion_pipelines (name, description, nodes_json, owner)
                values (?, ?, ?, ?)
                returning id, name, description, nodes_json, owner, created_at, updated_at
                """,
                (
                    request.name.strip(),
                    request.description.strip(),
                    nodes_json,
                    request.owner.strip() or "admin",
                ),
            ).fetchone()
            connection.commit()
        return self._to_pipeline(row)

    def update_pipeline(self, pipeline_id: int, request: IngestionPipelineUpdateRequest) -> IngestionPipelineItem:
        mapping = request.model_dump(exclude_unset=True)
        if not mapping:
            return self._get_pipeline_or_404(pipeline_id)

        fields: list[str] = []
        values: list[object] = []
        if "name" in mapping:
            fields.append("name = ?")
            values.append(str(mapping["name"]).strip())
        if "description" in mapping:
            fields.append("description = ?")
            values.append(str(mapping["description"] or "").strip())
        if "nodes" in mapping:
            fields.append("nodes_json = ?")
            nodes = mapping["nodes"] or []
            values.append(json.dumps(nodes, ensure_ascii=False))
        if "owner" in mapping:
            fields.append("owner = ?")
            values.append(str(mapping["owner"] or "").strip() or "admin")

        fields.append("updated_at = current_timestamp")
        with get_connection() as connection:
            existing = connection.execute(
                "select id from ingestion_pipelines where id = ?",
                (pipeline_id,),
            ).fetchone()
            if existing is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion pipeline not found")
            connection.execute(
                f"update ingestion_pipelines set {', '.join(fields)} where id = ?",
                [*values, pipeline_id],
            )
            connection.commit()
            row = connection.execute(
                """
                select id, name, description, nodes_json, owner, created_at, updated_at
                from ingestion_pipelines
                where id = ?
                """,
                (pipeline_id,),
            ).fetchone()
        return self._to_pipeline(row)

    def delete_pipeline(self, pipeline_id: int) -> None:
        with get_connection() as connection:
            row = connection.execute(
                "select id from ingestion_pipelines where id = ?",
                (pipeline_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion pipeline not found")
            connection.execute("delete from ingestion_pipelines where id = ?", (pipeline_id,))
            connection.commit()

    def _get_pipeline_or_404(self, pipeline_id: int) -> IngestionPipelineItem:
        with get_connection() as connection:
            row = connection.execute(
                """
                select id, name, description, nodes_json, owner, created_at, updated_at
                from ingestion_pipelines
                where id = ?
                """,
                (pipeline_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion pipeline not found")
        return self._to_pipeline(row)

    def list_tasks(self, *, document_id: int | None = None) -> IngestionTaskListResponse:
        with get_connection() as connection:
            if document_id is None:
                rows = connection.execute(
                    """
                    select id, knowledge_base_id, document_id, source_type, status, chunk_count, message, created_at
                    from ingestion_tasks
                    order by id desc
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    select id, knowledge_base_id, document_id, source_type, status, chunk_count, message, created_at
                    from ingestion_tasks
                    where document_id = ?
                    order by id desc
                    """,
                    (document_id,),
                ).fetchall()

        return IngestionTaskListResponse(items=[self._to_task(row) for row in rows])

    def list_task_nodes(self, task_id: int) -> IngestionTaskNodeListResponse:
        with get_connection() as connection:
            task_row = connection.execute(
                "select id from ingestion_tasks where id = ?",
                (task_id,),
            ).fetchone()
            if task_row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion task not found")

            rows = connection.execute(
                """
                select
                    id,
                    task_id,
                    node_id,
                    node_type,
                    node_order,
                    success,
                    status,
                    message,
                    error_message,
                    output_json,
                    duration_ms,
                    created_at
                from ingestion_task_nodes
                where task_id = ?
                order by node_order
                """,
                (task_id,),
            ).fetchall()

        return IngestionTaskNodeListResponse(items=[self._to_task_node(row) for row in rows])

    @staticmethod
    def _to_pipeline(row) -> IngestionPipelineItem:
        nodes = RetriFlowIngestionService._parse_pipeline_nodes(row["nodes_json"])
        return IngestionPipelineItem(
            id=int(row["id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            nodes=nodes,
            node_count=len(nodes),
            owner=str(row["owner"]),
            created_at=RetriFlowIngestionService._serialize_timestamp(row["created_at"]),
            updated_at=RetriFlowIngestionService._serialize_timestamp(row["updated_at"]),
        )

    @staticmethod
    def _parse_pipeline_nodes(value) -> list[IngestionPipelineNodeConfig]:
        if isinstance(value, list):
            raw_nodes = value
        else:
            try:
                raw_nodes = json.loads(str(value or "[]"))
            except json.JSONDecodeError:
                raw_nodes = []
        return [
            IngestionPipelineNodeConfig.model_validate(node)
            for node in raw_nodes
            if isinstance(node, dict)
        ]

    @staticmethod
    def _to_task(row) -> IngestionTaskItem:
        return IngestionTaskItem(
            id=row["id"],
            knowledge_base_id=row["knowledge_base_id"],
            document_id=row["document_id"],
            source_type=row["source_type"],
            status=row["status"],
            chunk_count=row["chunk_count"],
            message=row["message"],
            created_at=RetriFlowIngestionService._serialize_timestamp(row["created_at"]),
        )

    @staticmethod
    def _to_task_node(row) -> IngestionTaskNodeItem:
        return IngestionTaskNodeItem(
            id=row["id"],
            task_id=row["task_id"],
            node_id=row["node_id"],
            node_type=row["node_type"],
            node_order=row["node_order"],
            success=bool(row["success"]),
            status=row["status"],
            message=row["message"],
            error_message=row["error_message"],
            output=RetriFlowIngestionService._parse_json_field(row["output_json"], default={}),
            duration_ms=row["duration_ms"],
            created_at=RetriFlowIngestionService._serialize_timestamp(row["created_at"]),
        )

    @staticmethod
    def _parse_json_field(value, *, default):
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return default
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return default
        return default

    @staticmethod
    def _serialize_timestamp(value) -> str:
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
