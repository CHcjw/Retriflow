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
      {"node_id":"embed","node_type":"embedder","next_node_id":"index","condition":"","config":{"provider":"siliconflow","model":"Qwen/Qwen3-Embedding-8B"}},
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
-- Seed Admin Intent & Keyword Config
-- ============================================

DELETE FROM admin_intent_nodes
WHERE id IN (
    'invoice',
    'intent-sales',
    'intent-ticket',
    'intent-weather',
    'intent-sales-data',
    'intent-ticket-data',
    'intent-weather-data',
    'intent-sys',
    'intent-sys-welcome',
    'intent-sys-about-bot',
    'intent-sys-feedback'
);

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
VALUES
    (
        'invoice',
        '发票信息',
        'invoice',
        'DOMAIN',
        'KB',
        'ROOT',
        'kb-demo-1',
        'retriflow_chunk_vectors',
        '发票、票据、报销凭证等知识库检索问题。',
        '[]'::jsonb,
        '发票信息、票据、报销凭证等问题进入知识库检索。',
        '根据关联知识库内容回答，必要时引用来源。',
        5,
        10,
        1
    ),
    (
        'sales',
        '销售汇总数据统计',
        'sales',
        'DOMAIN',
        'MCP',
        'ROOT',
        '',
        '',
        '',
        '[]'::jsonb,
        '销售、销售汇总、销售统计、销售数据相关问题进入销售汇总数据统计意图。',
        '',
        NULL,
        13,
        1
    ),
    (
        'ticket',
        '客户工单服务管理',
        'ticket',
        'DOMAIN',
        'MCP',
        'ROOT',
        '',
        '',
        '',
        '[]'::jsonb,
        '客户工单、技术支持、工单状态、工单数量、处理进度相关问题进入客户工单服务管理意图。',
        '',
        NULL,
        15,
        1
    ),
    (
        'weather',
        '天气信息查询服务',
        'weather',
        'DOMAIN',
        'MCP',
        'ROOT',
        '',
        '',
        '',
        '[]'::jsonb,
        '城市天气、天气预报、温度、湿度、风力、空气质量相关问题进入天气信息查询服务意图。',
        '',
        NULL,
        17,
        1
    ),
    (
        'sales-data',
        '销售数据统计',
        'sales-data',
        'CATEGORY',
        'MCP',
        'sales',
        '',
        '',
        '销售数据统计，如：销售总额、销售量、销售占比、销售趋势、销售预测等。',
        '["销售总额是多少？", "销售量是多少？", "今年的销售业绩", "某位员工的销售业绩如何？", "华东销售额是多少？", "华南销售额是多少？"]'::jsonb,
        '识别销售总额、销售量、销售业绩、区域销售额等统计查询。',
        '你是工具参数提取器，任务是从用户问题中提取销售查询工具所需参数，并以合法 JSON 对象输出。不要输出 JSON 之外的解释。',
        NULL,
        14,
        1
    ),
    (
        'ticket-data',
        '客户工单查询',
        'ticket-data',
        'CATEGORY',
        'MCP',
        'ticket',
        '',
        '',
        '客户技术支持工单查询，如：工单状态、工单数量、解决率、紧急工单、处理进度等。',
        '["华东区有多少待处理工单？", "紧急工单有哪些？", "本月工单解决率是多少？", "腾讯科技的工单进展如何？", "企业版产品有多少未关闭工单？", "各地区工单数量统计"]'::jsonb,
        '识别待处理工单、紧急工单、解决率、客户工单进展、未关闭工单等查询。',
        '你是工具参数提取器，任务是从用户问题中提取工单查询工具所需参数，并以合法 JSON 对象输出。不要输出 JSON 之外的解释。',
        NULL,
        16,
        1
    ),
    (
        'weather-data',
        '天气查询',
        'weather-data',
        'CATEGORY',
        'MCP',
        'weather',
        '',
        '',
        '城市天气信息查询，如：当前天气、天气预报、温度、湿度、风力、空气质量等。',
        '["北京今天天气怎么样？", "上海明天会下雨吗？", "广州未来三天天气预报", "杭州现在多少度？", "成都这周天气如何？", "深圳空气质量怎么样？"]'::jsonb,
        '识别城市天气、天气预报、气温、空气质量等查询。',
        '你是工具参数提取器，任务是从用户问题中提取天气查询工具所需参数，并以合法 JSON 对象输出。不要输出 JSON 之外的解释。',
        NULL,
        18,
        1
    ),
    (
        'sys',
        '系统交互',
        'sys',
        'DOMAIN',
        'SYSTEM',
        'ROOT',
        '',
        '',
        '',
        '[]'::jsonb,
        '系统交互、欢迎问候、关于助手、情感反馈等通用交互意图。',
        '',
        NULL,
        15,
        1
    ),
    (
        'sys-welcome',
        '欢迎与问候',
        'sys-welcome',
        'CATEGORY',
        'SYSTEM',
        'sys',
        '',
        '',
        '用户与助手打招呼，如：你好、早上好、hi、在吗 等。',
        '["你好", "hello", "早上好", "在吗", "嗨"]'::jsonb,
        '识别用户问候、打招呼、确认助手是否在线等表达。',
        '',
        NULL,
        16,
        1
    ),
    (
        'sys-about-bot',
        '关于助手',
        'sys-about-bot',
        'CATEGORY',
        'SYSTEM',
        'sys',
        '',
        '',
        '询问助手是做什么的、是谁、能做什么等。',
        '["你是谁", "你是做什么的", "你能帮我做什么", "你是什么AI"]'::jsonb,
        '识别询问助手身份、能力范围、用途的表达。',
        '',
        NULL,
        17,
        1
    ),
    (
        'sys-feedback',
        '情感反馈',
        'sys-feedback',
        'CATEGORY',
        'SYSTEM',
        'sys',
        '',
        '',
        '用户对助手回答的情感反馈，包括表扬、感谢、质疑、纠正、不满等情绪表达。',
        '["真棒", "好样的", "太厉害了", "说得好", "你说的不对", "不太准确", "回答得不错", "谢谢你", "辛苦了", "答非所问", "很有帮助", "太棒了", "回答的一般"]'::jsonb,
        '识别用户对回答质量和情绪态度的反馈。',
        '你是企业内部知识助手「小码」。用户刚才对你的回答给出了情感反馈。请根据对话上下文判断用户情绪倾向，并做出自然、简短、有温度的回应：正向反馈真诚回应，负向反馈先表达歉意并询问哪里不准确，中性反馈自然回应。只回应用户情绪，1-2句话，不超过100字。',
        NULL,
        18,
        1
    )
