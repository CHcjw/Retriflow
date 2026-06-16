-- RetriFlow PostgreSQL inspection script
-- Use this file in HeidiSQL / DBeaver / DataGrip / pgAdmin to inspect the
-- current business tables and vector table status.

-- ============================================
-- Runtime Environment
-- ============================================

SELECT
    current_database() AS current_db,
    current_user AS current_user,
    current_schema() AS current_schema,
    version() AS postgres_version;

SELECT
    extname,
    extversion
FROM pg_extension
WHERE extname = 'vector';

-- ============================================
-- Core Table Status
-- ============================================

SELECT table_name
FROM information_schema.tables
WHERE table_schema = current_schema()
  AND table_name IN (
      'sessions',
      'users',
      'conversation_messages',
      'knowledge_bases',
      'knowledge_base_route_profiles',
      'knowledge_documents',
      'knowledge_chunks',
      'knowledge_document_blocks',
      'knowledge_document_table_cells',
      'admin_intent_nodes',
      'admin_keyword_mappings',
      'ingestion_pipelines',
      'ingestion_tasks',
      'ingestion_task_nodes',
      'conversation_memory_summaries',
      'conversation_mid_memories',
      'conversation_long_memories',
      'retriflow_chunk_vectors'
  )
ORDER BY table_name;

-- ============================================
-- Table Row Counts
-- ============================================

SELECT 'sessions' AS table_name, COUNT(*) AS row_count FROM sessions
UNION ALL
SELECT 'users', COUNT(*) FROM users
UNION ALL
SELECT 'conversation_messages', COUNT(*) FROM conversation_messages
UNION ALL
SELECT 'knowledge_bases', COUNT(*) FROM knowledge_bases
UNION ALL
SELECT 'knowledge_base_route_profiles', COUNT(*) FROM knowledge_base_route_profiles
UNION ALL
SELECT 'knowledge_documents', COUNT(*) FROM knowledge_documents
UNION ALL
SELECT 'knowledge_chunks', COUNT(*) FROM knowledge_chunks
UNION ALL
SELECT 'knowledge_document_blocks', COUNT(*) FROM knowledge_document_blocks
UNION ALL
SELECT 'knowledge_document_table_cells', COUNT(*) FROM knowledge_document_table_cells
UNION ALL
SELECT 'admin_intent_nodes', COUNT(*) FROM admin_intent_nodes
UNION ALL
SELECT 'admin_keyword_mappings', COUNT(*) FROM admin_keyword_mappings
UNION ALL
SELECT 'ingestion_pipelines', COUNT(*) FROM ingestion_pipelines
UNION ALL
SELECT 'ingestion_tasks', COUNT(*) FROM ingestion_tasks
UNION ALL
SELECT 'ingestion_task_nodes', COUNT(*) FROM ingestion_task_nodes
UNION ALL
SELECT 'conversation_memory_summaries', COUNT(*) FROM conversation_memory_summaries
UNION ALL
SELECT 'conversation_mid_memories', COUNT(*) FROM conversation_mid_memories
UNION ALL
SELECT 'conversation_long_memories', COUNT(*) FROM conversation_long_memories
ORDER BY table_name;

-- ============================================
-- Recent Business Records
-- ============================================

SELECT
    id,
    title,
    message_count,
    owner_id
FROM sessions
ORDER BY id
LIMIT 20;

SELECT
    id,
    username,
    role,
    created_at
FROM users
ORDER BY created_at DESC, id DESC
LIMIT 20;

SELECT
    knowledge_base_id,
    LEFT(profile_text, 120) AS profile_preview,
    sample_questions_json,
    keywords_json,
    updated_at
FROM knowledge_base_route_profiles
ORDER BY updated_at DESC
LIMIT 20;

SELECT
    id,
    knowledge_base_id,
    title,
    source_type,
    status,
    vector_index_status,
    vector_chunk_count,
    vector_indexed_at,
    created_at
FROM knowledge_documents
ORDER BY id DESC
LIMIT 20;

SELECT
    id,
    knowledge_base_id,
    document_id,
    chunk_index,
    strategy,
    document_type,
    created_at
FROM knowledge_chunks
ORDER BY id DESC
LIMIT 20;

SELECT
    id,
    knowledge_base_id,
    document_id,
    source_type,
    status,
    chunk_count,
    created_at
FROM ingestion_tasks
ORDER BY id DESC
LIMIT 20;

SELECT
    id,
    name,
    code,
    level,
    node_type,
    parent_id,
    knowledge_base_id,
    enabled,
    updated_at
FROM admin_intent_nodes
ORDER BY parent_id, sort_order, updated_at DESC
LIMIT 50;

SELECT
    id,
    raw_keyword,
    target_keyword,
    match_type,
    priority,
    enabled,
    knowledge_base_id,
    updated_at
FROM admin_keyword_mappings
ORDER BY priority DESC, raw_keyword ASC
LIMIT 50;

SELECT
    id,
    name,
    description,
    jsonb_array_length(nodes_json) AS node_count,
    owner,
    updated_at
FROM ingestion_pipelines
ORDER BY updated_at DESC, id DESC
LIMIT 20;

-- ============================================
-- Structured Document Overview
-- ============================================

SELECT
    block_type,
    COUNT(*) AS block_count
FROM knowledge_document_blocks
GROUP BY block_type
ORDER BY block_count DESC, block_type ASC;

SELECT
    block_id,
    COUNT(*) AS cell_count
FROM knowledge_document_table_cells
GROUP BY block_id
ORDER BY cell_count DESC, block_id ASC
LIMIT 20;

-- ============================================
-- Memory Overview
-- ============================================

SELECT
    session_id,
    last_message_id,
    updated_at,
    expires_at
FROM conversation_memory_summaries
ORDER BY updated_at DESC
LIMIT 20;

SELECT
    session_id,
    memory_type,
    status,
    updated_at,
    expires_at
FROM conversation_mid_memories
ORDER BY updated_at DESC
LIMIT 20;

SELECT
    owner_type,
    owner_id,
    memory_type,
    status,
    updated_at,
    expires_at
FROM conversation_long_memories
ORDER BY updated_at DESC
LIMIT 20;

-- ============================================
-- Vector Overview
-- ============================================

SELECT
    to_regclass('retriflow_chunk_vectors') AS vector_table_name,
    CASE
        WHEN to_regclass('retriflow_chunk_vectors') IS NULL THEN 'missing'
        ELSE 'ready'
    END AS vector_table_status;

SELECT
    relname AS table_name,
    n_live_tup AS approx_row_count
FROM pg_stat_user_tables
WHERE schemaname = current_schema()
  AND relname = 'retriflow_chunk_vectors';

-- Run the following two queries only after retriflow_chunk_vectors exists.
--
-- SELECT
--     chunk_id,
--     knowledge_base_id,
--     document_id,
--     document_title,
--     document_type,
--     strategy,
--     updated_at
-- FROM retriflow_chunk_vectors
-- ORDER BY updated_at DESC
-- LIMIT 20;
--
-- SELECT
--     document_title,
--     COUNT(*) AS chunk_vector_count
-- FROM retriflow_chunk_vectors
-- GROUP BY document_title
-- ORDER BY chunk_vector_count DESC, document_title ASC;

-- ============================================
-- Storage Size
-- ============================================

SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
WHERE schemaname = current_schema()
ORDER BY pg_total_relation_size(relid) DESC, relname ASC;
