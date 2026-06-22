-- RetriFlow PostgreSQL seed data
-- Usage:
-- 1. Run tools/postgres/schema_pg.sql first.
-- 2. Then run this file to insert demo seed data.

-- ============================================
-- Seed User
-- ============================================

INSERT INTO users (id, username, password_hash, role)
VALUES (
    'user-admin',
    'admin',
    'retriflow-seed-salt$3dcb8cd47f903b433a8eb58c95de902033e5a86d8956a4ddc51020965710a67d',
    'admin'
)
ON CONFLICT (id) DO UPDATE
SET
    username = EXCLUDED.username,
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role;

-- ============================================
-- Seed Sessions
-- ============================================

INSERT INTO sessions (id, title, message_count, owner_id)
VALUES ('session-demo-1', 'RetriFlow migration planning', 6, '')
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Seed Knowledge Base
-- ============================================

INSERT INTO knowledge_bases (
    id,
    name,
    product,
    document_count,
    embedding_model,
    collection_name,
    owner
)
VALUES (
    'kb-demo-1',
    'RetriFlow product knowledge base',
    'RetriFlow',
    1,
    'Qwen/Qwen3-Embedding-8B',
    'kbdemo1',
    'admin'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO knowledge_base_route_profiles (
    knowledge_base_id,
    profile_text,
    sample_questions_json,
    keywords_json
)
VALUES (
    'kb-demo-1',
    'RetriFlow product knowledge base migration python vue rag langgraph langchain',
    '["RetriFlow 是什么？", "RetriFlow 的迁移目标是什么？"]'::jsonb,
    '["retriflow", "langgraph", "langchain", "migration", "rag"]'::jsonb
)
ON CONFLICT (knowledge_base_id) DO NOTHING;

-- ============================================
-- Seed Knowledge Document
-- ============================================

INSERT INTO knowledge_documents (
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
VALUES (
    1,
    'kb-demo-1',
    'RetriFlow migration baseline',
    'manual',
    'RetriFlow migrates ragent capabilities into a Python and Vue stack.',
    'indexed',
    'indexed',
    1,
    '2026-06-09 10:00:00+08'
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
VALUES
    (1, 1, 'normalize', 'normalize', 1, 1, 'success', 'Normalized source text and preserved paragraph boundaries.', '', '{}'::jsonb, 1),
    (2, 1, 'segment', 'segment', 2, 1, 'success', 'Derived 1 semantic segments from source text.', '', '{"segmentCount":1}'::jsonb, 1),
    (3, 1, 'chunk', 'chunk', 3, 1, 'success', 'Generated 1 chunks with overlap-aware chunking.', '', '{"chunkCount":1}'::jsonb, 1),
    (4, 1, 'index', 'index', 4, 1, 'success', 'Indexed chunks into the local retrieval store.', '', '{"settings":{"store":"local"},"chunkCount":1}'::jsonb, 1)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Seed Ingestion Pipeline
-- ============================================

INSERT INTO ingestion_pipelines (
    id,
    name,
    description,
    nodes_json,
    owner
)
VALUES (
    1,
    'retriflow-ingestion-pipeline',
    'Document ingestion pipeline: Apache Tika parse, structured extraction, chunking, embedding and indexing.',
    '[
      {"node_id":"parse","node_type":"parser","next_node_id":"extract","condition":"","config":{"engine":"apache-tika","preserve_structure":true}},
      {"node_id":"extract","node_type":"extractor","next_node_id":"chunk","condition":"","config":{"extract":["paragraph","heading","table","image_caption","page_number"]}},
      {"node_id":"chunk","node_type":"chunker","next_node_id":"embed","condition":"","config":{"strategy":"auto","chunk_size":600,"chunk_overlap":120}},
      {"node_id":"embed","node_type":"embedder","next_node_id":"index","condition":"","config":{"provider":"siliconflow","model":"qwen-emb-8b"}},
      {"node_id":"index","node_type":"indexer","next_node_id":"","condition":"","config":{"store":"pgvector"}}
    ]'::jsonb,
    'admin'
)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- Seed Admin Intent & Keyword Config
-- ============================================

INSERT INTO admin_intent_nodes (
    id,
    name,
    code,
    level,
    node_type,
    parent_id,
    knowledge_base_id,
    collection_name,
    description,
    sample_questions_json,
    rule_snippet,
    prompt_template,
    top_k,
    sort_order,
    enabled
)
VALUES (
    'intent-demo-retriflow',
    'RetriFlow 知识检索',
    'retriflow_knowledge',
    'DOMAIN',
    'KB',
    'ROOT',
    'kb-demo-1',
    'retriflow_chunk_vectors',
    '用于识别 RetriFlow 项目规划、RAG 流程、迁移目标相关问题。',
    '["RetriFlow 一期应该先做什么？", "RetriFlow 的迁移目标是什么？"]'::jsonb,
    '命中 retriflow、rag、langgraph、langchain、迁移等关键词时优先进入该节点。',
    '根据 RetriFlow 知识库内容进行回答，必须引用来源。',
    5,
    10,
    1
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO admin_keyword_mappings (
    id,
    raw_keyword,
    target_keyword,
    match_type,
    priority,
    enabled,
    remark,
    knowledge_base_id
)
VALUES
    ('keyword-demo-rag', 'rag', 'RAG 检索增强生成', 'contains', 20, 1, 'RAG 相关问题归一化', 'kb-demo-1'),
    ('keyword-demo-retriflow', 'retriflow', 'RetriFlow', 'contains', 30, 1, '项目名称命中', 'kb-demo-1')
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

-- ============================================
-- Refresh Identity Sequences
-- ============================================
-- PostgreSQL identity sequences are not advanced by explicit id values in seed
-- inserts. Keep them aligned so the backend can insert new rows after seeding.

SELECT setval(
    pg_get_serial_sequence('knowledge_documents', 'id'),
    COALESCE((SELECT MAX(id) FROM knowledge_documents), 1),
    (SELECT MAX(id) IS NOT NULL FROM knowledge_documents)
);

SELECT setval(
    pg_get_serial_sequence('knowledge_chunks', 'id'),
    COALESCE((SELECT MAX(id) FROM knowledge_chunks), 1),
    (SELECT MAX(id) IS NOT NULL FROM knowledge_chunks)
);

SELECT setval(
    pg_get_serial_sequence('ingestion_tasks', 'id'),
    COALESCE((SELECT MAX(id) FROM ingestion_tasks), 1),
    (SELECT MAX(id) IS NOT NULL FROM ingestion_tasks)
);

SELECT setval(
    pg_get_serial_sequence('ingestion_task_nodes', 'id'),
    COALESCE((SELECT MAX(id) FROM ingestion_task_nodes), 1),
    (SELECT MAX(id) IS NOT NULL FROM ingestion_task_nodes)
);

SELECT setval(
    pg_get_serial_sequence('ingestion_pipelines', 'id'),
    COALESCE((SELECT MAX(id) FROM ingestion_pipelines), 1),
    (SELECT MAX(id) IS NOT NULL FROM ingestion_pipelines)
);

