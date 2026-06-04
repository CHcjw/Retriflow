-- RetriFlow PostgreSQL seed data
-- Reference style: ragent/resources/database/init_data_pg.sql
--
-- Usage:
-- 1. Run tools/postgres/schema_pg.sql first.
-- 2. Then run this file to insert demo seed data.

-- ============================================
-- Seed Sessions
-- ============================================

INSERT INTO sessions (id, title, message_count)
VALUES ('session-demo-1', 'RetriFlow migration planning', 6)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Seed Knowledge Base
-- ============================================

INSERT INTO knowledge_bases (id, name, product, document_count)
VALUES ('kb-demo-1', 'RetriFlow product knowledge base', 'RetriFlow', 1)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Seed Knowledge Document
-- ============================================

INSERT INTO knowledge_documents (id, knowledge_base_id, title, source_type, content, status)
VALUES (
    1,
    'kb-demo-1',
    'RetriFlow migration baseline',
    'manual',
    'RetriFlow migrates ragent capabilities into a Python and Vue stack.',
    'indexed'
)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Seed Knowledge Chunk
-- ============================================

INSERT INTO knowledge_chunks (
    id,
    knowledge_base_id,
    document_id,
    chunk_index,
    content,
    char_count,
    strategy,
    document_type,
    metadata_json
)
VALUES (
    1,
    'kb-demo-1',
    1,
    0,
    'RetriFlow migrates ragent capabilities into a Python and Vue stack.',
    68,
    'recursive',
    'manual',
    '{}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Seed Ingestion Task
-- ============================================

INSERT INTO ingestion_tasks (
    id,
    knowledge_base_id,
    document_id,
    source_type,
    status,
    chunk_count,
    message
)
VALUES (
    1,
    'kb-demo-1',
    1,
    'manual',
    'completed',
    1,
    'RetriFlow ingestion pipeline completed.'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO ingestion_task_nodes (
    id,
    task_id,
    node_type,
    node_order,
    success,
    message,
    duration_ms
)
VALUES
    (1, 1, 'normalize', 1, 1, 'Normalized source text and preserved paragraph boundaries.', 1),
    (2, 1, 'segment', 2, 1, 'Derived 1 semantic segments from source text.', 1),
    (3, 1, 'chunk', 3, 1, 'Generated 1 chunks with overlap-aware chunking.', 1),
    (4, 1, 'index', 4, 1, 'Indexed chunks into the local retrieval store.', 1)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Refresh Aggregates
-- ============================================

UPDATE knowledge_bases
SET document_count = (
    SELECT COUNT(*)
    FROM knowledge_documents
    WHERE knowledge_documents.knowledge_base_id = knowledge_bases.id
);
