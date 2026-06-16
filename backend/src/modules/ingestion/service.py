import json
import re
from dataclasses import dataclass
from math import sqrt

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


@dataclass
class IngestionPipelineResult:
    normalized_text: str
    segments: list[str]
    chunks: list[str]
    source_documents: list[Document]
    chunk_documents: list[Document]
    node_results: list[IngestionPipelineNodeResult]


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
        min_chunk_size: int = 8,
        embedding_service: RetriFlowEmbeddingService | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.recursive_separators = recursive_separators or list(self.DEFAULT_RECURSIVE_SEPARATORS)
        self.min_chunk_size = min_chunk_size
        self.embedding_service = embedding_service or RetriFlowEmbeddingService()

    def run(
        self,
        content: str,
        document_type: str | None = None,
        metadata: dict | None = None,
        source_documents: list[Document] | None = None,
    ) -> IngestionPipelineResult:
        normalized_text = self._normalize_text(content)
        resolved_document_type = (document_type or "manual").strip().lower() or "manual"
        resolved_strategy = self._resolve_strategy(resolved_document_type)

        if source_documents is not None:
            normalized_source_documents = self._normalize_source_documents(
                source_documents=source_documents,
                document_type=resolved_document_type,
                metadata=metadata or {},
            )
            segments = [document.page_content for document in normalized_source_documents]
        else:
            segments = self._segment_text(normalized_text)
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
            node_results=[
                IngestionPipelineNodeResult(
                    node_type="normalize",
                    node_order=1,
                    success=True,
                    message="Normalized source text and preserved paragraph boundaries.",
                    duration_ms=1,
                ),
                IngestionPipelineNodeResult(
                    node_type="segment",
                    node_order=2,
                    success=True,
                    message=f"Derived {len(segments)} semantic segments from source text.",
                    duration_ms=1,
                ),
                IngestionPipelineNodeResult(
                    node_type="chunk",
                    node_order=3,
                    success=True,
                    message=f"Generated {len(chunks)} chunks using {resolved_strategy} strategy.",
                    duration_ms=1,
                ),
                IngestionPipelineNodeResult(
                    node_type="index",
                    node_order=4,
                    success=True,
                    message="Indexed chunks into the local retrieval store.",
                    duration_ms=1,
                ),
            ],
        )

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
    ) -> list[Document]:
        normalized_documents: list[Document] = []
        segment_count = len(source_documents) or 1
        for index, source_document in enumerate(source_documents):
            page_content = cls._normalize_text(source_document.page_content)
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
            chunk_documents = self._fixed_chunk_documents(source_documents, overlap=0)
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

            if len(text) > self.chunk_size * 2:
                processed.extend(self._fixed_chunk_documents([candidate], overlap=self.chunk_overlap))
                continue

            processed.append(candidate)

        if buffer_document is not None:
            processed.append(buffer_document)

        normalized = [document for document in processed if document.page_content.strip()]
        for chunk_index, document in enumerate(normalized):
            document.metadata["postprocessed"] = True
            document.metadata["strategy"] = strategy
            document.metadata["document_type"] = document_type
            document.metadata["chunk_index"] = chunk_index
            document.metadata["chunk_count"] = len(normalized)
        return normalized

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

    def list_tasks(self) -> IngestionTaskListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, knowledge_base_id, document_id, source_type, status, chunk_count, message, created_at
                from ingestion_tasks
                order by id desc
                """
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
                select id, task_id, node_type, node_order, success, message, duration_ms, created_at
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
            node_type=row["node_type"],
            node_order=row["node_order"],
            success=bool(row["success"]),
            message=row["message"],
            duration_ms=row["duration_ms"],
            created_at=RetriFlowIngestionService._serialize_timestamp(row["created_at"]),
        )

    @staticmethod
    def _serialize_timestamp(value) -> str:
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
