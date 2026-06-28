import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from core.config import get_settings


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DatabaseRow:
    def __init__(self, columns: list[str], values: Iterable[Any]) -> None:
        self._columns = list(columns)
        self._values = tuple(values)
        self._mapping = {column: value for column, value in zip(self._columns, self._values, strict=False)}

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping.get(key, default)


class DatabaseCursor:
    def __init__(self, native_cursor) -> None:
        self._native_cursor = native_cursor
        self._columns = [
            description[0]
            for description in (native_cursor.description or [])
        ]

    @property
    def lastrowid(self) -> Any:
        return getattr(self._native_cursor, "lastrowid", None)

    def fetchone(self) -> DatabaseRow | None:
        row = self._native_cursor.fetchone()
        if row is None:
            return None
        return DatabaseRow(self._columns, row)

    def fetchall(self) -> list[DatabaseRow]:
        rows = self._native_cursor.fetchall()
        return [DatabaseRow(self._columns, row) for row in rows]


class DatabaseConnection:
    def __init__(self, backend: str, native_connection) -> None:
        self.backend = backend
        self._native_connection = native_connection

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self._native_connection.rollback()
        self._native_connection.close()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> DatabaseCursor:
        cursor = self._native_connection.cursor()
        cursor.execute(self._normalize_sql(sql), tuple(params))
        return DatabaseCursor(cursor)

    def executemany(self, sql: str, params_seq: Iterable[Iterable[Any]]) -> DatabaseCursor:
        cursor = self._native_connection.cursor()
        cursor.executemany(self._normalize_sql(sql), [tuple(params) for params in params_seq])
        return DatabaseCursor(cursor)

    def commit(self) -> None:
        self._native_connection.commit()

    def rollback(self) -> None:
        self._native_connection.rollback()

    def close(self) -> None:
        self._native_connection.close()

    def _normalize_sql(self, sql: str) -> str:
        if self.backend == "sqlite":
            return sql
        return sql.replace("?", "%s")


def get_connection() -> DatabaseConnection:
    backend = _resolve_database_backend()
    if backend == "pg":
        try:
            return _get_postgres_connection()
        except Exception:
            if _should_allow_sqlite_fallback():
                return _get_sqlite_connection()
            raise
    return _get_sqlite_connection()


def initialize_database() -> None:
    backend = _resolve_database_backend()
    if backend == "pg":
        try:
            _initialize_postgres_database()
            return
        except Exception:
            if _should_allow_sqlite_fallback():
                _initialize_sqlite_database()
                return
            raise
    _initialize_sqlite_database()


def configure_postgres_connection(native_connection) -> None:
    settings = get_settings()
    search_path = f"{_validated_identifier(settings.database_schema)},public"
    with native_connection.cursor() as cursor:
        cursor.execute("select set_config('search_path', %s, false)", (search_path,))


def _resolve_database_backend() -> str:
    settings = get_settings()
    requested = settings.database_backend.strip().lower()
    if requested in {"pg", "postgres", "postgresql"}:
        return "pg"
    if requested == "sqlite":
        return "sqlite"
    if settings.database_dsn.strip() or settings.pgvector_dsn.strip():
        return "pg"
    return "sqlite"


def _should_allow_sqlite_fallback() -> bool:
    settings = get_settings()
    if settings.allow_sqlite_fallback:
        return True
    requested = settings.database_backend.strip().lower()
    if requested == "sqlite":
        return True
    if requested in {"pg", "postgres", "postgresql"}:
        return False
    return not (settings.database_dsn.strip() or settings.pgvector_dsn.strip())


def _get_sqlite_connection() -> DatabaseConnection:
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    native_connection = sqlite3.connect(db_path)
    native_connection.execute("pragma foreign_keys = on")
    return DatabaseConnection("sqlite", native_connection)


def _get_postgres_connection() -> DatabaseConnection:
    psycopg = _import_psycopg()
    settings = get_settings()
    dsn = settings.database_dsn.strip() or settings.pgvector_dsn.strip()
    if not dsn:
        raise RuntimeError("PostgreSQL backend requested but no database DSN is configured")

    native_connection = psycopg.connect(dsn)
    configure_postgres_connection(native_connection)
    return DatabaseConnection("pg", native_connection)