ON CONFLICT (id) DO UPDATE
SET
    name = EXCLUDED.name,
    code = EXCLUDED.code,
    level = EXCLUDED.level,
    node_type = EXCLUDED.node_type,
    parent_id = EXCLUDED.parent_id,
    knowledge_base_id = EXCLUDED.knowledge_base_id,
    collection_name = EXCLUDED.collection_name,
    description = EXCLUDED.description,
    sample_questions_json = EXCLUDED.sample_questions_json,
    rule_snippet = EXCLUDED.rule_snippet,
    prompt_template = EXCLUDED.prompt_template,
    top_k = EXCLUDED.top_k,
    sort_order = EXCLUDED.sort_order,
    enabled = EXCLUDED.enabled,
    updated_at = NOW();

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

UPDATE knowledge_base_route_profiles
SET
    sample_questions_json = '[
      "询问助手是做什么的、是谁、能做什么等",
      "数据权限、访问控制、安全审计等相关说明",
      "销售数据统计，如：销售总额、销售量、销售占比、销售趋势、销售预测等"
    ]'::jsonb,
    keywords_json = '["系统交互", "业务系统", "实时数据", "数据安全", "销售汇总数据统计"]'::jsonb
WHERE knowledge_base_id = 'kb-demo-1';

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
    pg_get_serial_sequence('ingestion_pipelines', 'id'),
    COALESCE((SELECT MAX(id) FROM ingestion_pipelines), 1),
    (SELECT MAX(id) IS NOT NULL FROM ingestion_pipelines)
);

