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
            return _get_sqlite_connection()
    return _get_sqlite_connection()


def initialize_database() -> None:
    backend = _resolve_database_backend()
    if backend == "pg":
        try:
            _initialize_postgres_database()
            return
        except Exception:
            _initialize_sqlite_database()
            return
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
                message_count integer not null default 0
            )
            """
        )
        connection.execute(
            """
            create table if not exists knowledge_bases (
                id text primary key,
                name text not null,
                product text not null,
                document_count integer not null default 0
            )
            """
        )
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
                content text not null,
                status text not null default 'indexed',
                created_at text not null default current_timestamp,
                foreign key (knowledge_base_id) references knowledge_bases (id)
            )
            """
        )
        connection.execute(
            """
            create table if not exists knowledge_chunks (
                id integer primary key autoincrement,
                knowledge_base_id text not null,
                document_id integer not null,
                chunk_index integer not null,
                content text not null,
                char_count integer not null,
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
            create table if not exists ingestion_task_nodes (
                id integer primary key autoincrement,
                task_id integer not null,
                node_type text not null,
                node_order integer not null,
                success integer not null,
                message text not null default '',
                duration_ms integer not null default 0,
                created_at text not null default current_timestamp,
                foreign key (task_id) references ingestion_tasks (id)
            )
            """
        )
        connection.execute(
            """
            create table if not exists conversation_messages (
                id integer primary key autoincrement,
                session_id text not null,
                role text not null,
                content text not null,
                created_at text not null default current_timestamp
            )
            """
        )
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
                    message_count integer not null default 0
                )
                """
            )
            cursor.execute(
                """
                create table if not exists knowledge_bases (
                    id text primary key,
                    name text not null,
                    product text not null,
                    document_count integer not null default 0
                )
                """
            )
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
                    content text not null,
                    status text not null default 'indexed',
                    created_at timestamptz not null default now()
                )
                """
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
                    strategy text not null default 'recursive',
                    document_type text not null default 'manual',
                    metadata_json jsonb not null default '{}'::jsonb,
                    created_at timestamptz not null default now()
                )
                """
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
                create table if not exists ingestion_task_nodes (
                    id bigint generated by default as identity primary key,
                    task_id bigint not null references ingestion_tasks(id) on delete cascade,
                    node_type text not null,
                    node_order integer not null,
                    success integer not null,
                    message text not null default '',
                    duration_ms integer not null default 0,
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists conversation_messages (
                    id bigint generated by default as identity primary key,
                    session_id text not null references sessions(id) on delete cascade,
                    role text not null,
                    content text not null,
                    created_at timestamptz not null default now()
                )
                """
            )
            cursor.execute("create index if not exists idx_knowledge_documents_kb on knowledge_documents (knowledge_base_id)")
            cursor.execute("create index if not exists idx_knowledge_chunks_doc on knowledge_chunks (document_id, chunk_index)")
            cursor.execute("create index if not exists idx_structured_blocks_doc on knowledge_document_blocks (document_id, block_index)")
            cursor.execute("create index if not exists idx_table_cells_block on knowledge_document_table_cells (block_id, row_index, column_index)")
            cursor.execute("create index if not exists idx_ingestion_tasks_doc on ingestion_tasks (document_id, created_at desc)")
            cursor.execute("create index if not exists idx_ingestion_task_nodes_task on ingestion_task_nodes (task_id, node_order)")
            cursor.execute("create index if not exists idx_conversation_messages_session on conversation_messages (session_id, id)")

        _seed_demo_data(connection)
        connection.commit()


def _seed_demo_data(connection: DatabaseConnection) -> None:
    session_count = connection.execute("select count(*) from sessions").fetchone()[0]
    if session_count == 0:
        connection.execute(
            """
            insert into sessions (id, title, message_count)
            values (?, ?, ?)
            """,
            ("session-demo-1", "RetriFlow migration planning", 6),
        )

    knowledge_count = connection.execute("select count(*) from knowledge_bases").fetchone()[0]
    if knowledge_count == 0:
        connection.execute(
            """
            insert into knowledge_bases (id, name, product, document_count)
            values (?, ?, ?, ?)
            """,
            ("kb-demo-1", "RetriFlow product knowledge base", "RetriFlow", 1),
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
                "RetriFlow product knowledge base migration python vue rag langgraph langchain",
                '["RetriFlow 是什么？", "RetriFlow 的迁移目标是什么？"]',
                '["retriflow", "langgraph", "langchain", "migration", "rag"]',
            ),
        )

    document_count = connection.execute("select count(*) from knowledge_documents").fetchone()[0]
    if document_count == 0:
        connection.execute(
            """
            insert into knowledge_documents (id, knowledge_base_id, title, source_type, content, status)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "kb-demo-1",
                "RetriFlow migration baseline",
                "manual",
                "RetriFlow migrates ragent capabilities into a Python and Vue stack.",
                "indexed",
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
                "RetriFlow migrates ragent capabilities into a Python and Vue stack.",
                len("RetriFlow migrates ragent capabilities into a Python and Vue stack."),
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
            insert into ingestion_task_nodes (task_id, node_type, node_order, success, message, duration_ms)
            values (?, ?, ?, ?, ?, ?)
            """,
            [
                (task_id, "normalize", 1, 1, "Normalized source text and preserved paragraph boundaries.", 1),
                (task_id, "segment", 2, 1, "Derived 1 semantic segments from source text.", 1),
                (task_id, "chunk", 3, 1, "Generated 1 chunks with overlap-aware chunking.", 1),
                (task_id, "index", 4, 1, "Indexed chunks into the local retrieval store.", 1),
            ],
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
