# 技术设计文档（TECH_DESIGN）

## 技术栈选择

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Axios

### 后端

- Python 3.12
- FastAPI
- LangChain
- LangGraph
- LangSmith
- Pydantic
- httpx
- psycopg

### 数据库与存储

- PostgreSQL
  - 业务主库
  - 存储会话、消息、知识库、文档、chunks、structured blocks、ingestion tasks
- pgvector
  - 与 PostgreSQL 同库部署
  - 存储 `retriflow_chunk_vectors`
- SQLite
  - 仅用于测试隔离与兼容模式

### 本地依赖服务

- Apache Tika
- OCR 服务
- PostgreSQL + pgvector

## 项目结构

```text
RetriFlow/
|-- backend/
|   `-- src/
|       |-- api/
|       |-- core/
|       |-- domain/
|       |-- schemas/
|       `-- tests/
|-- frontend/
|   `-- src/
|-- docx/
|-- docs/
|-- tools/
`-- docker-compose.services.yml
```

### 核心后端模块

- `backend/src/main.py`
  - 应用工厂入口
  - 使用 `create_app()` 启动，避免导入阶段提前初始化
- `backend/src/core/config.py`
  - 统一读取模型、数据库、Tika、OCR、LangSmith 配置
- `backend/src/core/state.py`
  - 数据库连接抽象
  - PostgreSQL / SQLite 初始化
- `backend/src/domain/document_parser.py`
  - Tika 解析、结构化提取、文本 fallback
- `backend/src/domain/ingestion.py`
  - 清洗、分块、后处理
- `backend/src/domain/vector_store.py`
  - pgvector 持久化与向量检索
- `backend/src/domain/retrieval.py`
  - 混合检索主链路
- `backend/src/domain/reranker.py`
  - rerank 服务封装
- `backend/src/domain/knowledge_route.py`
  - 首页直聊知识库意图路由
- `backend/src/domain/llm.py`
  - 三段式 Prompt 与 LLM 调用
- `backend/src/domain/answer_postprocessor.py`
  - 引用、来源、冲突提示、安全过滤
- `backend/src/domain/workflow_adapter.py`
  - Fallback / LangGraph 工作流适配

## 数据模型

### 业务表

#### `sessions`

- `id`
- `title`
- `message_count`

#### `conversation_messages`

- `id`
- `session_id`
- `role`
- `content`
- `created_at`

#### `knowledge_bases`

- `id`
- `name`
- `product`
- `document_count`

#### `knowledge_base_route_profiles`

- `knowledge_base_id`
- `profile_text`
- `sample_questions_json`
- `keywords_json`
- `updated_at`

#### `knowledge_documents`

- `id`
- `knowledge_base_id`
- `title`
- `source_type`
- `content`
- `status`
- `created_at`

#### `knowledge_chunks`

- `id`
- `knowledge_base_id`
- `document_id`
- `chunk_index`
- `content`
- `char_count`
- `strategy`
- `document_type`
- `metadata_json`
- `created_at`

#### `knowledge_document_blocks`

- `id`
- `knowledge_base_id`
- `document_id`
- `block_index`
- `block_type`
- `page_number`
- `heading_path_json`
- `level`
- `text`
- `headers_json`
- `row_count`
- `column_count`
- `caption`
- `created_at`

#### `knowledge_document_table_cells`

- `id`
- `block_id`
- `row_index`
- `column_index`
- `text`
- `is_header`
- `created_at`

#### `ingestion_tasks`

- `id`
- `knowledge_base_id`
- `document_id`
- `source_type`
- `status`
- `chunk_count`
- `message`
- `created_at`

#### `ingestion_task_nodes`

- `id`
- `task_id`
- `node_type`
- `node_order`
- `success`
- `message`
- `duration_ms`
- `created_at`

### 向量表

#### `retriflow_chunk_vectors`

- `chunk_id`
- `knowledge_base_id`
- `document_id`
- `document_title`
- `content`
- `document_type`
- `strategy`
- `metadata_json`
- `embedding`
- `updated_at`

## 关键技术点

### 1. 首页直接聊天 + 知识库意图路由

- 用户先提问，不强制先选知识库
- 路由服务先分析问题与知识库画像
- 知识库画像持久化到 `knowledge_base_route_profiles`
- 高置信度时限定到命中的知识库检索
- 低置信度时回退到全局检索
- 可选启用 LLM 路由，失败时自动退回本地画像匹配

### 2. 混合检索主链路

当前实现已经切换为标准链路：

1. BM25 检索 Top80
2. 纯向量检索 Top80
3. RRF 融合 Top50
4. rerank Top10
5. 最终返回 Top5

当前 `workflow.retrieval_channels` 返回：

- `bm25`
- `semantic`
- `hybrid_rrf`
- `rerank`

### 3. 向量检索范围过滤

- BM25 与向量检索都支持 `knowledge_base_ids` 范围过滤
- 便于首页聊天先路由、后限定召回

### 4. rerank 服务设计

- 优先使用 OpenAI-compatible API 的 `/rerank`
- 使用配置中的 `default_rerank_model`
- 当 rerank 服务不可用时，回退到本地轻量排序逻辑

### 5. 生成答案链路

- 使用三段式 Prompt
  - System Prompt
  - Retrieved Context
  - User Query
- 生成温度固定为 `0.1`
- 后处理负责：
  - 自动补引用
  - 自动追加 `## 参考来源`
  - 冲突提示
  - 基础安全过滤
- 流式问答结束后会生成最终版答案并落库，而不是只保存原始分片

### 6. 流式聊天容错

- LangGraph 流式生成过程中，如果模型流在迭代阶段抛错，系统会自动降级为 fallback 文本
- SSE 输出包含：
  - `workflow`
  - `sources`
  - `delta`
  - `final`
  - `done`

### 7. 应用启动方式

- `backend/src/main.py` 采用工厂模式启动
- CLI 启动方式：

```powershell
& .\.venv\Scripts\python.exe .\backend\src\main.py
```

- `uvicorn` 实际使用 `main:create_app` + `factory=True`
- 避免测试和运行时在模块导入阶段提前初始化错误环境

### 8. SQL 脚本入口

保留 3 个主入口：

- `tools/postgres/schema_pg.sql`
- `tools/postgres/init_data_pg.sql`
- `tools/postgres/inspect_pg.sql`

## 当前实现状态

### 已完成

- Tika 解析链路
- 结构化 block 持久化
- 多策略分块
- 向量持久化
- 首页直聊知识库路由
- 混合检索
- LangGraph 最小工作流
- 同步 / 流式聊天
- 生成答案与后处理

### 待继续增强

- 更强的 LLM 知识库路由
- 更稳定的生产级 reranker 适配
- 更复杂的 LangGraph 多节点编排
- 检索评测与召回质量监控
- 更强的前端来源富展示
