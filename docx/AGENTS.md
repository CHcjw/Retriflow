# AGENTS 指令文件

## 项目概述

RetriFlow 是一个 `Python + FastAPI + LangChain + LangGraph + LangSmith + Vue 3` 的 Agentic RAG 项目，目标是复现并优化 `ragent` 的核心能力，包括文档解析、结构化入库、分块、向量化、混合检索、重排序、答案生成、MCP 工具调用、多轮记忆、链路追踪和后台运营管理。

当前后端已经采用 `modules + infra` 主架构。新实现应进入 `modules/` 或 `infra/`，不要再新建 `domain/` 兼容层。

## 开发规范

- 根目录统一使用 `.venv`，不要在 `backend/` 下再新建独立虚拟环境。
- 后端代码固定在 `backend/src`。
- 前端代码固定在 `frontend/src`。
- 后端新业务代码优先写入 `modules/`。
- 外部服务、模型、向量库、文档解析等基础设施适配优先写入 `infra/`。
- `domain/` 已移除；不要继续添加 domain facade、re-export 或测试桥接。
- API 层保持薄，只处理路由、鉴权依赖、参数和 service 调用。
- 配置读取集中在 `backend/src/core/config.py`。
- 数据库连接、初始化、自动补表和 seed 集中在 `backend/src/core/state.py`。
- 修改接口、数据库结构、RAG 链路、后台功能或配置后，必须同步更新 `docx/` 文档。
- 手工编辑文件优先使用补丁方式，避免覆盖用户已有改动。
- 不要回滚用户未明确要求回滚的改动。
- 常规 HTTP 请求使用 Axios；流式聊天保留 SSE / `fetch + ReadableStream`。
- Vue 使用 Composition API 和 `<script setup lang="ts">`。

## 架构边界

### modules

- `modules/auth`：认证。
- `modules/session`：会话。
- `modules/chat`：聊天和流式输出。
- `modules/knowledge`：知识库、文档、切块、路由画像。
- `modules/ingestion`：入库流水线和分块。
- `modules/memory`：短期、中期、长期记忆。
- `modules/mcp`：MCP 工具调用。
- `modules/rag`：意图识别、查询重写、检索、rerank、答案后处理、workflow。
- `modules/admin`：后台管理。

### infra

- `infra/llm`：模型调用。
- `infra/embeddings`：向量模型。
- `infra/vector_store`：pgvector / 内存向量存储。
- `infra/document_parser`：Tika、OCR、结构化提取、标准化。

### domain

`domain/` 已移除。旧代码如需迁移，应改为导入 `modules/` 或 `infra/` 下的真实实现。

测试不应 patch `domain.*` 路径；新增测试必须 patch `modules/` 或 `infra/` 的真实实现路径。
## 测试要求

- 后端行为变化必须补充或更新 pytest。
- 前端改动至少保证 `npm run build` 通过。
- 涉及登录状态时，检查：
  - `frontend/src/stores/auth.ts`
  - `frontend/src/services/api.ts`
  - `frontend/src/router/index.ts`
- 涉及后台接口时，必须区分“登录可读”和“仅 admin 可写/可管理”。
- 涉及数据库结构时，必须同步：
  - `backend/src/core/state.py`
  - `tools/postgres/schema_pg.sql`
  - 相关测试
- 涉及 seed 数据时，必须同步：
  - `tools/postgres/init_data_pg.sql`
  - 相关测试
- 测试中如使用 SQLite，应显式设置：
  - `RETRIFLOW_DATABASE_BACKEND=sqlite`
  - `RETRIFLOW_DB_PATH=<temp db>`
  - `RETRIFLOW_DATABASE_DSN=`
  - `RETRIFLOW_PGVECTOR_DSN=`
  - `RETRIFLOW_VECTOR_STORE_TYPE=memory`
- 声称完成前必须说明实际运行过哪些测试或构建。

