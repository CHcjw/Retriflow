import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from core.config import get_settings
from core.state import configure_postgres_connection, get_connection
from modules.rag.retrieval.channels import RetrievedChunkRecord, load_chunk_rows
from infra.embeddings import RetriFlowEmbeddingService


@dataclass
class VectorChunkRecord:
    chunk_id: int
    knowledge_base_id: str
    document_id: int
    document_title: str
    content: str
    document_type: str
    strategy: str
    collection_name: str = ""
    embedding_model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class RetriFlowVectorStore(Protocol):
    def upsert_chunk_records(self, records: list[VectorChunkRecord]) -> None:
        ...

    def delete_document_records(self, document_id: int) -> None:
        ...

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        knowledge_base_ids: list[str] | None = None,
    ) -> list[RetrievedChunkRecord]:
        ...


class InMemoryRetriFlowVectorStore:
    def __init__(self) -> None:
        self.embedding_service = RetriFlowEmbeddingService()

    def upsert_chunk_records(self, records: list[VectorChunkRecord]) -> None:
        # The primary relational store remains the source of truth for fallback mode.
        _ = records

    def delete_document_records(self, document_id: int) -> None:
        _ = document_id

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        knowledge_base_ids: list[str] | None = None,
    ) -> list[RetrievedChunkRecord]:
        rows = load_chunk_rows(knowledge_base_ids=knowledge_base_ids)
        if not rows:
            return []

        vector_store = InMemoryVectorStore(self.embedding_service)
        documents = [
            Document(
                id=str(row["chunk_id"]),
                page_content=row["content"],
                metadata={
                    "chunk_id": row["chunk_id"],
                    "knowledge_base_id": row["knowledge_base_id"],
                    "document_id": row["document_id"],
                    "document_title": row["document_title"],
                    "channel": "semantic",
                    "source_updated_at": row["source_updated_at"],
                },
            )
            for row in rows
        ]
        vector_store.add_documents(documents)

        results = vector_store.similarity_search_with_score(query, k=k)
        return [
            RetrievedChunkRecord(
                chunk_id=int(document.metadata["chunk_id"]),
                knowledge_base_id=str(document.metadata["knowledge_base_id"]),
                document_id=int(document.metadata["document_id"]),
                document_title=str(document.metadata["document_title"]),
                content=document.page_content,
                score=float(score),
                channel="semantic",
                source_updated_at=str(document.metadata.get("source_updated_at", "")),
            )
            for document, score in results
        ]


class PostgresRetriFlowVectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.embedding_service = RetriFlowEmbeddingService()
        self.fallback_store = InMemoryRetriFlowVectorStore()

    def upsert_chunk_records(self, records: list[VectorChunkRecord]) -> None:
        if not records:
            return

        try:
            vector_by_chunk_id = self._embed_records(records)
            dimension = len(next(iter(vector_by_chunk_id.values()), []))
            if dimension == 0:
                return

            with self._connect() as connection:
                self._setup(connection, dimension)
                register_vector = self._register_vector(connection)

                register_vector(connection)
                with connection.cursor() as cursor:
                    insert_sql = self._build_insert_sql()
                    payload = [
                        (
                            record.chunk_id,
                            record.knowledge_base_id,
                            record.document_id,
                            record.document_title,
                            record.content,
                            record.document_type,
                            record.strategy,
                            record.collection_name,
                            record.embedding_model,
                            json.dumps(record.metadata, ensure_ascii=False),
                            numpy.array(vector_by_chunk_id[record.chunk_id], dtype=numpy.float32),
                        )
                        for record in records
                        if record.chunk_id in vector_by_chunk_id
                    ]
                    cursor.executemany(insert_sql, payload)
                connection.commit()
        except Exception:
            self.fallback_store.upsert_chunk_records(records)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        knowledge_base_ids: list[str] | None = None,
    ) -> list[RetrievedChunkRecord]:
        try:
            query_vector = self.embedding_service.embed_query(query)
            dimension = len(query_vector)
            if dimension == 0:
                return []

            with self._connect() as connection:
                self._setup(connection, dimension)
                register_vector = self._register_vector(connection)

                register_vector(connection)
                self._maybe_backfill(connection)
                self._maybe_backfill_missing_records(connection, knowledge_base_ids=knowledge_base_ids)
                with connection.cursor() as cursor:
                    cursor.execute(
                        self._build_search_sql(knowledge_base_ids=knowledge_base_ids),
                        (
                            numpy.array(query_vector, dtype=numpy.float32),
                            *(knowledge_base_ids or []),
                            numpy.array(query_vector, dtype=numpy.float32),
                            k,
                        ),
                    )
                    rows = cursor.fetchall()

            return [
                RetrievedChunkRecord(
                    chunk_id=row[0],
                    knowledge_base_id=row[1],
                    document_id=row[2],
                document_title=row[3],
                content=row[4],
                score=float(row[5]),
                channel="semantic",
                source_updated_at=str(row[6] if len(row) > 6 else ""),
            )
            for row in rows
        ]
        except Exception:
            return self.fallback_store.similarity_search(query, k=k, knowledge_base_ids=knowledge_base_ids)

    def delete_document_records(self, document_id: int) -> None:
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"delete from {self.settings.pgvector_table} where document_id = %s",
                        (document_id,),
                    )
                connection.commit()
        except Exception:
            self.fallback_store.delete_document_records(document_id)

    def _connect(self):
        psycopg = self._import_psycopg()
        dsn = self.settings.pgvector_dsn.strip() or self.settings.database_dsn.strip()
        if not dsn:
            raise RuntimeError("No PostgreSQL DSN configured for vector persistence")
        connection = psycopg.connect(dsn)
        configure_postgres_connection(connection)
        return connection

    def _setup(self, connection, dimension: int) -> None:
        with connection.cursor() as cursor:
            cursor.execute("create extension if not exists vector")
            cursor.execute(
                f"""
                create table if not exists {self.settings.pgvector_table} (
                    chunk_id bigint primary key,
                    knowledge_base_id text not null,
                    document_id bigint not null,
                    document_title text not null,
                    content text not null,
                    document_type text not null,
                    strategy text not null,
                    collection_name text not null default '',
                    embedding_model text not null default '',
                    metadata_json jsonb not null default '{{}}'::jsonb,
                    embedding vector({dimension}) not null,
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                f"alter table {self.settings.pgvector_table} add column if not exists collection_name text not null default ''"
            )
            cursor.execute(
                f"alter table {self.settings.pgvector_table} add column if not exists embedding_model text not null default ''"
            )
            cursor.execute(
                f"""
                create index if not exists {self.settings.pgvector_table}_embedding_hnsw
                on {self.settings.pgvector_table}
                using hnsw (embedding vector_cosine_ops)
                """
            )

    def _maybe_backfill(self, connection) -> None:
        with connection.cursor() as cursor:
            cursor.execute(f"select count(*) from {self.settings.pgvector_table}")
            row_count = int(cursor.fetchone()[0])
        if row_count > 0:
            return

        records = self._load_primary_chunk_records()
        if not records:
            return

        vector_by_chunk_id = self._embed_records(records)
        with connection.cursor() as cursor:
            cursor.executemany(
                self._build_insert_sql(),
                [
                    (
                        record.chunk_id,
                        record.knowledge_base_id,
                        record.document_id,
                        record.document_title,
                        record.content,
                        record.document_type,
                        record.strategy,
                        record.collection_name,
                        record.embedding_model,
                        json.dumps(record.metadata, ensure_ascii=False),
                        numpy.array(vector_by_chunk_id[record.chunk_id], dtype=numpy.float32),
                    )
                    for record in records
                    if record.chunk_id in vector_by_chunk_id
                ],
            )
        connection.commit()

    def _maybe_backfill_missing_records(
        self,
        connection,
        knowledge_base_ids: list[str] | None = None,
    ) -> None:
        records = self._load_missing_primary_chunk_records(connection, knowledge_base_ids=knowledge_base_ids)
        if not records:
            return

        vector_by_chunk_id = self._embed_records(records)
        if not vector_by_chunk_id:
            return

        with connection.cursor() as cursor:
            cursor.executemany(
                self._build_insert_sql(),
                [
                    (
                        record.chunk_id,
                        record.knowledge_base_id,
                        record.document_id,
                        record.document_title,
                        record.content,
                        record.document_type,
                        record.strategy,
                        record.collection_name,
                        record.embedding_model,
                        json.dumps(record.metadata, ensure_ascii=False),
                        numpy.array(vector_by_chunk_id[record.chunk_id], dtype=numpy.float32),
                    )
                    for record in records
                    if record.chunk_id in vector_by_chunk_id
                ],
            )
        connection.commit()

    def _build_insert_sql(self) -> str:
        table = self.settings.pgvector_table
        return f"""
            insert into {table} (
                chunk_id,
                knowledge_base_id,
                document_id,
                document_title,
                content,
                document_type,
                strategy,
                collection_name,
                embedding_model,
                metadata_json,
                embedding,
                updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, now())
            on conflict (chunk_id) do update set
                knowledge_base_id = excluded.knowledge_base_id,
                document_id = excluded.document_id,
                document_title = excluded.document_title,
                content = excluded.content,
                document_type = excluded.document_type,
                strategy = excluded.strategy,
                collection_name = excluded.collection_name,
                embedding_model = excluded.embedding_model,
                metadata_json = excluded.metadata_json,
                embedding = excluded.embedding,
                updated_at = now()
        """

    def _build_search_sql(self, knowledge_base_ids: list[str] | None = None) -> str:
        table = self.settings.pgvector_table
        where_clause = ""
        if knowledge_base_ids:
            placeholders = ", ".join("%s" for _ in knowledge_base_ids)
            where_clause = f"and kc.knowledge_base_id in ({placeholders})"
        return f"""
            select
                kc.id as chunk_id,
                kc.knowledge_base_id,
                kc.document_id,
                kd.title as document_title,
                kc.content,
                1 - (v.embedding <=> %s) as score,
                coalesce(kd.vector_indexed_at, kc.created_at) as source_updated_at
            from {table} v
            join knowledge_chunks kc on kc.id = v.chunk_id
            join knowledge_documents kd on kd.id = kc.document_id
            where kc.enabled = 1
            {where_clause}
            order by v.embedding <=> %s
            limit %s
        """

    def _build_missing_records_sql(self, knowledge_base_ids: list[str] | None = None) -> str:
        table = self.settings.pgvector_table
        where_clause = ""
        if knowledge_base_ids:
            placeholders = ", ".join("%s" for _ in knowledge_base_ids)
            where_clause = f"and kc.knowledge_base_id in ({placeholders})"
        return f"""
            select
                kc.id as chunk_id,
                kc.knowledge_base_id,
                kc.document_id,
                kd.title as document_title,
                kc.content,
                kc.document_type,
                kc.strategy,
                kb.collection_name,
                kb.embedding_model,
                kc.metadata_json
            from knowledge_chunks kc
            join knowledge_documents kd on kd.id = kc.document_id
            join knowledge_bases kb on kb.id = kc.knowledge_base_id
            left join {table} v on v.chunk_id = kc.id
            where kc.enabled = 1
            {where_clause}
              and v.chunk_id is null
            order by kc.id
        """

    def _load_missing_primary_chunk_records(
        self,
        connection,
        knowledge_base_ids: list[str] | None = None,
    ) -> list[VectorChunkRecord]:
        with connection.cursor() as cursor:
            cursor.execute(
                self._build_missing_records_sql(knowledge_base_ids=knowledge_base_ids),
                tuple(knowledge_base_ids or []),
            )
            rows = cursor.fetchall()

        return [self._row_to_vector_chunk_record(row) for row in rows]

    @staticmethod
    def _import_psycopg():
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is not installed for pgvector persistence") from exc
        return psycopg

    @staticmethod
    def _register_vector(connection):
        try:
            from pgvector.psycopg import register_vector
        except ImportError as exc:
            raise RuntimeError("pgvector is not installed for pgvector persistence") from exc
        return register_vector

    @staticmethod
    def _load_primary_chunk_records() -> list[VectorChunkRecord]:
        with get_connection() as connection:
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
                    kb.collection_name,
                    kb.embedding_model,
                    kc.metadata_json
                from knowledge_chunks kc
                join knowledge_documents kd on kd.id = kc.document_id
                join knowledge_bases kb on kb.id = kc.knowledge_base_id
                where kc.enabled = 1
                order by kc.id
                """
            ).fetchall()

        return [
            PostgresRetriFlowVectorStore._row_to_vector_chunk_record(row)
            for row in rows
        ]

    @staticmethod
    def _row_to_vector_chunk_record(row) -> VectorChunkRecord:
        return VectorChunkRecord(
            chunk_id=int(row["chunk_id"]),
            knowledge_base_id=str(row["knowledge_base_id"]),
            document_id=int(row["document_id"]),
            document_title=str(row["document_title"]),
            content=str(row["content"]),
            document_type=str(row["document_type"]),
            strategy=str(row["strategy"]),
            collection_name=str(row["collection_name"] or row["knowledge_base_id"]).replace("-", ""),
            embedding_model=str(row["embedding_model"] or "Qwen/Qwen3-Embedding-8B-GGUF"),
            metadata=PostgresRetriFlowVectorStore._parse_json_field(
                row["metadata_json"],
                default={},
            ),
        )

    def _embed_records(self, records: list[VectorChunkRecord]) -> dict[int, list[float]]:
        vectors: dict[int, list[float]] = {}
        groups: dict[tuple[str | None, str | None], list[VectorChunkRecord]] = {}
        for record in records:
            model_name = record.embedding_model.strip() or None
            provider_name = self._derive_embedding_provider(model_name)
            groups.setdefault((provider_name, model_name), []).append(record)

        for (provider_name, model_name), group in groups.items():
            embedded = self.embedding_service.embed_texts(
                [record.content for record in group],
                provider_name=provider_name,
                model_name=model_name,
            )
            for record, vector in zip(group, embedded, strict=False):
                vectors[record.chunk_id] = vector
        return vectors

    @staticmethod
    def _derive_embedding_provider(model_name: str | None) -> str | None:
        normalized = (model_name or "").strip().lower()
        if not normalized:
            return None
        if "qwen/qwen3-embedding-8b-gguf" in normalized or normalized.startswith("lmstudio:"):
            return "lmstudio"
        if "qwen3-embedding:8b" in normalized or normalized.startswith("ollama:"):
            return "ollama"
        if "qwen/qwen3-embedding" in normalized:
            return "siliconflow"
        return None

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


def resolve_vector_store() -> RetriFlowVectorStore:
    settings = get_settings()
    if settings.vector_store_type == "pg" and (
        settings.pgvector_dsn.strip() or settings.database_dsn.strip()
    ):
        return PostgresRetriFlowVectorStore()
    return InMemoryRetriFlowVectorStore()
