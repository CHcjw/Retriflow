-- RetriFlow PostgreSQL seed data
-- Usage:
-- 1. Run resource/database/schema_pg.sql first.
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
    'pdf-ingestion-pipeline',
    'PDF文档摄取流水线 - 解析、AI增强、分块、向量化',
    '[
      {"node_id":"parse","node_type":"parser","next_node_id":"ai_enhance","condition":"","config":{"engine":"apache-tika","file_types":["pdf"],"preserve_structure":true}},
      {"node_id":"ai_enhance","node_type":"extractor","next_node_id":"chunk","condition":"","config":{"extract":["paragraph","heading","table","image_caption","page_number"],"normalize_layout":true}},
      {"node_id":"chunk","node_type":"chunker","next_node_id":"embed","condition":"","config":{"strategy":"structure_aware","chunk_size":600,"chunk_overlap":120}},
      {"node_id":"embed","node_type":"embedder","next_node_id":"index","condition":"","config":{"provider":"lmstudio","model":"Qwen/Qwen3-Embedding-8B-GGUF"}},
      {"node_id":"index","node_type":"indexer","next_node_id":"","condition":"","config":{"store":"pgvector"}}
    ]'::jsonb,
    'admin'
)
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    nodes_json = EXCLUDED.nodes_json,
    owner = EXCLUDED.owner,
    updated_at = NOW();

-- ============================================
-- Seed Admin Keyword Config
-- ============================================
-- 意图节点初始化已拆分到 init_intent_nodes_pg.sql。
-- 请先在前端创建需要绑定的知识库，再单独执行该脚本。

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
    ('keyword-k8s', 'K8s', 'Kubernetes', 'exact', 0, 1, '', ''),
    ('keyword-issue', 'issue', '工单', 'exact', 0, 1, '', '')
ON CONFLICT (id) DO UPDATE
SET
    raw_keyword = EXCLUDED.raw_keyword,
    target_keyword = EXCLUDED.target_keyword,
    match_type = EXCLUDED.match_type,
    priority = EXCLUDED.priority,
    enabled = EXCLUDED.enabled,
    remark = EXCLUDED.remark,
    knowledge_base_id = EXCLUDED.knowledge_base_id,
    updated_at = NOW();

INSERT INTO admin_sample_questions (
    id,
    title,
    description,
    question,
    sort_order,
    enabled
)
VALUES
    (
        'sample-system-about',
        '系统交互',
        '关于助手',
        '询问助手是做什么的、是谁、能做什么等',
        10,
        1
    ),
    (
        'sample-business-security',
        '业务系统',
        '数据安全',
        '数据权限、访问控制、安全审计等相关说明',
        20,
        1
    ),
    (
        'sample-realtime-sales',
        '实时数据',
        '销售汇总数据统计',
        '销售数据统计，如：销售总额、销售量、销售占比、销售趋势、销售预测等',
        30,
        1
    )
ON CONFLICT (id) DO UPDATE
SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    question = EXCLUDED.question,
    sort_order = EXCLUDED.sort_order,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

-- ============================================
-- Refresh Identity Sequences
-- ============================================
-- PostgreSQL identity sequences are not advanced by explicit id values in seed
-- inserts. Keep them aligned so the backend can insert new rows after seeding.

SELECT setval(
    pg_get_serial_sequence('ingestion_pipelines', 'id'),
    COALESCE((SELECT MAX(id) FROM ingestion_pipelines), 1),
    (SELECT MAX(id) IS NOT NULL FROM ingestion_pipelines)
);

