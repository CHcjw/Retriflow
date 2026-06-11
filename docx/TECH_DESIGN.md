# 技术设计文档（TECH_DESIGN）

## 技术栈选择

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Axios
- Pinia

### 后端

- Python 3.12
- FastAPI
- LangChain
- LangGraph
- LangSmith
- Pydantic
- httpx
- psycopg

### 认证

- 本地用户表
- Bearer Token
- 请求级当前用户上下文

### 数据库与存储

- PostgreSQL
  - 业务主库
  - 存储会话、消息、知识库、文档、chunk、structured blocks、ingestion tasks
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

### 后端模块划分

- `backend/src/main.py`
  - 应用工厂入口
- `backend/src/core/config.py`
  - 统一读取模型、数据库、Tika、OCR、LangSmith、MCP、记忆相关配置
- `backend/src/core/state.py`
  - PostgreSQL / SQLite 连接与表初始化
- `backend/src/domain/document_parser.py`
  - Tika 解析
  - MIME / 文本提取
  - 结构化内容提取与标准化清洗
- `backend/src/domain/ingestion.py`
  - 入库工作流
  - 文档标准化、分块、后处理、入库
- `backend/src/domain/vector_store.py`
  - pgvector 持久化与向量检索
- `backend/src/domain/retrieval.py`
  - BM25、向量、RRF、rerank 主链路
- `backend/src/domain/reranker.py`
  - reranker 服务封装
- `backend/src/domain/knowledge_route.py`
  - 首页直聊的知识库路由
- `backend/src/domain/intent_classifier.py`
  - 四类意图识别
  - 规则 + LLM 混合分类
- `backend/src/domain/query_rewrite.py`
  - 查询重写与多意图拆分
- `backend/src/domain/memory.py`
  - 短期 / 中期 / 长期记忆
  - 已支持 TTL、Prompt 注入上限、基于 query 的相关性注入
- `backend/src/domain/mcp/`
  - MCP 工具注册、参数提取、执行编排
- `backend/src/domain/llm.py`
  - 三段式 Prompt 组装
  - 记忆注入
  - LLM 调用与摘要生成
- `backend/src/domain/answer_postprocessor.py`
  - 引用、来源、冲突提示、安全过滤、格式化
- `backend/src/domain/workflow_adapter.py`
  - LangGraph 风格工作流适配

## 数据模型

### 业务表

#### `sessions`

- `id`
- `title`
- `message_count`
- `owner_id`

#### `users`

- `id`
- `username`
- `password_hash`
- `role`
- `created_at`

#### `conversation_messages`

- `id`
- `session_id`
- `role`
- `content`
- `created_at`

#### `conversation_memory_summaries`

- `id`
- `session_id`
- `content`
- `last_message_id`
- `updated_at`
- `expires_at`

用途：

- 保存短期记忆摘要
- 记录摘要已覆盖到哪一条消息
- 支持 TTL 过期清理

#### `conversation_mid_memories`

- `id`
- `session_id`
- `memory_type`
- `content`
- `status`
- `updated_at`
- `expires_at`

用途：

- 保存中期记忆，如阶段目标、约束、已解决事项、待确认事项

#### `conversation_long_memories`

- `id`
- `owner_type`
- `owner_id`
- `memory_type`
- `content`
- `status`
- `updated_at`
- `expires_at`

用途：

- 保存长期记忆，如用户偏好、稳定约束、身份画像、稳定事实

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
- `vector_index_status`
- `vector_chunk_count`
- `vector_indexed_at`
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

### 0. 登录认证

- 参考 `ragent` 的“登录后有当前用户上下文”的思路
- RetriFlow 当前采用轻量 Bearer Token 方案
- 已支持：
  - `/api/v1/auth/register`
  - `/api/v1/auth/login`
  - `/api/v1/auth/me`
- 前端已支持：
  - `/login` 登录/注册切换页
  - `frontend/src/stores/auth.ts` 统一管理登录态
  - `frontend/src/services/api.ts` 自动注入 Bearer Token
  - 401 响应触发前端自动清理登录态并跳转登录页
  - `frontend/src/router/index.ts` 通过 `meta.requiresAuth` 守卫聊天页和后台页
  - `frontend/src/composables/useRetriFlowAdmin.ts` 根据角色切换管理员模式与只读模式
  - `frontend/src/views/AdminView.vue` 对非 `admin` 明确展示只读提示并隐藏管理操作
  - `admin` 可在后台页直接调用文档 reindex，并查看 `vector_index_status / vector_chunk_count / vector_indexed_at`
