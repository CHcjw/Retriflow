# AGENTS 指令文件

## 项目概述

RetriFlow 是一个 Python + Vue 的 Agentic RAG 项目，当前已经具备：

- Tika 结构化解析
- 文档标准化清洗
- 多策略分块
- chunk embedding
- PostgreSQL 主库存储
- pgvector 同库向量持久化
- 混合检索
- LangGraph 最小工作流

## 开发规范

- 后端目录固定为 `backend/src`
- 前端目录固定为 `frontend/src`
- 根目录统一使用 `.venv`
- 后端分层保持 `api / core / domain / schemas / tests`
- API 层尽量薄，业务逻辑集中在 `domain`
- 数据库连接、初始化和兼容逻辑集中在 `core/state.py`
- 普通 HTTP 请求走 axios，流式聊天保留 fetch + ReadableStream
- 修改目录结构、配置项、接口或数据模型后，必须同步更新 `docx/` 和 `docs/`

## 测试要求

- 新增或修改后端逻辑时，优先补单元测试
- 至少保证后端全量测试通过
- 前端改动至少保证 `npm run build` 通过
- 关键路径包括：
  - 文档解析
  - 分块
  - 向量化
  - PostgreSQL 持久化
  - pgvector 写入
  - 检索
  - 聊天工作流

## 代码风格

- Python 保持清晰、可替换、低耦合
- 优先通过抽象层隔离数据库和向量存储实现
- Vue 使用 Composition API 和 `<script setup lang="ts">`
- 复杂状态和副作用放在 composables 或 store
- 避免把实现细节硬编码到测试里

## 注意事项

### 数据库

- 默认业务主库是 PostgreSQL
- 默认向量持久化路径是 PostgreSQL + pgvector 同库
- 主要 SQL 脚本遵循 `ragent` 风格：
  - `tools/postgres/schema_pg.sql`
  - `tools/postgres/init_data_pg.sql`
- 默认连接：
  - Host: `127.0.0.1`
  - Port: `5433`
  - DB: `retriflow`
  - User: `retriflow`
  - Password: `retriflow`
  - Schema: `public`
- SQLite 仅作为兼容模式和测试隔离用途，不再作为默认正式主库

### 向量存储

- 向量表默认是 `retriflow_chunk_vectors`
- 向量维度必须和当前 embedding 模型一致
- 如果 pgvector 服务不可用，系统会自动回退到本地内存语义检索

### 文档解析

- Tika 开启时优先使用 Tika
- 文本类文件在 Tika 不可用时允许 UTF-8 fallback
- 结构化 block 要尽量保留 `heading`、`paragraph`、`table`、`image_caption`、`page_break` 语义

### 当前未完成项

- rerank 尚未接入
- 更复杂的 LangGraph 编排尚未接入
- 权限、多租户、异步任务尚未接入
