import json
from pathlib import Path

from fastapi import HTTPException, status
from langchain_core.documents import Document

from core.config import get_settings
from core.state import get_connection
from domain.document_parser import RetriFlowDocumentParserService
from domain.ingestion import IngestionPipelineNodeResult, RetriFlowIngestionPipeline
from domain.vector_store import VectorChunkRecord, resolve_vector_store
from schemas.document_structure import (
    HeadingBlock,
    ImageCaptionBlock,
    ParagraphBlock,
    StructuredDocument,
    TableBlock,
)
from schemas.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    KnowledgeChunkItem,
    KnowledgeChunkListResponse,
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentItem,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentStructuredBlockItem,
    KnowledgeDocumentStructuredBlockListResponse,
    StructuredTableCellItem,
    StructuredTableRowItem,
)


class RetriFlowKnowledgeService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.document_parser_service = RetriFlowDocumentParserService()
        self.vector_store = resolve_vector_store()

    def list_knowledge_bases(self) -> KnowledgeBaseListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, name, product, document_count
                from knowledge_bases
                order by id
                """
            ).fetchall()
        return KnowledgeBaseListResponse(items=[self._to_knowledge_base(row) for row in rows])

    def create_knowledge_base(self, request: KnowledgeBaseCreateRequest) -> KnowledgeBaseItem:
        with get_connection() as connection:
            next_index = connection.execute("select count(*) from knowledge_bases").fetchone()[0] + 1
            knowledge_base_id = f"kb-{next_index}"
            connection.execute(
                """
                insert into knowledge_bases (id, name, product, document_count)
                values (?, ?, ?, ?)
                """,
                (knowledge_base_id, request.name, "RetriFlow", 0),
            )
            self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
            connection.commit()

        return KnowledgeBaseItem(
            id=knowledge_base_id,
            name=request.name,
            product="RetriFlow",
            document_count=0,
        )

    def list_documents(self, knowledge_base_id: str) -> KnowledgeDocumentListResponse:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, knowledge_base_id, title, source_type, status, created_at
                from knowledge_documents
                where knowledge_base_id = ?
                order by id
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
        pipeline_result = self._build_ingestion_pipeline(
            strategy=request.chunk_strategy,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            recursive_separators=request.recursive_separators or None,
        ).run(
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
    ) -> KnowledgeDocumentItem:
        self._ensure_knowledge_base_exists(knowledge_base_id)
        try:
            parsed_result = self.document_parser_service.parse_upload(filename, content_bytes, content_type)
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

        structured_source_documents = self._build_source_documents_from_structured_document(parsed_result.structured_document)
        resolved_document_type = document_type or self._infer_upload_document_type(parsed_result.structured_document)
        pipeline_result = self._build_ingestion_pipeline(
            strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            recursive_separators=recursive_separators,
        ).run(
            parsed_result.ingestion_text,
            document_type=resolved_document_type,
            metadata={
                "source_type": "upload",
                "file_name": parsed_result.structured_document.file_name,
                "content_type": parsed_result.structured_document.content_type,
            },
            source_documents=structured_source_documents,
        )
        merged_nodes = self._resequence_node_results(parsed_result.node_results + pipeline_result.node_results)
        return self._persist_document(
            knowledge_base_id=knowledge_base_id,
            title=parsed_result.title,
            source_type="upload",
            normalized_content=pipeline_result.normalized_text,
            chunk_documents=pipeline_result.chunk_documents,
            node_results=merged_nodes,
            structured_document=parsed_result.structured_document,
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
                    heading_path=json.loads(row["heading_path_json"] or "[]"),
                    level=row["level"],
                    text=row["text"],
                    headers=json.loads(row["headers_json"] or "[]"),
                    rows=rows,
                    row_count=row["row_count"],
                    column_count=row["column_count"],
                    caption=row["caption"],
                    created_at=self._serialize_timestamp(row["created_at"]),
                )
            )

        return KnowledgeDocumentStructuredBlockListResponse(items=items)

    def _persist_document(
        self,
        knowledge_base_id: str,
        title: str,
        source_type: str,
        normalized_content: str,
        chunk_documents: list[Document],
        node_results: list[IngestionPipelineNodeResult],
        structured_document: StructuredDocument | None = None,
    ) -> KnowledgeDocumentItem:
        vector_records: list[VectorChunkRecord] = []
        with get_connection() as connection:
            cursor = connection.execute(
                """
                insert into knowledge_documents (knowledge_base_id, title, source_type, content, status)
                values (?, ?, ?, ?, ?)
                returning id
                """,
                (knowledge_base_id, title, source_type, normalized_content, "indexed"),
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
                        metadata=dict(chunk_document.metadata),
                    )
                )

            if structured_document is not None:
                self._persist_structured_document(connection, knowledge_base_id, document_id, structured_document)

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
                    len(chunk_documents),
                    "RetriFlow ingestion pipeline completed.",
                ),
            )
            task_id = int(task_cursor.fetchone()[0])
            connection.executemany(
                """
                insert into ingestion_task_nodes (task_id, node_type, node_order, success, message, duration_ms)
                values (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        task_id,
                        node_result.node_type,
                        node_result.node_order,
                        int(node_result.success),
                        node_result.message,
                        node_result.duration_ms,
                    )
                    for node_result in node_results
                ],
            )

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
            self._sync_knowledge_base_route_profile(connection, knowledge_base_id)
            connection.commit()

            row = connection.execute(
                """
                select id, knowledge_base_id, title, source_type, status, created_at
                from knowledge_documents
                where id = ?
                """,
                (document_id,),
            ).fetchone()

        self.vector_store.upsert_chunk_records(vector_records)
        return self._to_document(row)

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
    def _resequence_node_results(node_results: list[IngestionPipelineNodeResult]) -> list[IngestionPipelineNodeResult]:
        return [
            IngestionPipelineNodeResult(
                node_type=node_result.node_type,
                node_order=index,
                success=node_result.success,
                message=node_result.message,
                duration_ms=node_result.duration_ms,
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
    ) -> RetriFlowIngestionPipeline:
        return RetriFlowIngestionPipeline(
            strategy=strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            recursive_separators=recursive_separators,
        )

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
        )

    @staticmethod
    def _to_document(row) -> KnowledgeDocumentItem:
        return KnowledgeDocumentItem(
            id=row["id"],
            knowledge_base_id=row["knowledge_base_id"],
            title=row["title"],
            source_type=row["source_type"],
            status=row["status"],
            created_at=RetriFlowKnowledgeService._serialize_timestamp(row["created_at"]),
        )

    @staticmethod
    def _to_chunk(row) -> KnowledgeChunkItem:
        return KnowledgeChunkItem(
            id=row["id"],
            knowledge_base_id=row["knowledge_base_id"],
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            char_count=row["char_count"],
            strategy=row["strategy"] or "recursive",
            document_type=row["document_type"] or "manual",
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=RetriFlowKnowledgeService._serialize_timestamp(row["created_at"]),
        )

    @staticmethod
    def _serialize_timestamp(value) -> str:
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

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