- 当前受保护接口：
  - `sessions`
  - `chat`
- 当前后台权限细分：
  - `knowledge-bases` 读取接口需要登录
  - `knowledge-bases` 写入、上传、reindex、样例导入需要 `admin`
  - `ingestion/tasks` 与 `ingestion/tasks/{id}/nodes` 需要 `admin`
- 会话创建默认绑定当前登录用户
- 默认调试账号：
  - `admin / admin`

### 1. 首页直聊 + 知识库路由

- 用户先提问，不强制先选知识库
- 先做意图识别，再做知识库路由，再决定检索或工具调用
- 高置信度时走限定知识库召回
- 低置信度时回退到全局检索

### 2. 四类意图识别

- 类型
  - `knowledge_retrieval`
  - `tool_call`
  - `chitchat`
  - `clarification`
- 顺序
  - `memory -> intent -> rewrite -> route/retrieve`
- 实现
  - 规则快速过滤
  - LLM 精分类
- 当前模型选择
  - 默认 `intent_provider=ollama`
  - 通过 `RetriFlowLLMService.extract_json_object(..., capability="intent")` 调用
  - 若本地 Ollama 可用，默认走 `RETRIFLOW_OLLAMA_CHAT_MODEL`
  - 若关闭或不可用，则回退为规则 / fallback

### 3. 查询重写

- 在记忆之后、检索之前执行
- 支持指代消解、上下文补全、口语转正式、多意图拆分
- 输出严格 JSON
- 失败自动回退原始问题

### 4. 混合检索主链路

标准链路：

1. Query Rewrite / 多子查询
2. BM25 Top80
3. 向量 Top80
4. RRF Top50
5. rerank Top10
6. final Top5

当前工作流返回：

- `workflow.retrieval_channels`
- `workflow.retrieval_stage_counts`
- `workflow.rewritten_queries`

### 5. 会话记忆架构

#### 短期记忆

- 采用“摘要 + 最近 N 轮”混合策略
- 摘要表支持 TTL
- 历史消息不直接删除

#### 中期记忆第二版

- 提取类型
  - `goal`
  - `constraint`
  - `resolved_item`
  - `open_item`
- 已支持
  - 独立 TTL
  - 去重
  - 数量裁剪
  - Prompt 注入上限
  - 基于 query 的相关性排序注入
- 仍待增强
  - 冲突合并
  - 状态流转
  - 重要性评分

#### 长期记忆第二版

- 提取类型
  - `preference`
  - `constraint`
  - `profile`
  - `stable_fact`
- 已支持
  - 独立 TTL
  - 去重
  - 数量裁剪
  - Prompt 注入上限
  - 基于 query 的相关性排序注入
- 会优先基于 `sessions.owner_id` 挂到 `user` owner
- 若 session 未绑定 owner，则回退到 `session` owner
- 同一 owner 下新增同类型长期记忆时，会将旧 active 记录置为 inactive
- 仍待增强
  - 冲突合并
  - 生命周期治理

### 6. 文档解析与结构化提取

- 使用 Apache Tika 解析常见文档
- 支持 PDF、DOC、DOCX、Markdown、表格类文档
- 提取标题、正文、表格、图片说明、页码
- 表格保留 header / row / col 关系
- 使用 Pydantic 做关键字段 schema 校验

### 7. 文档重建索引

支持：

- 按新的分块策略重新切 chunk
- 删除旧向量后重写入
- 保留 ingestion task 审计记录
- 刷新 `vector_index_status / vector_chunk_count / vector_indexed_at`

### 8. MCP 设计

- 采用程序控制的 MCP 调用模式
- 支持内置工具与远程 MCP Server
- 支持单轮命中多个工具
- 支持串行 / 并行执行
- 支持 `fail_fast`

### 9. 答案生成

- 三段式 Prompt
  - System Prompt
  - Retrieved Context
  - User Query
- 低 temperature 抑制幻觉
- 答案后处理补齐引用与来源

## 当前实现补充

- 当前默认 reranker 模型为 `Qwen/Qwen3-Reranker-8B`
- 当前默认意图识别模型入口走 Ollama provider
- 记忆服务相关测试已覆盖
  - TTL
  - Prompt 注入
  - query 相关性排序
