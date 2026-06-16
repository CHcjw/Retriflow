# 技术设计文档（TECH_DESIGN）

## 技术栈选择

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Axios
- SSE / ReadableStream

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

- PostgreSQL：主业务数据库。
- pgvector：向量持久化，默认向量表为 `retriflow_chunk_vectors`。
- SQLite：仅用于测试和兼容 fallback。
- 内存向量存储：仅用于测试或本地降级。

### 本地服务

- Apache Tika：文档解析和 MIME 检测。
- OCR 服务：图片文字识别和图片说明辅助。
- Docker Desktop：推荐用于管理 Tika、OCR、PostgreSQL + pgvector 等本地依赖。

## 项目结构

```text
RetriFlow/
|-- backend/
|   `-- src/
|       |-- api/
|       |   |-- deps/
|       |   `-- routes/
|       |-- core/
|       |-- modules/
|       |   |-- admin/
|       |   |-- auth/
|       |   |-- chat/
|       |   |-- ingestion/
|       |   |-- knowledge/
|       |   |-- mcp/
|       |   |-- memory/
|       |   |-- observability/
|       |   |-- rag/
|       |   `-- session/
|       |-- infra/
|       |   |-- document_parser/
|       |   |-- embeddings/
|       |   |-- llm/
|       |   `-- vector_store/
|       |-- schemas/
|       `-- tests/
|-- frontend/
|   `-- src/
|       |-- components/
|       |-- composables/
|       |-- router/
|       |-- services/
|       |-- stores/
|       `-- views/
|-- docx/
|-- docs/
|-- tools/
|   `-- postgres/
|-- docker-compose.services.yml
|-- .env
`-- .env.example
```

## 后端架构模式

当前后端已经从早期 `domain` 大包迁移为 `modules + infra` 主架构，`domain/` 目录已删除：

- `api/`：FastAPI 路由和鉴权依赖，保持薄层。
- `core/`：配置、数据库连接、初始化、补表、seed。
- `modules/`：业务模块和应用服务。
- `infra/`：外部服务和基础设施适配。
- `schemas/`：Pydantic 入参、出参和结构化文档模型。
- `domain/`：已删除，不再作为业务目录或兼容 facade。

### modules

- `modules/auth`：注册、登录、密码哈希、Token。
- `modules/session`：会话列表、创建、删除、消息读取和 owner 权限。
- `modules/chat`：非流式聊天、流式聊天、消息持久化、生成耗时记录。
- `modules/knowledge`：知识库、文档、切块、结构化块、知识库路由画像。
- `modules/ingestion`：分块策略、入库流水线、任务和节点日志。
- `modules/memory`：短期、中期、长期记忆。
- `modules/mcp`：MCP 工具注册、参数提取、远程客户端、执行编排。
- `modules/rag`：意图识别、查询重写、检索、RRF、rerank、答案后处理、工作流适配。
- `modules/admin`：Dashboard、用户、意图树、关键词映射、流水线、链路追踪、系统设置。

### infra

- `infra/llm`：OpenAI-compatible LLM 调用、三段式 Prompt、JSON 提取、模型路由。
- `infra/embeddings`：embedding provider 和本地 fallback。
- `infra/vector_store`：pgvector 和内存向量存储。
- `infra/document_parser`：Tika client、结构化提取、标准化清洗、OCR 图片说明、上传解析服务。

### domain

`domain/` 已删除。旧导入应迁移到 `modules/` 或 `infra/` 的真实路径；测试也必须 patch 新路径。详细说明见 `docs/domain_facade_notes.md`。
## 数据模型

### 用户与会话

- `users`：用户、密码哈希、角色。
- `sessions`：会话元数据、标题、消息数、owner。
- `conversation_messages`：用户和助手消息，含 `duration_ms`。
- `conversation_memory_summaries`：短期记忆摘要。
- `conversation_mid_memories`：中期记忆。
- `conversation_long_memories`：长期记忆。

### 知识库与文档

- `knowledge_bases`：知识库基础信息。
- `knowledge_base_route_profiles`：知识库路由画像、示例问题、关键词。
- `knowledge_documents`：文档元数据、标准化文本、索引状态。
- `knowledge_chunks`：chunk 内容、策略、文档类型、元数据、启停状态。
- `knowledge_document_blocks`：结构化文档块，保留段落、标题、表格、图片说明和页码。
- `knowledge_document_table_cells`：表格 row / col / header 关系。

### 入库与流水线

- `ingestion_tasks`：文档入库和重建索引任务。
- `ingestion_task_nodes`：流水线节点日志和耗时。
- `ingestion_pipelines`：后台流水线配置。

### 管理后台

- `admin_intent_nodes`：意图树节点配置。
- `admin_keyword_mappings`：关键词映射配置。
- 其他后台统计数据主要基于真实业务表实时聚合。

### 向量

- `retriflow_chunk_vectors`：pgvector 向量表，由后端按当前 embedding 维度自动建表。

## RAG 主链路

标准执行顺序：

1. 加载会话记忆。
2. 意图识别。
3. 查询重写和多意图拆分。
4. 知识库路由。
5. BM25 Top80。
6. 向量 Top80。
7. RRF Top50。
8. rerank Top10。
9. final Top5。
10. 构建三段式 Prompt。
11. LLM 生成答案。
12. 答案后处理。
13. 持久化消息、耗时和记忆。

## 文档解析链路

1. Tika 检测真实 MIME 类型。
2. Tika 解析 XHTML 和 metadata。
3. 提取正文段落、标题层级、表格、图片说明和页码。
4. 对 DOCX/PDF 内嵌图片尝试 OCR 提取图片说明。
5. 标准化清洗文本、表格单元格和空值。
6. 使用 Pydantic schema 校验结构化文档。
7. 转换为 ingestion text 和 LangChain Document。
8. 进入分块、索引和向量写入。

## PostgreSQL SQL 脚本

脚本目录：`tools/postgres/`

- `schema_pg.sql`：创建业务表、索引、扩展和兼容字段。
- `init_data_pg.sql`：插入默认管理员、示例知识库、示例文档、示例 chunk、默认流水线、意图节点和关键词映射。
- `inspect_pg.sql`：用于 HeidiSQL / DBeaver / pgAdmin 等工具检查表结构和数据。

执行顺序：

```sql
-- 1. 先执行 schema_pg.sql
-- 2. 再执行 init_data_pg.sql
-- 3. 如需排查，再执行 inspect_pg.sql
```

默认管理员：

```text
username: admin
password: admin
role: admin
```

## 关键技术点

- 测试环境必须显式设置 SQLite 和内存向量存储，避免连接本地 PostgreSQL / pgvector。
- 生产环境默认 PostgreSQL + pgvector。
- `domain/` 已删除，新功能不要重新堆到 `domain/` 或恢复兼容 facade。
- 需要 patch 依赖时，应 patch 新模块的真实路径，例如 `modules.rag.workflow_adapter`、`modules.knowledge.service`、`infra.document_parser.service`。
- 文档解析和 OCR 外部服务不可用时必须可降级，不能静默卡死。
- 流式回答最终持久化前要做答案后处理，但不能让前端先显示整段最终答案再假装流式。
- 链路追踪和 Dashboard 优先使用 `conversation_messages.duration_ms` 的真实耗时。

## 验证命令

本轮架构迁移相关回归：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_tika_client.py backend/src/tests/retriflow_backend/test_document_parser.py backend/src/tests/retriflow_backend/test_document_structure.py backend/src/tests/retriflow_backend/test_document_normalizer.py backend/src/tests/retriflow_backend/test_document_caption_enrichment.py backend/src/tests/retriflow_backend/test_ingestion_pipeline.py backend/src/tests/retriflow_backend/test_ingestion_api.py backend/src/tests/retriflow_backend/test_knowledge_api.py backend/src/tests/retriflow_backend/test_knowledge_document_api.py backend/src/tests/retriflow_backend/test_vector_store.py backend/src/tests/retriflow_backend/test_retrieval_engine.py backend/src/tests/retriflow_backend/test_reranker.py backend/src/tests/retriflow_backend/test_chat_api.py backend/src/tests/retriflow_backend/test_chat_mcp_api.py backend/src/tests/retriflow_backend/test_memory_service.py backend/src/tests/retriflow_backend/test_model_routing.py -q
```

前端构建：

```powershell
cd frontend
cmd /c npm.cmd run build
```
