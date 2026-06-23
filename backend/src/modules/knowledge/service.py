import json
from pathlib import Path

from fastapi import HTTPException, status
from langchain_core.documents import Document

from core.config import get_settings
from core.state import get_connection
from infra.document_parser import RetriFlowDocumentParserService
from infra.storage import resolve_file_storage
from infra.vector_store import VectorChunkRecord, resolve_vector_store
from modules.ingestion import IngestionPipelineNodeResult, RetriFlowIngestionPipeline
from schemas.document_structure import (
    HeadingBlock,
    ImageCaptionBlock,
    PageBreakBlock,
    ParagraphBlock,
    StructuredDocument,
    TableCell,
    TableBlock,
    TableRow,
)
from schemas.knowledge import (
    IngestionPipelineNodeConfig,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    KnowledgeBaseUpdateRequest,
    KnowledgeChunkItem,
    KnowledgeChunkListResponse,
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentItem,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentPreviewResponse,
    KnowledgeDocumentReindexRequest,
    KnowledgeDocumentUpdateRequest,
    KnowledgeDocumentStructuredBlockItem,
    KnowledgeDocumentStructuredBlockListResponse,
    StructuredTableCellItem,
    StructuredTableRowItem,
    KnowledgeBaseRouteProfileItem,
    KnowledgeBaseRouteProfileUpdateRequest,
)