## 推荐回归命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_chat_api.py backend/src/tests/retriflow_backend/test_knowledge_document_api.py backend/src/tests/retriflow_backend/test_retrieval_engine.py -q
```

完整迁移相关回归：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_tika_client.py backend/src/tests/retriflow_backend/test_document_parser.py backend/src/tests/retriflow_backend/test_document_structure.py backend/src/tests/retriflow_backend/test_document_normalizer.py backend/src/tests/retriflow_backend/test_document_caption_enrichment.py backend/src/tests/retriflow_backend/test_ingestion_pipeline.py backend/src/tests/retriflow_backend/test_ingestion_api.py backend/src/tests/retriflow_backend/test_knowledge_api.py backend/src/tests/retriflow_backend/test_knowledge_document_api.py backend/src/tests/retriflow_backend/test_vector_store.py backend/src/tests/retriflow_backend/test_retrieval_engine.py backend/src/tests/retriflow_backend/test_reranker.py backend/src/tests/retriflow_backend/test_chat_api.py backend/src/tests/retriflow_backend/test_chat_mcp_api.py backend/src/tests/retriflow_backend/test_memory_service.py backend/src/tests/retriflow_backend/test_model_routing.py -q
```

前端构建：

```powershell
cd frontend
cmd /c npm.cmd run build
```

## 代码风格

- Python 保持清晰、低耦合、可测试。
- Pydantic schema 用于 API 入参出参和关键结构化字段校验。
- 数据库字段新增时要考虑老库兼容，使用自动补列或幂等 SQL。
- 后端服务类不要在模块导入时创建全局业务单例。
- 核心业务依赖优先从 `modules/` 或 `infra/` 导入。
- Vue 组件保持数据流清晰，复杂业务逻辑放入 composable。
- 后台页面必须角色感知：普通用户隐藏管理操作，非 admin 给出明确提示。
- 聊天回答必须以用户可读 Markdown 样式渲染，不应裸露 `##`、`**` 等 Markdown 标记。
- 链路追踪、Dashboard 和后台表格必须基于真实后端数据，不使用无意义死数据。

## RAG 链路规则

标准执行顺序：

1. 加载会话记忆。
2. 意图识别。
3. 查询重写。
4. 知识库路由 / 工具路由。
5. BM25 Top80。
6. 向量 Top80。
7. RRF Top50。
8. rerank Top10。
9. final Top5。
10. 构建三段式 Prompt。
11. LLM 生成答案。
12. 答案后处理。
13. 持久化消息和链路耗时。
14. 更新短期/中期/长期记忆。

调试时优先关注：

- `workflow.rewritten_queries`
- `workflow.rewrite_query_count`
- `workflow.retrieval_stage_counts`
- `workflow.retrieval_channels`
- `vector_index_status`
- `vector_chunk_count`
- `vector_indexed_at`
- `conversation_messages.duration_ms`

## 文档入库规则

- 文档解析优先使用 Apache Tika。
- Tika 检测真实 MIME 类型，不应只依赖文件后缀。
- 支持 PDF、DOC、DOCX、Markdown、文本和表格类文档。
- 必须尽量保留标题层级、正文段落、表格结构、图片说明和页码。
- 表格不能只转纯文本，必须保留 row / col / header 关系。
- 标准化清洗后使用 Pydantic 做关键字段 schema 校验。
- 文档创建和 reindex 都必须刷新：
  - `vector_index_status`
  - `vector_chunk_count`
  - `vector_indexed_at`
- reindex 必须先删除该文档旧向量，再写入新向量。
- reindex 必须保留历史 ingestion task 审计记录。

## MCP 规则

- 当前 MCP 是程序控制调用，不是模型原生 function calling。
- 支持内置工具和远程 MCP Server。
- 支持单轮多个工具。
- 执行模式支持 `sequential` 和 `parallel`。
- 单工具失败不应影响其他工具，除非 `fail_fast=true`。

## 答案生成规则

- 使用三段式 Prompt：
  - System Prompt
  - Retrieved Context
  - User Query
- 默认低 temperature，例如 `0.1`，用于降低幻觉。
- 如果参考资料不足，必须给出兜底回复，不能编造。
- 答案必须引用参考资料编号，例如 `[1]`。
- 最终答案必须经过后处理：
  - 引用补齐
  - 来源补充
  - 冲突提示
  - 基础安全过滤
  - Markdown 格式整理

## 注意事项

- 不要要求用户先选择知识库再聊天；用户体验必须是首页直接提问。
- 不要把后台做成纯前端假数据，能新增/修改/删除的地方优先接真实后端。
- 不要让删除会话只在前端消失，必须删除数据库里的会话和关联消息/记忆。
- 不要在前端展示内部路由、冗长路径或调试字段作为“来源”。
- 不要在回答完成后把 Markdown 渲染退回纯文本。
- 不要用时间戳差假装链路耗时；新链路必须记录真实耗时。
- 外部服务不可用时优先降级并给出明确错误信息，不要静默失败或长时间卡死。
