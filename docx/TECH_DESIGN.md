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

### 数据存储

- PostgreSQL
  - 作为业务主库
  - 保存会话、消息、知识库、文档、chunks、structured blocks、ingestion tasks
- pgvector
  - 与 PostgreSQL 同库部署
  - 保存 `retriflow_chunk_vectors`
  - 提供语义检索持久化能力
- SQLite
  - 仅保留为兼容模式和测试隔离用途

### 本地依赖服务

- Apache Tika
- OCR 服务
- PostgreSQL + pgvector

## 项目结构

```text
RetriFlow/
|-- backend/
|   |-- pyproject.toml
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
|   |-- tika/
|   |-- ocr/
|   `-- postgres/
`-- docker-compose.services.yml
```

### 关键后端模块

- `backend/src/core/config.py`
  - 统一读取数据库、模型、Tika、OCR、LangSmith 配置
- `backend/src/core/state.py`
  - 数据库连接抽象
  - 支持 PostgreSQL 主模式和 SQLite 兼容模式
  - 负责初始化业务表与种子数据
- `backend/src/domain/document_parser.py`
  - Tika 解析、结构化提取、文本类 fallback
- `backend/src/domain/ingestion.py`
  - 文本标准化、结构化块持久化、分块策略执行
- `backend/src/domain/embeddings.py`
  - Embedding 服务封装与 fallback embedding
- `backend/src/domain/vector_store.py`
  - pgvector 存储、相似度检索、主库 chunk 回填
- `backend/src/domain/retrieval.py`
  - keyword + title + semantic 混合召回
- `backend/src/domain/workflow_adapter.py`
  - LangGraph 工作流适配层

## 数据模型

### PostgreSQL 业务表

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

### 1. PostgreSQL 主库 + pgvector 同库

- 默认运行模式下，业务事实数据和向量数据都进入同一个 PostgreSQL 数据库
- 业务表与向量表通过 `chunk_id` 对齐
- 避免了原先 SQLite 主库与 PostgreSQL 向量库分裂后的运维复杂度

### 2. 数据访问兼容层

- `core/state.py` 提供统一的 `get_connection()`
- 上层业务服务不直接感知 `sqlite3` 或 `psycopg`
- 测试可以继续显式切回 SQLite，降低迁移风险

### 3. 向量持久化策略

- chunk 入库后立即执行 embedding
- 向量写入 `retriflow_chunk_vectors`
- 若 pgvector 不可用，仍可回退到内存向量检索，保证开发环境可用性

### 4. PostgreSQL SQL 脚本

当前只保留 3 个主入口脚本：

- `tools/postgres/schema_pg.sql`
- `tools/postgres/init_data_pg.sql`
- `tools/postgres/inspect_pg.sql`

对应职责：

- `schema_pg.sql`
  - 初始化业务表结构
- `init_data_pg.sql`
  - 初始化 demo 种子数据
- `inspect_pg.sql`
  - 巡检业务表和向量表

补充说明：

- `retriflow_chunk_vectors` 改为由后端首次成功写入 embedding 时自动创建
- 这样可以避免 HeidiSQL 等客户端在执行 `DO $$` 块时出现兼容问题

### 5. 文档解析链路

- 优先使用 Apache Tika 解析 MIME、正文、结构化内容
- OCR 服务用于补充图片文本识别
- 文本类文件在 Tika 不可用时允许 UTF-8 fallback

### 6. 分块策略体系

- 固定大小分块
- 重叠分块
- 递归分块
- Embedding 语义分块
- 递归 + 语义混合分块
- 自动策略选择

### 7. 混合检索路径

- keyword 通道：关键词匹配
- title 通道：文档标题匹配
- semantic 通道：pgvector 相似度检索
- 最终统一去重与排序

## 本地 PostgreSQL 连接信息

- Host: `127.0.0.1`
- Port: `5433`
- Database: `retriflow`
- Username: `retriflow`
- Password: `retriflow`
- Schema: `public`

这些配置当前已经同步到：

- `.env`
- `.env.example`
- `docker-compose.services.yml`
- `docs/local-services.md`
