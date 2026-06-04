import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from core.config import get_settings
from core.state import configure_postgres_connection, get_connection
from domain.embeddings import RetriFlowEmbeddingService
from domain.retrieval_channels import RetrievedChunkRecord, load_chunk_rows


@dataclass
class VectorChunkRecord:
    chunk_id: int
    knowledge_base_id: str
    document_id: int
    document_title: str
    content: str
    document_type: str
    strategy: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RetriFlowVectorStore(Protocol):
    def upsert_chunk_records(self, records: list[VectorChunkRecord]) -> None:
        ...

    def similarity_search(self, query: str, k: int = 4) -> list[RetrievedChunkRecord]:
        ...


class InMemoryRetriFlowVectorStore:
    def __init__(self) -> None:
        self.embedding_service = RetriFlowEmbeddingService()

    def upsert_chunk_records(self, records: list[VectorChunkRecord]) -> None:
        # The primary relational store remains the source of truth for fallback mode.
        _ = records

    def similarity_search(self, query: str, k: int = 4) -> list[RetrievedChunkRecord]:
        rows = load_chunk_rows()
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
            vectors = self.embedding_service.embed_texts([record.content for record in records])
            dimension = len(vectors[0]) if vectors else 0
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
                            json.dumps(record.metadata, ensure_ascii=False),
                            numpy.array(vector, dtype=numpy.float32),
                        )
                        for record, vector in zip(records, vectors, strict=False)
                    ]
                    cursor.executemany(insert_sql, payload)
                connection.commit()
        except Exception:
            self.fallback_store.upsert_chunk_records(records)

    def similarity_search(self, query: str, k: int = 4) -> list[RetrievedChunkRecord]:
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
                with connection.cursor() as cursor:
                    cursor.execute(
                        self._build_search_sql(),
                        (
                            numpy.array(query_vector, dtype=numpy.float32),
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
                )
                for row in rows
            ]
        except Exception:
            return self.fallback_store.similarity_search(query, k=k)

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
                    metadata_json jsonb not null default '{{}}'::jsonb,
                    embedding vector({dimension}) not null,
                    updated_at timestamptz not null default now()
                )
                """
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

        vectors = self.embedding_service.embed_texts([record.content for record in records])
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
                        json.dumps(record.metadata, ensure_ascii=False),
                        numpy.array(vector, dtype=numpy.float32),
                    )
                    for record, vector in zip(records, vectors, strict=False)
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
                metadata_json,
                embedding,
                updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, now())
            on conflict (chunk_id) do update set
                knowledge_base_id = excluded.knowledge_base_id,
                document_id = excluded.document_id,
                document_title = excluded.document_title,
                content = excluded.content,
                document_type = excluded.document_type,
                strategy = excluded.strategy,
                metadata_json = excluded.metadata_json,
                embedding = excluded.embedding,
                updated_at = now()
        """

    def _build_search_sql(self) -> str:
        table = self.settings.pgvector_table
        return f"""
            select
                chunk_id,
                knowledge_base_id,
                document_id,
                document_title,
                content,
                1 - (embedding <=> %s) as score
            from {table}
            order by embedding <=> %s
            limit %s
        """

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
                    kc.metadata_json
                from knowledge_chunks kc
                join knowledge_documents kd on kd.id = kc.document_id
                order by kc.id
                """
            ).fetchall()

        return [
            VectorChunkRecord(
                chunk_id=int(row["chunk_id"]),
                knowledge_base_id=str(row["knowledge_base_id"]),
                document_id=int(row["document_id"]),
                document_title=str(row["document_title"]),
                content=str(row["content"]),
                document_type=str(row["document_type"]),
                strategy=str(row["strategy"]),
                metadata=json.loads(row["metadata_json"] or "{}"),
            )
            for row in rows
        ]


def resolve_vector_store() -> RetriFlowVectorStore:
    settings = get_settings()
    if settings.vector_store_type == "pg" and (
        settings.pgvector_dsn.strip() or settings.database_dsn.strip()
    ):
        return PostgresRetriFlowVectorStore()
    return InMemoryRetriFlowVectorStore()