class RetriFlowKnowledgeService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.document_parser_service = RetriFlowDocumentParserService()
        self.file_storage = resolve_file_storage()
        self.vector_store = resolve_vector_store()

    def list_knowledge_bases(self) -> KnowledgeBaseListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select
                    kb.id,
                    kb.name,
                    kb.product,
                    kb.document_count,
                    kb.embedding_model,
                    kb.collection_name,
                    kb.owner,
                    kb.created_at as kb_created_at,
                    kb.updated_at as kb_updated_at,
                    min(kd.created_at) as created_at,
                    max(coalesce(kd.vector_indexed_at, kd.created_at)) as updated_at
                from knowledge_bases kb
                left join knowledge_documents kd on kd.knowledge_base_id = kb.id
                group by kb.id, kb.name, kb.product, kb.document_count, kb.embedding_model, kb.collection_name, kb.owner, kb.created_at, kb.updated_at
                order by kb.id
                """
            ).fetchall()
        return KnowledgeBaseListResponse(items=[self._to_knowledge_base(row) for row in rows])

    def create_knowledge_base(self, request: KnowledgeBaseCreateRequest) -> KnowledgeBaseItem:
        with get_connection() as connection:
            existing_ids = connection.execute("select id from knowledge_bases").fetchall()
            next_index = self._next_numeric_suffix([str(row["id"]) for row in existing_ids], prefix="kb-")
            knowledge_base_id = f"kb-{next_index}"
            collection_name = request.collection_name.strip() or knowledge_base_id.replace("-", "")
            connection.execute(
                """
                insert into knowledge_bases (id, name, product, document_count, embedding_model, collection_name, owner, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, current_timestamp)
                """,
                (
                    knowledge_base_id,
                    request.name.strip(),
                    "RetriFlow",
                    0,
                    request.embedding_model.strip() or "Qwen/Qwen3-Embedding-8B",
                    collection_name,
                    "admin",
                ),
            )
            self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
            connection.commit()

        return KnowledgeBaseItem(
            id=knowledge_base_id,
            name=request.name.strip(),
            product="RetriFlow",
            document_count=0,
            embedding_model=request.embedding_model.strip() or "Qwen/Qwen3-Embedding-8B",
            collection_name=collection_name,
        )

    def update_knowledge_base(
        self,
        knowledge_base_id: str,
        request: KnowledgeBaseUpdateRequest,
    ) -> KnowledgeBaseItem:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        with get_connection() as connection:
            current = connection.execute(
                """
                select id, name, product, document_count, embedding_model, collection_name, owner, created_at, updated_at
                from knowledge_bases
                where id = ?
                """,
                (knowledge_base_id,),
            ).fetchone()
            name = request.name.strip() if request.name is not None else str(current["name"])
            embedding_model = (
                request.embedding_model.strip()
                if request.embedding_model is not None and request.embedding_model.strip()
                else str(current["embedding_model"] or "Qwen/Qwen3-Embedding-8B")
            )
            collection_name = (
                request.collection_name.strip()
                if request.collection_name is not None
                else str(current["collection_name"] or knowledge_base_id.replace("-", ""))
            )
            connection.execute(
                """
                update knowledge_bases
                set name = ?,
                    embedding_model = ?,
                    collection_name = ?,
                    updated_at = current_timestamp
                where id = ?
                """,
                (name, embedding_model, collection_name, knowledge_base_id),
            )
            self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
            connection.commit()
        return self._get_knowledge_base(knowledge_base_id)

    def delete_knowledge_base(self, knowledge_base_id: str) -> None:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        with get_connection() as connection:
            document_rows = connection.execute(
                """
                select id
                from knowledge_documents
                where knowledge_base_id = ?
                """,
                (knowledge_base_id,),
            ).fetchall()

            for row in document_rows:
                document_id = int(row["id"])
                try:
                    self.vector_store.delete_document_records(document_id)
                except Exception:
                    pass
                self._delete_document_children(connection, knowledge_base_id, document_id)

            connection.execute("delete from ingestion_task_nodes where task_id in (select id from ingestion_tasks where knowledge_base_id = ?)", (knowledge_base_id,))
            connection.execute("delete from ingestion_tasks where knowledge_base_id = ?", (knowledge_base_id,))
            connection.execute("delete from knowledge_documents where knowledge_base_id = ?", (knowledge_base_id,))
            connection.execute("delete from knowledge_base_route_profiles where knowledge_base_id = ?", (knowledge_base_id,))
            connection.execute("delete from knowledge_bases where id = ?", (knowledge_base_id,))
            connection.commit()

    def delete_document(self, knowledge_base_id: str, document_id: int) -> None:
        self._ensure_document_exists(knowledge_base_id, document_id)
        with get_connection() as connection:
            source_row = connection.execute(
                "select source_uri from knowledge_documents where knowledge_base_id = ? and id = ?",
                (knowledge_base_id, document_id),
            ).fetchone()
        try:
            self.vector_store.delete_document_records(document_id)
        except Exception:
            pass
        if source_row is not None and source_row["source_uri"]:
            try:
                self.file_storage.delete_by_uri(str(source_row["source_uri"]))
            except Exception:
                pass

        with get_connection() as connection:
            self._delete_document_children(connection, knowledge_base_id, document_id)
            connection.execute(
                "delete from ingestion_task_nodes where task_id in (select id from ingestion_tasks where document_id = ?)",
                (document_id,),
            )
            connection.execute("delete from ingestion_tasks where document_id = ?", (document_id,))
            connection.execute(
                "delete from knowledge_documents where knowledge_base_id = ? and id = ?",
                (knowledge_base_id, document_id),
            )
            self._sync_knowledge_base_document_count(connection, knowledge_base_id)
            connection.commit()

    def update_document(
        self,
        knowledge_base_id: str,
        document_id: int,
        request: KnowledgeDocumentUpdateRequest,
    ) -> KnowledgeDocumentItem:
        self._ensure_document_exists(knowledge_base_id, document_id)
        processing_fields = {
            "document_type",
            "process_mode",
            "pipeline_id",
            "chunk_strategy",
            "chunk_size",
            "chunk_overlap",
            "recursive_separators",
            "chunk_config",
        }
        update_payload = request.model_dump(exclude_unset=True)
        has_processing_update = any(field in update_payload for field in processing_fields)
        with get_connection() as connection:
            if request.title is not None:
                connection.execute(
                    """
                    update knowledge_documents
                    set title = ?
                    where knowledge_base_id = ? and id = ?
                    """,
                    (request.title.strip(), knowledge_base_id, document_id),
                )
                self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
            if has_processing_update:
                row = connection.execute(
                    """
                    select processing_config_json
                    from knowledge_documents
                    where knowledge_base_id = ? and id = ?
                    """,
                    (knowledge_base_id, document_id),
                ).fetchone()
                current_config = self._parse_json_field(row["processing_config_json"] if row else None, default={})
                processing_config = self._build_processing_config(
                    document_type=request.document_type
                    if request.document_type is not None
                    else current_config.get("documentType", "knowledge_base"),
                    process_mode=request.process_mode
                    if request.process_mode is not None
                    else current_config.get("processMode", "chunk_strategy"),
                    pipeline_id=request.pipeline_id
                    if "pipeline_id" in update_payload
                    else current_config.get("pipelineId"),
                    chunk_strategy=request.chunk_strategy
                    if request.chunk_strategy is not None
                    else current_config.get("chunkStrategy", "structure_aware"),
                    chunk_size=request.chunk_size
                    if request.chunk_size is not None
                    else int(current_config.get("chunkSize") or 1400),
                    chunk_overlap=request.chunk_overlap
                    if request.chunk_overlap is not None
                    else int(current_config.get("chunkOverlap") or 0),
                    recursive_separators=request.recursive_separators
                    if request.recursive_separators is not None
                    else list(current_config.get("recursiveSeparators") or []),
                    chunk_config=request.chunk_config
                    if request.chunk_config is not None
                    else dict(current_config.get("chunkConfig") or {}),
                )
                try:
                    self.vector_store.delete_document_records(document_id)
                except Exception:
                    pass
                connection.execute(
                    """
                    delete from knowledge_chunks
                    where knowledge_base_id = ? and document_id = ?
                    """,
                    (knowledge_base_id, document_id),
                )
                connection.execute(
                    """
                    delete from ingestion_tasks
                    where knowledge_base_id = ? and document_id = ?
                    """,
                    (knowledge_base_id, document_id),
                )
                connection.execute(
                    """
                    update knowledge_documents
                    set vector_index_status = ?,
                        vector_chunk_count = ?,
                        vector_indexed_at = ?,
                        processing_config_json = ?
                    where knowledge_base_id = ? and id = ?
                    """,
                    (
                        "pending",
                        0,
                        None,
                        json.dumps(processing_config, ensure_ascii=False),
                        knowledge_base_id,
                        document_id,
                    ),
                )
            if request.enabled is not None:
                connection.execute(
                    """
                    update knowledge_chunks
                    set enabled = ?
                    where knowledge_base_id = ? and document_id = ?
                    """,
                    (int(request.enabled), knowledge_base_id, document_id),
                )
            connection.commit()
        if request.enabled is not None:
            self._sync_document_vector_records(knowledge_base_id, document_id)
        return self._get_document(document_id)

    def preview_document(self, knowledge_base_id: str, document_id: int) -> KnowledgeDocumentPreviewResponse:
        row = self._get_document_row(knowledge_base_id, document_id)
        return KnowledgeDocumentPreviewResponse(
            id=int(row["id"]),
            knowledge_base_id=str(row["knowledge_base_id"]),
            title=str(row["title"]),
            source_type=self._source_type_label(str(row["source_type"])),
            content=str(row["content"] or ""),
            source_uri=row.get("source_uri") or "",
            created_at=self._serialize_timestamp(row["created_at"]),
        )

    def open_document_source(self, knowledge_base_id: str, document_id: int):
        row = self._get_document_row(knowledge_base_id, document_id)
        source_uri = str(row.get("source_uri") or "")
        if not source_uri:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document source file not found",
            )
        try:
            stream = self.file_storage.open_stream(source_uri)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document source file not found",
            ) from exc
        filename = self._filename_from_source_uri(source_uri, fallback=str(row["title"]))
        content_type = self._guess_content_type(filename)
        return stream, filename, content_type

    def list_documents(self, knowledge_base_id: str) -> KnowledgeDocumentListResponse:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        with get_connection() as connection:
            rows = connection.execute(
                """
                select
                    kd.id,
                    kd.knowledge_base_id,
                    kd.title,
                    kd.source_type,
                    kd.source_uri,
                    kd.content,
                    kd.status,
                    kd.vector_index_status,
                    kd.vector_chunk_count,
                    kd.vector_indexed_at,
                    kd.processing_config_json,
                    kd.created_at,
                    min(kc.strategy) as processing_mode,
                    min(kc.document_type) as document_type,
                    min(kc.enabled) as min_enabled
                from knowledge_documents kd
                left join knowledge_chunks kc on kc.document_id = kd.id
                where kd.knowledge_base_id = ?
                group by
                    kd.id,
                    kd.knowledge_base_id,
                    kd.title,
                    kd.source_type,
                    kd.source_uri,
                    kd.content,
                    kd.status,
                    kd.vector_index_status,
                    kd.vector_chunk_count,
                    kd.vector_indexed_at,
                    kd.processing_config_json,
                    kd.created_at
                order by kd.id
                """,
                (knowledge_base_id,),
            ).fetchall()

        return KnowledgeDocumentListResponse(items=[self._to_document(row) for row in rows])

    def create_document(
        self,
        knowledge_base_id: str,
        request: KnowledgeDocumentCreateRequest,
    ) -> KnowledgeDocumentItem:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        pipeline_options = self._build_pipeline_options(
                strategy=request.chunk_strategy,
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
                recursive_separators=request.recursive_separators or None,
                chunk_config=request.chunk_config,
            )
        if request.process_mode == "data_channel":
            pipeline_options["process_mode"] = request.process_mode
            pipeline_options["pipeline_id"] = request.pipeline_id
        pipeline_result = self._build_ingestion_pipeline(**pipeline_options).run(
            request.content,
            document_type=request.document_type,
            metadata={"source_type": request.source_type},
        )
        return self._persist_document(
            knowledge_base_id=knowledge_base_id,
            title=request.title,
            source_type=request.source_type,
            normalized_content=pipeline_result.normalized_text,
            chunk_documents=pipeline_result.chunk_documents,
            node_results=pipeline_result.node_results,
            structured_document=None,
            persist_ingestion_task=request.process_mode == "data_channel",
        )

    def upload_document(
        self,
        knowledge_base_id: str,
        filename: str,
        content_bytes: bytes,
        content_type: str | None = None,
        document_type: str | None = None,
        chunk_strategy: str = "auto",
        chunk_size: int = 600,
        chunk_overlap: int = 120,
        recursive_separators: list[str] | None = None,
        chunk_config: dict | None = None,
        process_mode: str = "chunk_strategy",
        pipeline_id: int | None = None,
    ) -> KnowledgeDocumentItem:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        stored_file = self.file_storage.upload_bytes(content_bytes, filename, content_type)
        with self.file_storage.open_stream(stored_file.uri) as source_stream:
            stored_content_bytes = source_stream.read()
        try:
            parsed_result = self.document_parser_service.parse_upload(filename, stored_content_bytes, content_type)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        return self._persist_uploaded_document(
            knowledge_base_id=knowledge_base_id,
            title=parsed_result.title,
            structured_document=parsed_result.structured_document,
            parsed_content=parsed_result.ingestion_text,
            source_uri=stored_file.uri,
            processing_config=self._build_processing_config(
                document_type=document_type or "knowledge_base",
                process_mode=process_mode,
                pipeline_id=pipeline_id,
                chunk_strategy=chunk_strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                recursive_separators=recursive_separators or [],
                chunk_config=chunk_config or {},
            ),
        )

    def reindex_document(
        self,
        knowledge_base_id: str,
        document_id: int,
        request: KnowledgeDocumentReindexRequest,
    ) -> KnowledgeDocumentItem:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        with get_connection() as connection:
            document_row = connection.execute(
                """
                select
                    id,
                    knowledge_base_id,
                    title,
                    source_type,
                    content,
                    status,
                    vector_index_status,
                    vector_chunk_count,
                    vector_indexed_at,
                    created_at
                from knowledge_documents
                where knowledge_base_id = ? and id = ?
                """,
                (knowledge_base_id, document_id),
            ).fetchone()
            if document_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found",
                )

            current_document_type = self._load_document_type(connection, document_id)
            structured_document = self._load_persisted_structured_document(
                connection=connection,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                title=str(document_row["title"]),
                normalized_content=str(document_row["content"]),
            )

        resolved_document_type = request.document_type or current_document_type
        pipeline_options = self._build_pipeline_options(
                strategy=request.chunk_strategy,
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
                recursive_separators=request.recursive_separators or None,
                chunk_config=request.chunk_config,
            )
        if request.process_mode == "data_channel":
            pipeline_options["process_mode"] = request.process_mode
            pipeline_options["pipeline_id"] = request.pipeline_id
        pipeline = self._build_ingestion_pipeline(**pipeline_options)

        try:
            if structured_document is not None:
                source_documents = self._build_source_documents_from_structured_document(structured_document)
                pipeline_result = pipeline.run(
                    structured_document.text_content or str(document_row["content"]),
                    document_type=resolved_document_type,
                    metadata={
                        "source_type": str(document_row["source_type"]),
                        "file_name": structured_document.file_name,
                        "content_type": structured_document.content_type,
                    },
                    source_documents=source_documents,
                )
            else:
                pipeline_result = pipeline.run(
                    str(document_row["content"]),
                    document_type=resolved_document_type,
                    metadata={"source_type": str(document_row["source_type"])},
                )
        except Exception as exc:
            self._mark_document_index_failed(document_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document chunking failed: {exc}",
            ) from exc

        return self._replace_document_index(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            title=str(document_row["title"]),
            source_type=str(document_row["source_type"]),
            normalized_content=pipeline_result.normalized_text,
            chunk_documents=pipeline_result.chunk_documents,
            node_results=pipeline_result.node_results,
            structured_document=structured_document,
            processing_config=self._build_processing_config(
                document_type=resolved_document_type,
                process_mode=request.process_mode,
                pipeline_id=request.pipeline_id,
                chunk_strategy=request.chunk_strategy,
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
                recursive_separators=request.recursive_separators,
                chunk_config=request.chunk_config,
            ),
            persist_ingestion_task=request.process_mode == "data_channel",
        )

    def import_sample_directory(self, knowledge_base_id: str) -> int:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        sample_dir = Path(self.settings.sample_knowledge_dir)
        if not sample_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sample knowledge directory not found",
            )

        imported_count = 0
        for path in sorted(sample_dir.rglob("*.md")):
            content = path.read_text(encoding="utf-8")
            relative_path = path.relative_to(sample_dir)
            title = relative_path.stem
            source_type = f"sample:{relative_path.parent.as_posix()}" if relative_path.parent.as_posix() != "." else "sample"
            self.create_document(
                knowledge_base_id,
                KnowledgeDocumentCreateRequest(
                    title=title,
                    source_type=source_type,
                    content=content,
                    document_type="knowledge_base",
                    chunk_strategy="auto",
                    chunk_size=600,
                    chunk_overlap=120,
                    chunk_config={},
                ),
            )
            imported_count += 1

        return imported_count

    def list_document_chunks(self, knowledge_base_id: str, document_id: int) -> KnowledgeChunkListResponse:
        self._ensure_document_exists(knowledge_base_id, document_id)
        with get_connection() as connection:
            rows = connection.execute(
                """
                select
                    id,
                    knowledge_base_id,
                    document_id,
                    chunk_index,
                    content,
                    char_count,
                    enabled,
                    strategy,
                    document_type,
                    metadata_json,
                    created_at
                from knowledge_chunks
                where knowledge_base_id = ? and document_id = ?
                order by chunk_index
                """,
                (knowledge_base_id, document_id),
            ).fetchall()

        return KnowledgeChunkListResponse(items=[self._to_chunk(row) for row in rows])

    def update_document_chunk(
        self,
        knowledge_base_id: str,
        document_id: int,
        chunk_id: int,
        *,
        enabled: bool | None = None,
        content: str | None = None,
    ) -> KnowledgeChunkItem:
        self._ensure_document_exists(knowledge_base_id, document_id)
        with get_connection() as connection:
            row = connection.execute(
                """
                select id
                from knowledge_chunks
                where knowledge_base_id = ? and document_id = ? and id = ?
                """,
                (knowledge_base_id, document_id, chunk_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")

            update_parts: list[str] = []
            params: list[object] = []
            if enabled is not None:
                update_parts.append("enabled = ?")
                params.append(int(enabled))
            if content is not None:
                update_parts.extend(["content = ?", "char_count = ?"])
                params.extend([content.strip(), len(content.strip())])

            connection.execute(
                f"""
                update knowledge_chunks
                set {", ".join(update_parts)}
                where knowledge_base_id = ? and document_id = ? and id = ?
                """,
                (*params, knowledge_base_id, document_id, chunk_id),
            )
            connection.commit()

            updated = connection.execute(
                """
                select
                    id,
                    knowledge_base_id,
                    document_id,
                    chunk_index,
                    content,
                    char_count,
                    enabled,
                    strategy,
                    document_type,
                    metadata_json,
                    created_at
                from knowledge_chunks
                where id = ?
                """,
                (chunk_id,),
            ).fetchone()

        self._sync_document_vector_records(knowledge_base_id, document_id)
        return self._to_chunk(updated)

    def update_document_chunk_enabled(
        self,
        knowledge_base_id: str,
        document_id: int,
        chunk_id: int,
        enabled: bool,
    ) -> KnowledgeChunkItem:
        return self.update_document_chunk(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            chunk_id=chunk_id,
            enabled=enabled,
        )

    def update_document_chunks_enabled(
        self,
        knowledge_base_id: str,
        document_id: int,
        chunk_ids: list[int],
        enabled: bool,
    ) -> int:
        self._ensure_document_exists(knowledge_base_id, document_id)
        with get_connection() as connection:
            if chunk_ids:
                placeholders = ",".join("?" for _ in chunk_ids)
                params = [int(enabled), knowledge_base_id, document_id, *chunk_ids]
                cursor = connection.execute(
                    f"""
                    update knowledge_chunks
                    set enabled = ?
                    where knowledge_base_id = ? and document_id = ? and id in ({placeholders})
                    """,
                    params,
                )
            else:
                cursor = connection.execute(
                    """
                    update knowledge_chunks
                    set enabled = ?
                    where knowledge_base_id = ? and document_id = ?
                    """,
                    (int(enabled), knowledge_base_id, document_id),
                )
            connection.commit()
            updated_count = int(getattr(cursor._native_cursor, "rowcount", 0) or 0)

        self._sync_document_vector_records(knowledge_base_id, document_id)
        return updated_count

    def delete_document_chunk(self, knowledge_base_id: str, document_id: int, chunk_id: int) -> None:
        self._ensure_document_exists(knowledge_base_id, document_id)
        with get_connection() as connection:
            row = connection.execute(
                """
                select id
                from knowledge_chunks
                where knowledge_base_id = ? and document_id = ? and id = ?
                """,
                (knowledge_base_id, document_id, chunk_id),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")

            connection.execute(
                """
                delete from knowledge_chunks
                where knowledge_base_id = ? and document_id = ? and id = ?
                """,
                (knowledge_base_id, document_id, chunk_id),
            )
            connection.execute(
                """
                update knowledge_documents
                set vector_chunk_count = (
                    select count(*)
                    from knowledge_chunks
                    where knowledge_base_id = ? and document_id = ?
                )
                where knowledge_base_id = ? and id = ?
                """,
                (knowledge_base_id, document_id, knowledge_base_id, document_id),
            )
            connection.commit()

        self._sync_document_vector_records(knowledge_base_id, document_id)

    def list_document_structured_blocks(
        self,
        knowledge_base_id: str,
        document_id: int,
    ) -> KnowledgeDocumentStructuredBlockListResponse:
        self._ensure_document_exists(knowledge_base_id, document_id)
        with get_connection() as connection:
            block_rows = connection.execute(
                """
                select
                    id,
                    knowledge_base_id,
                    document_id,
                    block_index,
                    block_type,
                    page_number,
                    heading_path_json,
                    level,
                    text,
                    headers_json,
                    row_count,
                    column_count,
                    caption,
                    created_at
                from knowledge_document_blocks
                where knowledge_base_id = ? and document_id = ?
                order by block_index
                """,
                (knowledge_base_id, document_id),
            ).fetchall()

            if not block_rows:
                return KnowledgeDocumentStructuredBlockListResponse(items=[])

            block_ids = [row["id"] for row in block_rows]
            placeholders = ",".join("?" for _ in block_ids)
            cell_rows = connection.execute(
                f"""
                select
                    block_id,
                    row_index,
                    column_index,
                    text,
                    is_header
                from knowledge_document_table_cells
                where block_id in ({placeholders})
                order by block_id, row_index, column_index
                """,
                tuple(block_ids),
            ).fetchall()

        grouped_cells: dict[int, dict[int, list[StructuredTableCellItem]]] = {}
        for row in cell_rows:
            grouped_cells.setdefault(row["block_id"], {}).setdefault(row["row_index"], []).append(
                StructuredTableCellItem(
                    row_index=row["row_index"],
                    column_index=row["column_index"],
                    text=row["text"],
                    is_header=bool(row["is_header"]),
                )
            )

        items: list[KnowledgeDocumentStructuredBlockItem] = []
        for row in block_rows:
            grouped_rows = grouped_cells.get(row["id"], {})
            rows = [
                StructuredTableRowItem(
                    row_index=row_index,
                    cells=cells,
                )
                for row_index, cells in sorted(grouped_rows.items())
            ]
            items.append(
                KnowledgeDocumentStructuredBlockItem(
                    id=row["id"],
                    knowledge_base_id=row["knowledge_base_id"],
                    document_id=row["document_id"],
                    block_index=row["block_index"],
                    block_type=row["block_type"],
                    page_number=row["page_number"],
                    heading_path=self._parse_json_field(row["heading_path_json"], default=[]),
                    level=row["level"],
                    text=row["text"],
                    headers=self._parse_json_field(row["headers_json"], default=[]),
                    rows=rows,
                    row_count=row["row_count"],
                    column_count=row["column_count"],
                    caption=row["caption"],
                    created_at=self._serialize_timestamp(row["created_at"]),
                )
            )

        return KnowledgeDocumentStructuredBlockListResponse(items=items)

    def _replace_document_index(
        self,
        knowledge_base_id: str,
        document_id: int,
        title: str,
        source_type: str,
        normalized_content: str,
        chunk_documents: list[Document],
        node_results: list[IngestionPipelineNodeResult],
        structured_document: StructuredDocument | None = None,
        source_uri: str = "",
        processing_config: dict | None = None,
        persist_ingestion_task: bool = False,
    ) -> KnowledgeDocumentItem:
        try:
            self.vector_store.delete_document_records(document_id)
        except Exception:
            pass

        vector_records: list[VectorChunkRecord] = []
        with get_connection() as connection:
            vector_settings = self._load_knowledge_base_vector_settings(connection, knowledge_base_id)
            self._delete_document_children(connection, knowledge_base_id, document_id)
            connection.execute(
                """
                update knowledge_documents
                set title = ?,
                    source_type = ?,
                    content = ?,
                    status = ?,
                    vector_index_status = ?,
                    vector_chunk_count = ?,
                    vector_indexed_at = ?,
                    processing_config_json = ?
                where knowledge_base_id = ? and id = ?
                """,
                (
                    title,
                    source_type,
                    normalized_content,
                    "indexed",
                    "pending",
                    0,
                    None,
                    json.dumps(processing_config or {}, ensure_ascii=False),
                    knowledge_base_id,
                    document_id,
                ),
            )

            for chunk_index, chunk_document in enumerate(chunk_documents):
                chunk_cursor = connection.execute(
                    """
                    insert into knowledge_chunks (
                        knowledge_base_id,
                        document_id,
                        chunk_index,
                        content,
                        char_count,
                        strategy,
                        document_type,
                        metadata_json
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    returning id
                    """,
                    (
                        knowledge_base_id,
                        document_id,
                        chunk_index,
                        chunk_document.page_content,
                        len(chunk_document.page_content),
                        str(chunk_document.metadata.get("strategy", "recursive")),
                        str(chunk_document.metadata.get("document_type", "manual")),
                        json.dumps(chunk_document.metadata, ensure_ascii=False),
                    ),
                )
                chunk_id = int(chunk_cursor.fetchone()[0])
                vector_records.append(
                    VectorChunkRecord(
                        chunk_id=chunk_id,
                        knowledge_base_id=knowledge_base_id,
                        document_id=document_id,
                        document_title=title,
                        content=chunk_document.page_content,
                        document_type=str(chunk_document.metadata.get("document_type", "manual")),
                        strategy=str(chunk_document.metadata.get("strategy", "recursive")),
                        collection_name=vector_settings["collection_name"],
                        embedding_model=vector_settings["embedding_model"],
                        metadata=dict(chunk_document.metadata),
                    )
                )

            if structured_document is not None:
                self._persist_structured_document(connection, knowledge_base_id, document_id, structured_document)

            if persist_ingestion_task:
                self._persist_ingestion_task(
                    connection=connection,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    source_type=source_type,
                    chunk_count=len(chunk_documents),
                    message="RetriFlow data channel pipeline completed.",
                    node_results=node_results,
                )
            self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
            connection.commit()

        return self._finalize_vector_index(document_id=document_id, vector_records=vector_records)

    def _persist_uploaded_document(
        self,
        knowledge_base_id: str,
        title: str,
        structured_document: StructuredDocument,
        parsed_content: str,
        source_uri: str,
        processing_config: dict,
    ) -> KnowledgeDocumentItem:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                insert into knowledge_documents (
                    knowledge_base_id,
                    title,
                    source_type,
                    source_uri,
                    content,
                    status,
                    vector_index_status,
                    vector_chunk_count,
                    vector_indexed_at,
                    processing_config_json
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                returning id
                """,
                (
                    knowledge_base_id,
                    title,
                    "upload",
                    source_uri,
                    parsed_content,
                    "indexed",
                    "pending",
                    0,
                    None,
                    json.dumps(processing_config, ensure_ascii=False),
                ),
            )
            document_id = int(cursor.fetchone()[0])
            self._persist_structured_document(connection, knowledge_base_id, document_id, structured_document)
            self._sync_knowledge_base_document_count(connection, knowledge_base_id)
            self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
            connection.commit()

        return self._get_document(document_id)

    def _persist_document(
        self,
        knowledge_base_id: str,
        title: str,
        source_type: str,
        normalized_content: str,
        chunk_documents: list[Document],
        node_results: list[IngestionPipelineNodeResult],
        structured_document: StructuredDocument | None = None,
        source_uri: str = "",
        persist_ingestion_task: bool = False,
    ) -> KnowledgeDocumentItem:
        vector_records: list[VectorChunkRecord] = []
        with get_connection() as connection:
            vector_settings = self._load_knowledge_base_vector_settings(connection, knowledge_base_id)
            cursor = connection.execute(
                """
                insert into knowledge_documents (
                    knowledge_base_id,
                    title,
                    source_type,
                    source_uri,
                    content,
                    status,
                    vector_index_status,
                    vector_chunk_count,
                    vector_indexed_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                returning id
                """,
                (
                    knowledge_base_id,
                    title,
                    source_type,
                    source_uri,
                    normalized_content,
                    "indexed",
                    "pending",
                    0,
                    None,
                ),
            )
            document_id = int(cursor.fetchone()[0])

            for chunk_index, chunk_document in enumerate(chunk_documents):
                chunk_cursor = connection.execute(
                    """
                    insert into knowledge_chunks (
                        knowledge_base_id,
                        document_id,
                        chunk_index,
                        content,
                        char_count,
                        strategy,
                        document_type,
                        metadata_json
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    returning id
                    """,
                    (
                        knowledge_base_id,
                        document_id,
                        chunk_index,
                        chunk_document.page_content,
                        len(chunk_document.page_content),
                        str(chunk_document.metadata.get("strategy", "recursive")),
                        str(chunk_document.metadata.get("document_type", "manual")),
                        json.dumps(chunk_document.metadata, ensure_ascii=False),
                    ),
                )
                chunk_id = int(chunk_cursor.fetchone()[0])
                vector_records.append(
                    VectorChunkRecord(
                        chunk_id=chunk_id,
                        knowledge_base_id=knowledge_base_id,
                        document_id=int(document_id),
                        document_title=title,
                        content=chunk_document.page_content,
                        document_type=str(chunk_document.metadata.get("document_type", "manual")),
                        strategy=str(chunk_document.metadata.get("strategy", "recursive")),
                        collection_name=vector_settings["collection_name"],
                        embedding_model=vector_settings["embedding_model"],
                        metadata=dict(chunk_document.metadata),
                    )
                )

            if structured_document is not None:
                self._persist_structured_document(connection, knowledge_base_id, document_id, structured_document)

            if persist_ingestion_task:
                self._persist_ingestion_task(
                    connection=connection,
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    source_type=source_type,
                    chunk_count=len(chunk_documents),
                    message="RetriFlow data channel pipeline completed.",
                    node_results=node_results,
                )
            self._sync_knowledge_base_document_count(connection, knowledge_base_id)
            self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
            connection.commit()

            row = connection.execute(
                """
                select
                    id,
                    knowledge_base_id,
                    title,
                    source_type,
                    source_uri,
                    status,
                    vector_index_status,
                    vector_chunk_count,
                    vector_indexed_at,
                    created_at
                from knowledge_documents
                where id = ?
                """,
                (document_id,),
            ).fetchone()
        return self._finalize_vector_index(document_id=document_id, vector_records=vector_records)

    @staticmethod
    def _persist_ingestion_task(
        *,
        connection,
        knowledge_base_id: str,
        document_id: int,
        source_type: str,
        chunk_count: int,
        message: str,
        node_results: list[IngestionPipelineNodeResult],
    ) -> None:
        task_cursor = connection.execute(
            """
            insert into ingestion_tasks (knowledge_base_id, document_id, source_type, status, chunk_count, message)
            values (?, ?, ?, ?, ?, ?)
            returning id
            """,
            (
                knowledge_base_id,
                document_id,
                source_type,
                "completed",
                chunk_count,
                message,
            ),
        )
        task_id = int(task_cursor.fetchone()[0])
        connection.executemany(
            """
            insert into ingestion_task_nodes (
                task_id,
                node_id,
                node_type,
                node_order,
                success,
                status,
                message,
                error_message,
                output_json,
                duration_ms
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    task_id,
                    node_result.node_id,
                    node_result.node_type,
                    node_result.node_order,
                    int(node_result.success),
                    node_result.status,
                    node_result.message,
                    node_result.error_message,
                    json.dumps(node_result.output, ensure_ascii=False),
                    node_result.duration_ms,
                )
                for node_result in node_results
            ],
        )

    @staticmethod
    def _persist_structured_document(
        connection,
        knowledge_base_id: str,
        document_id: int,
        structured_document: StructuredDocument,
    ) -> None:
        for block in structured_document.blocks:
            headers = block.headers if isinstance(block, TableBlock) else []
            block_cursor = connection.execute(
                """
                insert into knowledge_document_blocks (
                    knowledge_base_id,
                    document_id,
                    block_index,
                    block_type,
                    page_number,
                    heading_path_json,
                    level,
                    text,
                    headers_json,
                    row_count,
                    column_count,
                    caption
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                returning id
                """,
                (
                    knowledge_base_id,
                    document_id,
                    block.block_index,
                    block.block_type,
                    block.page_number,
                    json.dumps(block.heading_path, ensure_ascii=False),
                    getattr(block, "level", None),
                    getattr(block, "text", None),
                    json.dumps(headers, ensure_ascii=False),
                    getattr(block, "row_count", None),
                    getattr(block, "column_count", None),
                    getattr(block, "caption", None),
                ),
            )
            block_id = int(block_cursor.fetchone()[0])

            if isinstance(block, TableBlock):
                for row in block.rows:
                    for cell in row.cells:
                        connection.execute(
                            """
                            insert into knowledge_document_table_cells (
                                block_id,
                                row_index,
                                column_index,
                                text,
                                is_header
                            )
                            values (?, ?, ?, ?, ?)
                            """,
                            (
                                block_id,
                                cell.row_index,
                                cell.column_index,
                                cell.text,
                                int(cell.is_header),
                            ),
                        )

    @staticmethod
    def _delete_document_children(connection, knowledge_base_id: str, document_id: int) -> None:
        block_rows = connection.execute(
            """
            select id
            from knowledge_document_blocks
            where knowledge_base_id = ? and document_id = ?
            """,
            (knowledge_base_id, document_id),
        ).fetchall()
        block_ids = [int(row["id"]) for row in block_rows]
        if block_ids:
            placeholders = ",".join("?" for _ in block_ids)
            connection.execute(
                f"delete from knowledge_document_table_cells where block_id in ({placeholders})",
                tuple(block_ids),
            )
        connection.execute(
            """
            delete from knowledge_document_blocks
            where knowledge_base_id = ? and document_id = ?
            """,
            (knowledge_base_id, document_id),
        )
        connection.execute(
            """
            delete from knowledge_chunks
            where knowledge_base_id = ? and document_id = ?
            """,
            (knowledge_base_id, document_id),
        )

    def _finalize_vector_index(
        self,
        document_id: int,
        vector_records: list[VectorChunkRecord],
    ) -> KnowledgeDocumentItem:
        try:
            self.vector_store.upsert_chunk_records(vector_records)
            vector_index_status = "indexed"
            vector_chunk_count = len(vector_records)
        except Exception:
            vector_index_status = "failed"
            vector_chunk_count = 0

        with get_connection() as connection:
            connection.execute(
                """
                update knowledge_documents
                set vector_index_status = ?,
                    vector_chunk_count = ?,
                    vector_indexed_at = current_timestamp
                where id = ?
                """,
                (vector_index_status, vector_chunk_count, document_id),
            )
            connection.commit()
            row = connection.execute(
                """
                select
                    kd.id,
                    kd.knowledge_base_id,
                    kd.title,
                    kd.source_type,
                    kd.source_uri,
                    kd.content,
                    kd.status,
                    kd.vector_index_status,
                    kd.vector_chunk_count,
                    kd.vector_indexed_at,
                    kd.processing_config_json,
                    kd.created_at,
                    min(kc.strategy) as processing_mode,
                    min(kc.document_type) as document_type,
                    min(kc.enabled) as min_enabled
                from knowledge_documents kd
                left join knowledge_chunks kc on kc.document_id = kd.id
                where kd.id = ?
                group by kd.id, kd.knowledge_base_id, kd.title, kd.source_type, kd.source_uri, kd.content, kd.status, kd.vector_index_status, kd.vector_chunk_count, kd.vector_indexed_at, kd.processing_config_json, kd.created_at
                """,
                (document_id,),
            ).fetchone()
        return self._to_document(row)

    @staticmethod
    def _mark_document_index_failed(document_id: int) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                update knowledge_documents
                set vector_index_status = ?,
                    vector_chunk_count = ?,
                    vector_indexed_at = current_timestamp
                where id = ?
                """,
                ("failed", 0, document_id),
            )
            connection.commit()

    def _get_document(self, document_id: int) -> KnowledgeDocumentItem:
        with get_connection() as connection:
            row = connection.execute(
                """
                select
                    kd.id,
                    kd.knowledge_base_id,
                    kd.title,
                    kd.source_type,
                    kd.source_uri,
                    kd.content,
                    kd.status,
                    kd.vector_index_status,
                    kd.vector_chunk_count,
                    kd.vector_indexed_at,
                    kd.processing_config_json,
                    kd.created_at,
                    min(kc.strategy) as processing_mode,
                    min(kc.document_type) as document_type,
                    min(kc.enabled) as min_enabled
                from knowledge_documents kd
                left join knowledge_chunks kc on kc.document_id = kd.id
                where kd.id = ?
                group by kd.id, kd.knowledge_base_id, kd.title, kd.source_type, kd.source_uri, kd.content, kd.status, kd.vector_index_status, kd.vector_chunk_count, kd.vector_indexed_at, kd.processing_config_json, kd.created_at
                """,
                (document_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return self._to_document(row)

    @staticmethod
    def _get_document_row(knowledge_base_id: str, document_id: int):
        with get_connection() as connection:
            row = connection.execute(
                """
                select
                    id,
                    knowledge_base_id,
                    title,
                    source_type,
                    source_uri,
                    content,
                    created_at
                from knowledge_documents
                where knowledge_base_id = ? and id = ?
                """,
                (knowledge_base_id, document_id),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return row

    @staticmethod
    def _filename_from_source_uri(source_uri: str, *, fallback: str) -> str:
        object_name = source_uri.rsplit("/", 1)[-1]
        if "-" in object_name:
            return object_name.split("-", 1)[1] or fallback
        return object_name or fallback

    @staticmethod
    def _guess_content_type(filename: str) -> str:
        import mimetypes

        return mimetypes.guess_type(filename)[0] or "application/octet-stream"

    def _get_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBaseItem:
        with get_connection() as connection:
            row = connection.execute(
                """
                select
                    kb.id,
                    kb.name,
                    kb.product,
                    kb.document_count,
                    kb.embedding_model,
                    kb.collection_name,
                    kb.owner,
                    kb.created_at as kb_created_at,
                    kb.updated_at as kb_updated_at,
                    min(kd.created_at) as created_at,
                    max(coalesce(kd.vector_indexed_at, kd.created_at)) as updated_at
                from knowledge_bases kb
                left join knowledge_documents kd on kd.knowledge_base_id = kb.id
                where kb.id = ?
                group by kb.id, kb.name, kb.product, kb.document_count, kb.embedding_model, kb.collection_name, kb.owner, kb.created_at, kb.updated_at
                """,
                (knowledge_base_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
        return self._to_knowledge_base(row)

    @staticmethod
    def _load_document_type(connection, document_id: int) -> str:
        row = connection.execute(
            """
            select document_type
            from knowledge_chunks
            where document_id = ?
            order by chunk_index
            limit 1
            """,
            (document_id,),
        ).fetchone()
        if row is None:
            return "manual"
        return str(row["document_type"] or "manual")

    @staticmethod
    def _load_knowledge_base_vector_settings(connection, knowledge_base_id: str) -> dict[str, str]:
        row = connection.execute(
            """
            select embedding_model, collection_name
            from knowledge_bases
            where id = ?
            """,
            (knowledge_base_id,),
        ).fetchone()
        if row is None:
            return {
                "embedding_model": "Qwen/Qwen3-Embedding-8B",
                "collection_name": knowledge_base_id.replace("-", ""),
            }
        return {
            "embedding_model": str(row["embedding_model"] or "Qwen/Qwen3-Embedding-8B"),
            "collection_name": str(row["collection_name"] or knowledge_base_id.replace("-", "")),
        }

    @staticmethod
    def _load_persisted_structured_document(
        connection,
        knowledge_base_id: str,
        document_id: int,
        title: str,
        normalized_content: str,
    ) -> StructuredDocument | None:
        block_rows = connection.execute(
            """
            select
                id,
                block_index,
                block_type,
                page_number,
                heading_path_json,
                level,
                text,
                headers_json,
                row_count,
                column_count,
                caption
            from knowledge_document_blocks
            where knowledge_base_id = ? and document_id = ?
            order by block_index
            """,
            (knowledge_base_id, document_id),
        ).fetchall()
        if not block_rows:
            return None

        block_ids = [int(row["id"]) for row in block_rows]
        placeholders = ",".join("?" for _ in block_ids)
        cell_rows = connection.execute(
            f"""
            select
                block_id,
                row_index,
                column_index,
                text,
                is_header
            from knowledge_document_table_cells
            where block_id in ({placeholders})
            order by block_id, row_index, column_index
            """,
            tuple(block_ids),
        ).fetchall()

        grouped_cells: dict[int, dict[int, list[TableCell]]] = {}
        for row in cell_rows:
            grouped_cells.setdefault(int(row["block_id"]), {}).setdefault(int(row["row_index"]), []).append(
                TableCell(
                    row_index=int(row["row_index"]),
                    column_index=int(row["column_index"]),
                    text=str(row["text"]),
                    is_header=bool(row["is_header"]),
                )
            )

        blocks = []
        for row in block_rows:
            block_id = int(row["id"])
            heading_path = RetriFlowKnowledgeService._parse_json_field(
                row["heading_path_json"],
                default=[],
            )
            block_type = str(row["block_type"])
            if block_type == "heading":
                blocks.append(
                    HeadingBlock(
                        block_index=int(row["block_index"]),
                        page_number=row["page_number"],
                        heading_path=heading_path,
                        level=int(row["level"] or 1),
                        text=str(row["text"] or ""),
                    )
                )
                continue
            if block_type == "paragraph":
                blocks.append(
                    ParagraphBlock(
                        block_index=int(row["block_index"]),
                        page_number=row["page_number"],
                        heading_path=heading_path,
                        text=str(row["text"] or ""),
                    )
                )
                continue
            if block_type == "image_caption":
                blocks.append(
                    ImageCaptionBlock(
                        block_index=int(row["block_index"]),
                        page_number=row["page_number"],
                        heading_path=heading_path,
                        text=str(row["text"] or ""),
                    )
                )
                continue
            if block_type == "page_break":
                blocks.append(
                    PageBreakBlock(
                        block_index=int(row["block_index"]),
                        page_number=row["page_number"],
                        heading_path=heading_path,
                    )
                )
                continue

            table_rows = [
                TableRow(row_index=row_index, cells=cells)
                for row_index, cells in sorted(grouped_cells.get(block_id, {}).items())
            ]
            blocks.append(
                TableBlock(
                    block_index=int(row["block_index"]),
                    page_number=row["page_number"],
                    heading_path=heading_path,
                    headers=RetriFlowKnowledgeService._parse_json_field(
                        row["headers_json"],
                        default=[],
                    ),
                    rows=table_rows,
                    row_count=int(row["row_count"] or 0),
                    column_count=int(row["column_count"] or 0),
                    caption=row["caption"],
                )
            )

        return StructuredDocument(
            file_name=title,
            content_type="application/octet-stream",
            title=title,
            metadata={},
            blocks=blocks,
            text_content=normalized_content,
        )

    @staticmethod
    def _resequence_node_results(node_results: list[IngestionPipelineNodeResult]) -> list[IngestionPipelineNodeResult]:
        return [
            IngestionPipelineNodeResult(
                node_type=node_result.node_type,
                node_order=index,
                success=node_result.success,
                message=node_result.message,
                duration_ms=node_result.duration_ms,
                node_id=node_result.node_id,
                status=node_result.status,
                error_message=node_result.error_message,
                output=node_result.output,
            )
            for index, node_result in enumerate(node_results, start=1)
        ]

    @staticmethod
    def _infer_upload_document_type(structured_document: StructuredDocument) -> str:
        content_type = (structured_document.content_type or "").lower()
        if "html" in content_type:
            return "html"
        if "pdf" in content_type:
            return "knowledge_base"
        if "sheet" in content_type or "excel" in content_type:
            return "knowledge_base"
        return "knowledge_base"

    @staticmethod
    def _build_ingestion_pipeline(
        strategy: str,
        chunk_size: int,
        chunk_overlap: int,
        recursive_separators: list[str] | None = None,
        chunk_config: dict | None = None,
        process_mode: str = "chunk_strategy",
        pipeline_id: int | None = None,
    ) -> RetriFlowIngestionPipeline:
        if process_mode == "data_channel":
            nodes = RetriFlowKnowledgeService._load_ingestion_pipeline_nodes(pipeline_id)
            try:
                return RetriFlowIngestionPipeline.from_pipeline_nodes(
                    nodes,
                    fallback_strategy=strategy,
                    fallback_chunk_size=chunk_size,
                    fallback_chunk_overlap=chunk_overlap,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid ingestion pipeline: {exc}",
                ) from exc
        return RetriFlowIngestionPipeline(
            strategy=strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            recursive_separators=recursive_separators,
            chunk_config=chunk_config,
        )

    @staticmethod
    def _build_pipeline_options(
        *,
        strategy: str,
        chunk_size: int,
        chunk_overlap: int,
        recursive_separators: list[str] | None = None,
        chunk_config: dict | None = None,
    ) -> dict:
        options = {
            "strategy": strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "recursive_separators": recursive_separators,
        }
        if chunk_config:
            options["chunk_config"] = chunk_config
        return options

    @staticmethod
    def _build_processing_config(
        *,
        document_type: str,
        process_mode: str,
        pipeline_id: int | None,
        chunk_strategy: str,
        chunk_size: int,
        chunk_overlap: int,
        recursive_separators: list[str],
        chunk_config: dict,
    ) -> dict:
        return {
            "documentType": document_type,
            "processMode": process_mode,
            "pipelineId": pipeline_id,
            "chunkStrategy": chunk_strategy,
            "chunkSize": chunk_size,
            "chunkOverlap": chunk_overlap,
            "recursiveSeparators": recursive_separators,
            "chunkConfig": chunk_config,
        }

    @staticmethod
    def _load_ingestion_pipeline_nodes(pipeline_id: int | None) -> list[IngestionPipelineNodeConfig]:
        with get_connection() as connection:
            if pipeline_id is None:
                row = connection.execute(
                    """
                    select nodes_json
                    from ingestion_pipelines
                    order by id asc
                    limit 1
                    """
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    select nodes_json
                    from ingestion_pipelines
                    where id = ?
                    """,
                    (pipeline_id,),
                ).fetchone()

        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion pipeline not found")

        try:
            raw_nodes = json.loads(str(row["nodes_json"] or "[]"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid ingestion pipeline") from exc
        return [
            IngestionPipelineNodeConfig.model_validate(node)
            for node in raw_nodes
            if isinstance(node, dict)
        ]

    @staticmethod
    def _build_source_documents_from_structured_document(structured_document: StructuredDocument) -> list[Document]:
        source_documents: list[Document] = []
        for block in structured_document.blocks:
            page_content = RetriFlowKnowledgeService._block_to_text(block)
            if not page_content:
                continue
            source_documents.append(
                Document(
                    page_content=page_content,
                    metadata={
                        "block_type": block.block_type,
                        "block_index": block.block_index,
                        "page_number": block.page_number,
                        "heading_path": list(block.heading_path),
                    },
                )
            )
        return source_documents

    @staticmethod
    def _block_to_text(block) -> str:
        if isinstance(block, (HeadingBlock, ParagraphBlock, ImageCaptionBlock)):
            return getattr(block, "text", "").strip()
        if isinstance(block, TableBlock):
            segments: list[str] = []
            if block.headers:
                segments.append(" | ".join(block.headers))
            for row in block.rows:
                segments.append(" | ".join(cell.text for cell in row.cells))
            return "\n".join(segment for segment in segments if segment.strip()).strip()
        return ""

    def _ensure_knowledge_base_exists(self, knowledge_base_id: str) -> None:
        with get_connection() as connection:
            row = connection.execute(
                "select id from knowledge_bases where id = ?",
                (knowledge_base_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found",
            )

    def _ensure_document_exists(self, knowledge_base_id: str, document_id: int) -> None:
        with get_connection() as connection:
            row = connection.execute(
                """
                select id
                from knowledge_documents
                where knowledge_base_id = ? and id = ?
                """,
                (knowledge_base_id, document_id),
            ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

    @staticmethod
    def _to_knowledge_base(row) -> KnowledgeBaseItem:
        return KnowledgeBaseItem(
            id=row["id"],
            name=row["name"],
            product=row["product"],
            document_count=row["document_count"],
            embedding_model=row.get("embedding_model") or "Qwen/Qwen3-Embedding-8B",
            collection_name=row.get("collection_name") or str(row["id"]).replace("-", ""),
            owner=row.get("owner") or "admin",
            created_at=RetriFlowKnowledgeService._serialize_timestamp(row.get("kb_created_at") or row.get("created_at")),
            updated_at=RetriFlowKnowledgeService._serialize_timestamp(row.get("kb_updated_at") or row.get("updated_at")),
        )

    @staticmethod
    def _to_document(row) -> KnowledgeDocumentItem:
        processing_config = RetriFlowKnowledgeService._parse_json_field(
            row.get("processing_config_json"),
            default={},
        )
        min_enabled = row.get("min_enabled")
        return KnowledgeDocumentItem(
            id=row["id"],
            knowledge_base_id=row["knowledge_base_id"],
            title=row["title"],
            source_type=RetriFlowKnowledgeService._source_type_label(row["source_type"]),
            source_uri=row.get("source_uri") or "",
            processing_mode=row.get("processing_mode") or processing_config.get("processMode") or "auto",
            status=row["status"],
            enabled=True if min_enabled is None else bool(min_enabled),
            vector_index_status=row.get("vector_index_status", "pending"),
            vector_chunk_count=int(row.get("vector_chunk_count", 0) or 0),
            document_type=row.get("document_type") or processing_config.get("documentType") or "knowledge_base",
            size_label=RetriFlowKnowledgeService._format_content_size(row.get("content", "")),
            processing_config=processing_config,
            vector_indexed_at=RetriFlowKnowledgeService._serialize_timestamp(row.get("vector_indexed_at")),
            created_at=RetriFlowKnowledgeService._serialize_timestamp(row["created_at"]),
        )

    @staticmethod
    def _source_type_label(source_type: str) -> str:
        if source_type in {"manual", "upload"}:
            return "local"
        return source_type or "local"

    @staticmethod
    def _format_content_size(content: str | None) -> str:
        byte_size = len((content or "").encode("utf-8"))
        if byte_size < 1024:
            return f"{byte_size} B"
        if byte_size < 1024 * 1024:
            return f"{byte_size / 1024:.1f} KB"
        return f"{byte_size / 1024 / 1024:.1f} MB"

    @staticmethod
    def _to_chunk(row) -> KnowledgeChunkItem:
        return KnowledgeChunkItem(
            id=row["id"],
            knowledge_base_id=row["knowledge_base_id"],
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            char_count=row["char_count"],
            enabled=bool(row.get("enabled", 1)),
            strategy=row["strategy"] or "recursive",
            document_type=row["document_type"] or "manual",
            metadata=RetriFlowKnowledgeService._parse_json_field(row["metadata_json"], default={}),
            created_at=RetriFlowKnowledgeService._serialize_timestamp(row["created_at"]),
        )

    @staticmethod
    def _serialize_timestamp(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            if value.strip().lower() == "none":
                return ""
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _parse_json_field(value, *, default):
        if value is None:
            return default
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return default
            return json.loads(text)
        return default

    @staticmethod
    def _sync_knowledge_base_document_count(connection, knowledge_base_id: str) -> None:
        connection.execute(
            """
            update knowledge_bases
            set document_count = (
                select count(*)
                from knowledge_documents
                where knowledge_base_id = ?
            )
            where id = ?
            """,
            (knowledge_base_id, knowledge_base_id),
        )

    def _sync_document_vector_records(self, knowledge_base_id: str, document_id: int) -> None:
        try:
            self.vector_store.delete_document_records(document_id)
        except Exception:
            pass

        with get_connection() as connection:
            vector_settings = self._load_knowledge_base_vector_settings(connection, knowledge_base_id)
            rows = connection.execute(
                """
                select
                    kc.id as chunk_id,
                    kc.knowledge_base_id,
                    kc.document_id,
                    kd.title as document_title,
                    kc.content,
                    kc.document_type,
                    kc.strategy,
                    kc.metadata_json
                from knowledge_chunks kc
                join knowledge_documents kd on kd.id = kc.document_id
                where kc.knowledge_base_id = ? and kc.document_id = ? and kc.enabled = 1
                order by kc.chunk_index
                """,
                (knowledge_base_id, document_id),
            ).fetchall()

        records = [
            VectorChunkRecord(
                chunk_id=int(row["chunk_id"]),
                knowledge_base_id=str(row["knowledge_base_id"]),
                document_id=int(row["document_id"]),
                document_title=str(row["document_title"]),
                content=str(row["content"]),
                document_type=str(row["document_type"]),
                strategy=str(row["strategy"]),
                collection_name=vector_settings["collection_name"],
                embedding_model=vector_settings["embedding_model"],
                metadata=self._parse_json_field(row["metadata_json"], default={}),
            )
            for row in rows
        ]
        if records:
            try:
                self.vector_store.upsert_chunk_records(records)
            except Exception:
                pass

    @staticmethod
    def _sync_knowledge_base_route_profile(connection, knowledge_base_id: str) -> None:
        kb_row = connection.execute(
            """
            select id, name
            from knowledge_bases
            where id = ?
            """,
            (knowledge_base_id,),
        ).fetchone()
        if kb_row is None:
            return

        doc_rows = connection.execute(
            """
            select title, content
            from knowledge_documents
            where knowledge_base_id = ?
            order by id
            """,
            (knowledge_base_id,),
        ).fetchall()

        name = str(kb_row["name"])
        titles = [str(row["title"]) for row in doc_rows]
        snippets = [str(row["content"])[:240] for row in doc_rows[:4]]
        profile_text = " ".join([name, *titles[:8], *snippets]).strip()
        keywords = RetriFlowKnowledgeService._extract_route_keywords(name=name, titles=titles, snippets=snippets)
        sample_questions = RetriFlowKnowledgeService._build_route_sample_questions(name=name, keywords=keywords)

        connection.execute(
            """
            insert into knowledge_base_route_profiles (
                knowledge_base_id,
                profile_text,
                sample_questions_json,
                keywords_json,
                updated_at
            )
            values (?, ?, ?, ?, current_timestamp)
            on conflict (knowledge_base_id) do update set
                profile_text = excluded.profile_text,
                sample_questions_json = excluded.sample_questions_json,
                keywords_json = excluded.keywords_json,
                updated_at = current_timestamp
            """,
            (
                knowledge_base_id,
                profile_text,
                json.dumps(sample_questions, ensure_ascii=False),
                json.dumps(keywords, ensure_ascii=False),
            ),
        )

    @staticmethod
    def _extract_route_keywords(name: str, titles: list[str], snippets: list[str]) -> list[str]:
        import re

        text = " ".join([name, *titles, *snippets]).lower()
        english_tokens = re.findall(r"[a-z][a-z0-9_-]{2,}", text)
        keywords: list[str] = []
        for token in english_tokens:
            if token not in keywords:
                keywords.append(token)
        return keywords[:16]

    @staticmethod
    def _build_route_sample_questions(name: str, keywords: list[str]) -> list[str]:
        if keywords:
            lead_keyword = keywords[0]
            return [
                f"{name} 主要覆盖什么内容？",
                f"{lead_keyword} 相关流程有哪些？",
            ]
        return [
            f"{name} 主要覆盖什么内容？",
            f"{name} 的常见问题有哪些？",
        ]

    @staticmethod
    def _next_numeric_suffix(existing_ids: list[str], *, prefix: str) -> int:
        max_suffix = 0
        for item in existing_ids:
            if not item.startswith(prefix):
                continue
            suffix = item[len(prefix):]
            if suffix.isdigit():
                max_suffix = max(max_suffix, int(suffix))
        return max_suffix + 1

    def get_route_profile(self, knowledge_base_id: str) -> KnowledgeBaseRouteProfileItem:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        with get_connection() as connection:
            row = connection.execute(
                """
                select knowledge_base_id, profile_text, sample_questions_json, keywords_json, updated_at
                from knowledge_base_route_profiles
                where knowledge_base_id = ?
                """,
                (knowledge_base_id,),
            ).fetchone()
            
            if row is None:
                self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
                connection.commit()
                row = connection.execute(
                    """
                    select knowledge_base_id, profile_text, sample_questions_json, keywords_json, updated_at
                    from knowledge_base_route_profiles
                    where knowledge_base_id = ?
                    """,
                    (knowledge_base_id,),
                ).fetchone()

        return KnowledgeBaseRouteProfileItem(
            knowledge_base_id=row["knowledge_base_id"],
            profile_text=row["profile_text"],
            sample_questions=self._parse_json_field(row["sample_questions_json"], default=[]),
            keywords=self._parse_json_field(row["keywords_json"], default=[]),
            updated_at=self._serialize_timestamp(row["updated_at"]),
        )

    def update_route_profile(
        self,
        knowledge_base_id: str,
        request: KnowledgeBaseRouteProfileUpdateRequest,
    ) -> KnowledgeBaseRouteProfileItem:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        with get_connection() as connection:
            connection.execute(
                """
                insert into knowledge_base_route_profiles (
                    knowledge_base_id,
                    profile_text,
                    sample_questions_json,
                    keywords_json,
                    updated_at
                )
                values (?, ?, ?, ?, current_timestamp)
                on conflict (knowledge_base_id) do update set
                    profile_text = excluded.profile_text,
                    sample_questions_json = excluded.sample_questions_json,
                    keywords_json = excluded.keywords_json,
                    updated_at = current_timestamp
                """,
                (
                    knowledge_base_id,
                    request.profile_text,
                    json.dumps(request.sample_questions, ensure_ascii=False),
                    json.dumps(request.keywords, ensure_ascii=False),
                ),
            )
            connection.commit()
        return self.get_route_profile(knowledge_base_id)