def _initialize_sqlite_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            create table if not exists sessions (
                id text primary key,
                title text not null,
                message_count integer not null default 0,
                owner_id text not null default ''
            )
            """
        )
        _ensure_sqlite_column(connection, "sessions", "owner_id", "text not null default ''")
        connection.execute(
            """
            create table if not exists users (
                id text primary key,
                username text not null unique,
                password_hash text not null,
                role text not null default 'user',
                avatar_url text not null default '',
                created_at text not null default current_timestamp
            )
            """
        )
        _ensure_sqlite_column(connection, "users", "avatar_url", "text not null default ''")
        connection.execute(
            """
            create table if not exists knowledge_bases (
                id text primary key,
                name text not null,
                product text not null,
                document_count integer not null default 0,
                embedding_model text not null default 'Qwen/Qwen3-Embedding-8B',
                collection_name text not null default '',
                owner text not null default 'admin',
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            )
            """
        )
        _ensure_sqlite_column(connection, "knowledge_bases", "embedding_model", "text not null default 'Qwen/Qwen3-Embedding-8B'")
        _ensure_sqlite_column(connection, "knowledge_bases", "collection_name", "text not null default ''")
        _ensure_sqlite_column(connection, "knowledge_bases", "owner", "text not null default 'admin'")
        _ensure_sqlite_column(connection, "knowledge_bases", "created_at", "text not null default current_timestamp")
        _ensure_sqlite_column(connection, "knowledge_bases", "updated_at", "text not null default current_timestamp")
        connection.execute(
            """
            create table if not exists knowledge_base_route_profiles (
                knowledge_base_id text primary key,
                profile_text text not null default '',
                sample_questions_json text not null default '[]',
                keywords_json text not null default '[]',
                updated_at text not null default current_timestamp,
                foreign key (knowledge_base_id) references knowledge_bases (id)
            )
            """
        )
        connection.execute(
            """
            create table if not exists knowledge_documents (
                id integer primary key autoincrement,
                knowledge_base_id text not null,
                title text not null,
                source_type text not null,
                source_uri text not null default '',
                source_hash text not null default '',
                content text not null,
                status text not null default 'indexed',
                vector_index_status text not null default 'pending',
                vector_chunk_count integer not null default 0,
                vector_indexed_at text,
                processing_config_json text not null default '{}',
                created_at text not null default current_timestamp,
                foreign key (knowledge_base_id) references knowledge_bases (id)
            )
            """
        )
        _ensure_sqlite_column(connection, "knowledge_documents", "vector_index_status", "text not null default 'pending'")
        _ensure_sqlite_column(connection, "knowledge_documents", "vector_chunk_count", "integer not null default 0")
        _ensure_sqlite_column(connection, "knowledge_documents", "vector_indexed_at", "text")
        _ensure_sqlite_column(connection, "knowledge_documents", "source_uri", "text not null default ''")
        _ensure_sqlite_column(connection, "knowledge_documents", "source_hash", "text not null default ''")
        _ensure_sqlite_column(connection, "knowledge_documents", "processing_config_json", "text not null default '{}'")
        connection.execute(
            """
            create table if not exists knowledge_chunks (
                id integer primary key autoincrement,
                knowledge_base_id text not null,
                document_id integer not null,
                chunk_index integer not null,
                content text not null,
                char_count integer not null,
                enabled integer not null default 1,
                strategy text not null default 'recursive',
                document_type text not null default 'manual',
                metadata_json text not null default '{}',
                created_at text not null default current_timestamp,
                foreign key (knowledge_base_id) references knowledge_bases (id),
                foreign key (document_id) references knowledge_documents (id)
            )
            """
        )
        _ensure_sqlite_column(connection, "knowledge_chunks", "strategy", "text not null default 'recursive'")
        _ensure_sqlite_column(connection, "knowledge_chunks", "document_type", "text not null default 'manual'")
        _ensure_sqlite_column(connection, "knowledge_chunks", "metadata_json", "text not null default '{}'")
        _ensure_sqlite_column(connection, "knowledge_chunks", "enabled", "integer not null default 1")
        connection.execute(
            """
            create table if not exists knowledge_document_blocks (
                id integer primary key autoincrement,
                knowledge_base_id text not null,
                document_id integer not null,
                block_index integer not null,
                block_type text not null,
                page_number integer,
                heading_path_json text not null default '[]',
                level integer,
                text text,
                headers_json text not null default '[]',
                row_count integer,
                column_count integer,
                caption text,
                created_at text not null default current_timestamp,
                foreign key (knowledge_base_id) references knowledge_bases (id),
                foreign key (document_id) references knowledge_documents (id)
            )
            """
        )
        connection.execute(
            """
            create table if not exists knowledge_document_table_cells (
                id integer primary key autoincrement,
                block_id integer not null,
                row_index integer not null,
                column_index integer not null,
                text text not null default '',
                is_header integer not null default 0,
                created_at text not null default current_timestamp,
                foreign key (block_id) references knowledge_document_blocks (id)
            )
            """
        )
        connection.execute(
            """
            create table if not exists ingestion_tasks (
                id integer primary key autoincrement,
                knowledge_base_id text not null,
                document_id integer not null,
                source_type text not null,
                status text not null,
                chunk_count integer not null default 0,
                message text not null default '',
                created_at text not null default current_timestamp,
                foreign key (knowledge_base_id) references knowledge_bases (id),
                foreign key (document_id) references knowledge_documents (id)
            )
            """
        )
        connection.execute(
            """
            create table if not exists ingestion_pipelines (
                id integer primary key autoincrement,
                name text not null,
                description text not null default '',
                nodes_json text not null default '[]',
                owner text not null default 'admin',
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            )
            """
        )
        connection.execute(
            """
            create table if not exists ingestion_task_nodes (
                id integer primary key autoincrement,
                task_id integer not null,
                node_id text not null default '',
                node_type text not null,
                node_order integer not null,
                success integer not null,
                status text not null default 'success',
                message text not null default '',
                error_message text not null default '',
                output_json text not null default '{}',
                duration_ms integer not null default 0,
                created_at text not null default current_timestamp,
                foreign key (task_id) references ingestion_tasks (id)
            )
            """
        )
        _ensure_sqlite_column(connection, "ingestion_task_nodes", "node_id", "text not null default ''")
        _ensure_sqlite_column(connection, "ingestion_task_nodes", "status", "text not null default 'success'")
        _ensure_sqlite_column(connection, "ingestion_task_nodes", "error_message", "text not null default ''")
        _ensure_sqlite_column(connection, "ingestion_task_nodes", "output_json", "text not null default '{}'")
        connection.execute(
            """
            create table if not exists admin_intent_nodes (
                id text primary key,
                name text not null,
                code text not null unique,
                level text not null default 'INTENT',
                node_type text not null default 'KB',
                parent_id text not null default 'ROOT',
                knowledge_base_id text not null default '',
                mcp_tool_id text not null default '',
                collection_name text not null default '',
                description text not null default '',
                sample_questions_json text not null default '[]',
                rule_snippet text not null default '',
                prompt_template text not null default '',
                param_prompt_template text not null default '',
                top_k integer,
                min_score real,
                sort_order integer not null default 0,
                enabled integer not null default 1,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            )
            """
        )
        _ensure_sqlite_column(connection, "admin_intent_nodes", "mcp_tool_id", "text not null default ''")
        _ensure_sqlite_column(connection, "admin_intent_nodes", "param_prompt_template", "text not null default ''")
        _ensure_sqlite_column(connection, "admin_intent_nodes", "min_score", "real")
        connection.execute(
            """
            create table if not exists admin_keyword_mappings (
                id text primary key,
                raw_keyword text not null,
                target_keyword text not null,
                match_type text not null default 'exact',
                priority integer not null default 0,
                enabled integer not null default 1,
                remark text not null default '',
                knowledge_base_id text not null default '',
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            )
            """
        )
        connection.execute(
            """
            create table if not exists admin_sample_questions (
                id text primary key,
                title text not null,
                description text not null default '',
                question text not null,
                sort_order integer not null default 0,
                enabled integer not null default 1,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            )
            """
        )
        connection.execute(
            """
            create table if not exists model_health (
                capability text not null,
                provider_name text not null,
                model text not null,
                state text not null default 'healthy',
                failure_count integer not null default 0,
                success_count integer not null default 0,
                opened_at real,
                last_success_at real,
                last_failure_at real,
                last_error text not null default '',
                last_success_duration_ms integer,
                last_first_packet_ms integer,
                half_open_in_flight integer not null default 0,
                updated_at text not null default current_timestamp,
                primary key (capability, provider_name, model)
            )
            """
        )
        _ensure_sqlite_column(connection, "model_health", "half_open_in_flight", "integer not null default 0")
        connection.execute(
            """
            create table if not exists conversation_messages (
                id integer primary key autoincrement,
                session_id text not null,
                role text not null,
                content text not null,
                duration_ms integer not null default 0,
                created_at text not null default current_timestamp
            )
            """
        )
        _ensure_sqlite_column(connection, "conversation_messages", "duration_ms", "integer not null default 0")
        connection.execute(
            """
            create table if not exists message_feedback (
                id integer primary key autoincrement,
                message_id integer not null,
                session_id text not null,
                user_id text not null,
                vote integer not null,
                reason text not null default '',
                comment text not null default '',
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp
            )
            """
        )
        connection.execute(
            """
            create table if not exists rag_trace_nodes (
                id text primary key,
                session_id text not null,
                task_id text not null default '',
                parent_id text not null default '',
                name text not null,
                node_type text not null default 'METHOD',
                status text not null default 'running',
                input_summary text not null default '',
                output_summary text not null default '',
                error_message text not null default '',
                metadata_json text not null default '{}',
                started_at text not null default current_timestamp,
                finished_at text,
                duration_ms integer not null default 0
            )
            """
        )
        connection.execute(
            """
            create table if not exists conversation_memory_summaries (
                id integer primary key autoincrement,
                session_id text not null,
                content text not null,
                last_message_id integer not null,
                updated_at text not null default current_timestamp,
                expires_at text
            )
            """
        )
        connection.execute(
            """
            create table if not exists conversation_mid_memories (
                id integer primary key autoincrement,
                session_id text not null,
                memory_type text not null default 'topic',
                content text not null,
                status text not null default 'active',
                updated_at text not null default current_timestamp,
                expires_at text
            )
            """
        )
        connection.execute(
            """
            create table if not exists conversation_long_memories (
                id integer primary key autoincrement,
                owner_type text not null default 'session',
                owner_id text not null,
                memory_type text not null default 'preference',
                content text not null,
                status text not null default 'active',
                updated_at text not null default current_timestamp,
                expires_at text
            )
            """
        )
        connection.execute("create index if not exists idx_admin_intent_nodes_parent on admin_intent_nodes (parent_id, sort_order)")
        connection.execute("create index if not exists idx_knowledge_documents_source_hash on knowledge_documents (knowledge_base_id, source_hash)")
        connection.execute("create index if not exists idx_admin_keyword_mappings_keyword on admin_keyword_mappings (raw_keyword, enabled)")
        connection.execute("create index if not exists idx_admin_sample_questions_enabled on admin_sample_questions (enabled, sort_order)")
        connection.execute("create index if not exists idx_model_health_state on model_health (state, provider_name)")
        connection.execute("create index if not exists idx_rag_trace_nodes_session on rag_trace_nodes (session_id, started_at)")
        connection.execute("create index if not exists idx_rag_trace_nodes_parent on rag_trace_nodes (parent_id)")
        connection.execute("create unique index if not exists idx_message_feedback_user_message on message_feedback (message_id, user_id)")
        _seed_demo_data(connection)
        connection.commit()


def _initialize_postgres_database() -> None:
    settings = get_settings()
    schema_name = _validated_identifier(settings.database_schema)
    psycopg = _import_psycopg()

    with _get_postgres_connection() as connection:
        with connection._native_connection.cursor() as cursor:
            cursor.execute("create extension if not exists vector")
            cursor.execute(
                psycopg.sql.SQL("create schema if not exists {}").format(
                    psycopg.sql.Identifier(schema_name)
                )
            )
            cursor.execute(
                """
                create table if not exists sessions (
                    id text primary key,
                    title text not null,
                    message_count integer not null default 0,
                    owner_id text not null default ''
                )
                """
            )
            _ensure_postgres_column(
                cursor,
                "sessions",
                "owner_id",
                "text not null default ''",
            )
            cursor.execute(
                """
                create table if not exists users (
                    id text primary key,
                    username text not null unique,
                    password_hash text not null,
                    role text not null default 'user',
                    avatar_url text not null default '',
                    created_at timestamptz not null default now()
                )
                """
            )
            _ensure_postgres_column(cursor, "users", "avatar_url", "text not null default ''")
            cursor.execute(
                """
                create table if not exists knowledge_bases (
                    id text primary key,
                    name text not null,
                    product text not null,
                    document_count integer not null default 0,
                    embedding_model text not null default 'Qwen/Qwen3-Embedding-8B',
                    collection_name text not null default '',
                    owner text not null default 'admin',
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute("alter table knowledge_bases add column if not exists embedding_model text not null default 'Qwen/Qwen3-Embedding-8B'")
            cursor.execute("alter table knowledge_bases add column if not exists collection_name text not null default ''")
            cursor.execute("alter table knowledge_bases add column if not exists owner text not null default 'admin'")
            cursor.execute("alter table knowledge_bases add column if not exists created_at timestamptz not null default now()")
            cursor.execute("alter table knowledge_bases add column if not exists updated_at timestamptz not null default now()")
            cursor.execute(
                """
                create table if not exists knowledge_base_route_profiles (
                    knowledge_base_id text primary key references knowledge_bases(id) on delete cascade,
                    profile_text text not null default '',
                    sample_questions_json jsonb not null default '[]'::jsonb,
                    keywords_json jsonb not null default '[]'::jsonb,
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists knowledge_documents (
                    id bigint generated by default as identity primary key,
                    knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
                    title text not null,
                    source_type text not null,
                    source_uri text not null default '',
                    source_hash text not null default '',
                    content text not null,
                    status text not null default 'indexed',
                    vector_index_status text not null default 'pending',
                    vector_chunk_count integer not null default 0,
                    vector_indexed_at timestamptz,
                    processing_config_json jsonb not null default '{}'::jsonb,
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute("alter table knowledge_documents add column if not exists source_hash text not null default ''")
            _ensure_postgres_column(
                cursor,
                "knowledge_documents",
                "vector_index_status",
                "text not null default 'pending'",
            )
            _ensure_postgres_column(
                cursor,
                "knowledge_documents",
                "vector_chunk_count",
                "integer not null default 0",
            )
            _ensure_postgres_column(
                cursor,
                "knowledge_documents",
                "vector_indexed_at",
                "timestamptz",
            )
            _ensure_postgres_column(
                cursor,
                "knowledge_documents",
                "source_uri",
                "text not null default ''",
            )
            _ensure_postgres_column(
                cursor,
                "knowledge_documents",
                "processing_config_json",
                "jsonb not null default '{}'::jsonb",
            )
            cursor.execute(
                """
                create table if not exists knowledge_chunks (
                    id bigint generated by default as identity primary key,
                    knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
                    document_id bigint not null references knowledge_documents(id) on delete cascade,
                    chunk_index integer not null,
                    content text not null,
                    char_count integer not null,
                    enabled integer not null default 1,
                    strategy text not null default 'recursive',
                    document_type text not null default 'manual',
                    metadata_json jsonb not null default '{}'::jsonb,
                    created_at timestamptz not null default now()
                )
                """
            )
            _ensure_postgres_column(
                cursor,
                "knowledge_chunks",
                "strategy",
                "text not null default 'recursive'",
            )
            _ensure_postgres_column(
                cursor,
                "knowledge_chunks",
                "document_type",
                "text not null default 'manual'",
            )
            _ensure_postgres_column(
                cursor,
                "knowledge_chunks",
                "metadata_json",
                "jsonb not null default '{}'::jsonb",
            )
            _ensure_postgres_column(
                cursor,
                "knowledge_chunks",
                "enabled",
                "integer not null default 1",
            )
            cursor.execute(
                """
                create table if not exists knowledge_document_blocks (
                    id bigint generated by default as identity primary key,
                    knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
                    document_id bigint not null references knowledge_documents(id) on delete cascade,
                    block_index integer not null,
                    block_type text not null,
                    page_number integer,
                    heading_path_json jsonb not null default '[]'::jsonb,
                    level integer,
                    text text,
                    headers_json jsonb not null default '[]'::jsonb,
                    row_count integer,
                    column_count integer,
                    caption text,
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists knowledge_document_table_cells (
                    id bigint generated by default as identity primary key,
                    block_id bigint not null references knowledge_document_blocks(id) on delete cascade,
                    row_index integer not null,
                    column_index integer not null,
                    text text not null default '',
                    is_header integer not null default 0,
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists ingestion_tasks (
                    id bigint generated by default as identity primary key,
                    knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
                    document_id bigint not null references knowledge_documents(id) on delete cascade,
                    source_type text not null,
                    status text not null,
                    chunk_count integer not null default 0,
                    message text not null default '',
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists ingestion_pipelines (
                    id bigint generated by default as identity primary key,
                    name text not null,
                    description text not null default '',
                    nodes_json jsonb not null default '[]'::jsonb,
                    owner text not null default 'admin',
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists ingestion_task_nodes (
                    id bigint generated by default as identity primary key,
                    task_id bigint not null references ingestion_tasks(id) on delete cascade,
                    node_id text not null default '',
                    node_type text not null,
                    node_order integer not null,
                    success integer not null,
                    status text not null default 'success',
                    message text not null default '',
                    error_message text not null default '',
                    output_json jsonb not null default '{}'::jsonb,
                    duration_ms integer not null default 0,
                    created_at timestamptz not null default now()
                )
                """
            )
            _ensure_postgres_column(cursor, "ingestion_task_nodes", "node_id", "text not null default ''")
            _ensure_postgres_column(cursor, "ingestion_task_nodes", "status", "text not null default 'success'")
            _ensure_postgres_column(cursor, "ingestion_task_nodes", "error_message", "text not null default ''")
            _ensure_postgres_column(cursor, "ingestion_task_nodes", "output_json", "jsonb not null default '{}'::jsonb")
            cursor.execute(
                """
                create table if not exists admin_intent_nodes (
                    id text primary key,
                    name text not null,
                    code text not null unique,
                    level text not null default 'INTENT',
                    node_type text not null default 'KB',
                    parent_id text not null default 'ROOT',
                    knowledge_base_id text not null default '',
                    mcp_tool_id text not null default '',
                    collection_name text not null default '',
                    description text not null default '',
                    sample_questions_json jsonb not null default '[]'::jsonb,
                    rule_snippet text not null default '',
                    prompt_template text not null default '',
                    param_prompt_template text not null default '',
                    top_k integer,
                    min_score double precision,
                    sort_order integer not null default 0,
                    enabled integer not null default 1,
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            _ensure_postgres_column(cursor, "admin_intent_nodes", "mcp_tool_id", "text not null default ''")
            _ensure_postgres_column(cursor, "admin_intent_nodes", "param_prompt_template", "text not null default ''")
            _ensure_postgres_column(cursor, "admin_intent_nodes", "min_score", "double precision")
            cursor.execute(
                """
                create table if not exists admin_keyword_mappings (
                    id text primary key,
                    raw_keyword text not null,
                    target_keyword text not null,
                    match_type text not null default 'exact',
                    priority integer not null default 0,
                    enabled integer not null default 1,
                    remark text not null default '',
                    knowledge_base_id text not null default '',
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists admin_sample_questions (
                    id text primary key,
                    title text not null,
                    description text not null default '',
                    question text not null,
                    sort_order integer not null default 0,
                    enabled integer not null default 1,
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists model_health (
                    capability text not null,
                    provider_name text not null,
                    model text not null,
                    state text not null default 'healthy',
                    failure_count integer not null default 0,
                    success_count integer not null default 0,
                    opened_at double precision,
                    last_success_at double precision,
                    last_failure_at double precision,
                    last_error text not null default '',
                    last_success_duration_ms integer,
                    last_first_packet_ms integer,
                    half_open_in_flight integer not null default 0,
                    updated_at timestamptz not null default now(),
                    primary key (capability, provider_name, model)
                )
                """
            )
            _ensure_postgres_column(cursor, "model_health", "half_open_in_flight", "integer not null default 0")
            cursor.execute(
                """
                create table if not exists conversation_messages (
                    id bigint generated by default as identity primary key,
                    session_id text not null references sessions(id) on delete cascade,
                    role text not null,
                    content text not null,
                    duration_ms integer not null default 0,
                    created_at timestamptz not null default now()
                )
                """
            )
            _ensure_postgres_column(cursor, "conversation_messages", "duration_ms", "integer not null default 0")
            cursor.execute(
                """
                create table if not exists message_feedback (
                    id bigint generated by default as identity primary key,
                    message_id bigint not null references conversation_messages(id) on delete cascade,
                    session_id text not null references sessions(id) on delete cascade,
                    user_id text not null references users(id) on delete cascade,
                    vote integer not null,
                    reason text not null default '',
                    comment text not null default '',
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists rag_trace_nodes (
                    id text primary key,
                    session_id text not null,
                    task_id text not null default '',
                    parent_id text not null default '',
                    name text not null,
                    node_type text not null default 'METHOD',
                    status text not null default 'running',
                    input_summary text not null default '',
                    output_summary text not null default '',
                    error_message text not null default '',
                    metadata_json jsonb not null default '{}'::jsonb,
                    started_at timestamptz not null default now(),
                    finished_at timestamptz,
                    duration_ms integer not null default 0
                )
                """
            )
            cursor.execute(
                """
                create table if not exists conversation_memory_summaries (
                    id bigint generated by default as identity primary key,
                    session_id text not null references sessions(id) on delete cascade,
                    content text not null,
                    last_message_id bigint not null,
                    updated_at timestamptz not null default now(),
                    expires_at timestamptz
                )
                """
            )
            cursor.execute(
                """
                create table if not exists conversation_mid_memories (
                    id bigint generated by default as identity primary key,
                    session_id text not null references sessions(id) on delete cascade,
                    memory_type text not null default 'topic',
                    content text not null,
                    status text not null default 'active',
                    updated_at timestamptz not null default now(),
                    expires_at timestamptz
                )
                """
            )
            cursor.execute(
                """
                create table if not exists conversation_long_memories (
                    id bigint generated by default as identity primary key,
                    owner_type text not null default 'session',
                    owner_id text not null,
                    memory_type text not null default 'preference',
                    content text not null,
                    status text not null default 'active',
                    updated_at timestamptz not null default now(),
                    expires_at timestamptz
                )
                """
            )
            cursor.execute("create index if not exists idx_knowledge_documents_kb on knowledge_documents (knowledge_base_id)")
            cursor.execute("create index if not exists idx_knowledge_documents_source_hash on knowledge_documents (knowledge_base_id, source_hash)")
            cursor.execute("create index if not exists idx_knowledge_chunks_doc on knowledge_chunks (document_id, chunk_index)")
            cursor.execute("create index if not exists idx_structured_blocks_doc on knowledge_document_blocks (document_id, block_index)")
            cursor.execute("create index if not exists idx_table_cells_block on knowledge_document_table_cells (block_id, row_index, column_index)")
            cursor.execute("create index if not exists idx_ingestion_tasks_doc on ingestion_tasks (document_id, created_at desc)")
            cursor.execute("create index if not exists idx_ingestion_task_nodes_task on ingestion_task_nodes (task_id, node_order)")
            cursor.execute("create index if not exists idx_admin_intent_nodes_parent on admin_intent_nodes (parent_id, sort_order)")
            cursor.execute("create index if not exists idx_admin_keyword_mappings_keyword on admin_keyword_mappings (raw_keyword, enabled)")
            cursor.execute("create index if not exists idx_admin_sample_questions_enabled on admin_sample_questions (enabled, sort_order)")
            cursor.execute("create index if not exists idx_model_health_state on model_health (state, provider_name)")
            cursor.execute("create index if not exists idx_conversation_messages_session on conversation_messages (session_id, id)")
            cursor.execute("create index if not exists idx_rag_trace_nodes_session on rag_trace_nodes (session_id, started_at)")
            cursor.execute("create index if not exists idx_rag_trace_nodes_parent on rag_trace_nodes (parent_id)")
            cursor.execute("create unique index if not exists idx_message_feedback_user_message on message_feedback (message_id, user_id)")
            cursor.execute("create index if not exists idx_conversation_memory_summaries_session on conversation_memory_summaries (session_id, id desc)")
            cursor.execute("create index if not exists idx_conversation_mid_memories_session on conversation_mid_memories (session_id, id desc)")
            cursor.execute("create index if not exists idx_conversation_long_memories_owner on conversation_long_memories (owner_type, owner_id, id desc)")

        _seed_demo_data(connection)
        connection.commit()


def _seed_demo_data(connection: DatabaseConnection) -> None:
    settings = get_settings()
    user_count = connection.execute("select count(*) from users").fetchone()[0]
    if user_count == 0:
        connection.execute(
            """
            insert into users (id, username, password_hash, role)
            values (?, ?, ?, ?)
            """,
            ("user-admin", "admin", _seed_password_hash("admin"), "admin"),
        )

    _seed_default_ingestion_pipeline(connection)

    if not settings.seed_demo_content:
        return

    session_count = connection.execute("select count(*) from sessions").fetchone()[0]
    if session_count == 0:
        connection.execute(
            """
            insert into sessions (id, title, message_count, owner_id)
            values (?, ?, ?, ?)
            """,
            ("session-demo-1", "RetriFlow enterprise RAG planning", 6, ""),
        )

    knowledge_count = connection.execute("select count(*) from knowledge_bases").fetchone()[0]
    if knowledge_count == 0:
        connection.execute(
            """
            insert into knowledge_bases (id, name, product, document_count, embedding_model, collection_name, owner)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            ("kb-demo-1", "RetriFlow product knowledge base", "RetriFlow", 1, "Qwen/Qwen3-Embedding-8B", "kbdemo1", "admin"),
        )
    route_profile_count = connection.execute("select count(*) from knowledge_base_route_profiles").fetchone()[0]
    if route_profile_count == 0:
        connection.execute(
            """
            insert into knowledge_base_route_profiles (
                knowledge_base_id,
                profile_text,
                sample_questions_json,
                keywords_json
            )
            values (?, ?, ?, ?)
            """,
            (
                "kb-demo-1",
                "RetriFlow product knowledge base enterprise rag workflow python vue langgraph langchain",
                '["RetriFlow 是什么？", "RetriFlow 的企业知识问答链路是什么？"]',
                '["retriflow", "langgraph", "langchain", "workflow", "rag"]',
            ),
        )

    document_count = connection.execute("select count(*) from knowledge_documents").fetchone()[0]
    if document_count == 0:
        connection.execute(
            """
            insert into knowledge_documents (
                id,
                knowledge_base_id,
                title,
                source_type,
                content,
                status,
                vector_index_status,
                vector_chunk_count,
                vector_indexed_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "kb-demo-1",
                "RetriFlow enterprise RAG baseline",
                "manual",
                "RetriFlow is an enterprise RAG system built with Python, FastAPI, Vue, LangGraph, hybrid retrieval, MCP tools, and observable workflows.",
                "indexed",
                "indexed",
                1,
                "2026-06-09 10:00:00",
            ),
        )

    chunk_count = connection.execute("select count(*) from knowledge_chunks").fetchone()[0]
    if chunk_count == 0:
        connection.execute(
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
            """,
            (
                "kb-demo-1",
                1,
                0,
                "RetriFlow is an enterprise RAG system built with Python, FastAPI, Vue, LangGraph, hybrid retrieval, MCP tools, and observable workflows.",
                len("RetriFlow is an enterprise RAG system built with Python, FastAPI, Vue, LangGraph, hybrid retrieval, MCP tools, and observable workflows."),
                "recursive",
                "manual",
                "{}",
            ),
        )

    ingestion_count = connection.execute("select count(*) from ingestion_tasks").fetchone()[0]
    if ingestion_count == 0:
        task_id = connection.execute(
            """
            insert into ingestion_tasks (knowledge_base_id, document_id, source_type, status, chunk_count, message)
            values (?, ?, ?, ?, ?, ?)
            returning id
            """,
            ("kb-demo-1", 1, "manual", "completed", 1, "RetriFlow ingestion pipeline completed."),
        ).fetchone()[0]
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
                (task_id, "normalize", "normalize", 1, 1, "success", "Normalized source text and preserved paragraph boundaries.", "", "{}", 1),
                (task_id, "segment", "segment", 2, 1, "success", "Derived 1 semantic segments from source text.", "", '{"segmentCount":1}', 1),
                (task_id, "chunk", "chunk", 3, 1, "success", "Generated 1 chunks with overlap-aware chunking.", "", '{"chunkCount":1}', 1),
                (task_id, "index", "index", 4, 1, "success", "Indexed chunks into the local retrieval store.", "", '{"settings":{"store":"local"},"chunkCount":1}', 1),
            ],
        )

    pipeline_count = connection.execute("select count(*) from ingestion_pipelines").fetchone()[0]
    if pipeline_count == 0:
        import json

        default_nodes = [
            {
                "node_id": "parse",
                "node_type": "parser",
                "next_node_id": "ai_enhance",
                "condition": "",
                "config": {"engine": "apache-tika", "file_types": ["pdf"], "preserve_structure": True},
            },
            {
                "node_id": "ai_enhance",
                "node_type": "extractor",
                "next_node_id": "chunk",
                "condition": "",
                "config": {"extract": ["paragraph", "heading", "table", "image_caption", "page_number"], "normalize_layout": True},
            },
            {
                "node_id": "chunk",
                "node_type": "chunker",
                "next_node_id": "embed",
                "condition": "",
                "config": {"strategy": "structure_aware", "chunk_size": 600, "chunk_overlap": 120},
            },
            {
                "node_id": "embed",
                "node_type": "embedder",
                "next_node_id": "index",
                "condition": "",
                "config": {"provider": "lmstudio", "model": "Qwen/Qwen3-Embedding-8B-GGUF"},
            },
            {
                "node_id": "index",
                "node_type": "indexer",
                "next_node_id": "",
                "condition": "",
                "config": {"store": "pgvector"},
            },
        ]
        connection.execute(
            """
            insert into ingestion_pipelines (name, description, nodes_json, owner)
            values (?, ?, ?, ?)
            """,
            (
                "pdf-ingestion-pipeline",
                "PDF文档摄取流水线 - 解析、AI增强、分块、向量化",
                json.dumps(default_nodes, ensure_ascii=False),
                "admin",
            ),
        )

    connection.execute(
        """
        update knowledge_bases
        set document_count = (
            select count(*)
            from knowledge_documents
            where knowledge_documents.knowledge_base_id = knowledge_bases.id
        )
        """
    )


def _seed_default_ingestion_pipeline(connection: DatabaseConnection) -> None:
    pipeline_count = connection.execute("select count(*) from ingestion_pipelines").fetchone()[0]
    if pipeline_count > 0:
        return

    import json

    default_nodes = [
        {
            "node_id": "parse",
            "node_type": "parser",
            "next_node_id": "ai_enhance",
            "condition": "",
            "config": {"engine": "apache-tika", "file_types": ["pdf"], "preserve_structure": True},
        },
        {
            "node_id": "ai_enhance",
            "node_type": "extractor",
            "next_node_id": "chunk",
            "condition": "",
            "config": {"extract": ["paragraph", "heading", "table", "image_caption", "page_number"], "normalize_layout": True},
        },
        {
            "node_id": "chunk",
            "node_type": "chunker",
            "next_node_id": "embed",
            "condition": "",
            "config": {"strategy": "structure_aware", "chunk_size": 600, "chunk_overlap": 120},
        },
        {
            "node_id": "embed",
            "node_type": "embedder",
            "next_node_id": "index",
            "condition": "",
            "config": {"provider": "lmstudio", "model": "Qwen/Qwen3-Embedding-8B-GGUF"},
        },
        {
            "node_id": "index",
            "node_type": "indexer",
            "next_node_id": "",
            "condition": "",
            "config": {"store": "pgvector"},
        },
    ]
    connection.execute(
        """
        insert into ingestion_pipelines (name, description, nodes_json, owner)
        values (?, ?, ?, ?)
        """,
        (
            "pdf-ingestion-pipeline",
            "PDF文档摄取流水线 - 解析、AI增强、分块、向量化",
            json.dumps(default_nodes, ensure_ascii=False),
            "admin",
        ),
    )


def _ensure_sqlite_column(
    connection: DatabaseConnection,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute(f"pragma table_info({table_name})").fetchall()
    }
    if column_name in existing_columns:
        return
    connection.execute(f"alter table {table_name} add column {column_name} {column_sql}")


def _ensure_postgres_column(
    cursor,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    cursor.execute(
        """
        select 1
        from information_schema.columns
        where table_schema = current_schema()
          and table_name = %s
          and column_name = %s
        limit 1
        """,
        (table_name, column_name),
    )
    if cursor.fetchone() is not None:
        return
    cursor.execute(f"alter table {table_name} add column {column_name} {column_sql}")


def _seed_password_hash(password: str) -> str:
    salt = "retriflow-seed-salt"
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def _validated_identifier(identifier: str) -> str:
    candidate = identifier.strip()
    if not IDENTIFIER_PATTERN.match(candidate):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return candidate


def _import_psycopg():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is not installed for PostgreSQL support") from exc
    return psycopg

