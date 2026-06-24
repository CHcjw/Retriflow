# RetriFlow 技术设计

## 技术栈

- 前端：Vue 3 + TypeScript + Vite + Vue Router + Pinia。
- 样式：项目内 CSS，后台组件保持统一表格、表单、下拉框和响应式布局。
- 后端：Python 3.12 + FastAPI + Pydantic。
- RAG：LangChain + LangGraph + OpenAI-compatible LLM。
- 数据库：PostgreSQL，测试兼容 SQLite。
- 向量存储：pgvector，测试和降级场景支持 memory vector store。
- 文档解析：Apache Tika，OCR 服务可选。
- 队列依赖：Redis，使用 `docker-compose.services.yml` 提供本地服务。
- 对象存储：本地文件系统或 RustFS/S3，使用同一 `infra/storage` 抽象。
- 外部模型：支持 OpenAI-compatible provider、Ollama embedding 和 reranker。

## 项目结构

```text
RetriFlow/
  backend/
    src/
      api/              # FastAPI 路由与鉴权依赖
      core/             # 配置、数据库连接、初始化、补表和 seed
      infra/            # LLM、embedding、vector store、document parser
      modules/          # auth、chat、knowledge、ingestion、mcp、memory、rag、admin
      schemas/          # Pydantic 入参、出参和结构化模型
      tests/            # pytest 回归测试
  frontend/
    src/
      components/       # 通用组件；后台组件按 chunks/common/dashboard/documents/intent/keyword/knowledge/pipeline/samples/settings/trace/users 拆分
      composables/      # 复用状态与业务编排；后台 composable 按 common/documents/intent/keyword/knowledge/pipeline/users 拆分
      router/           # 前端路由
      services/         # HTTP client、API 类型和按 auth/chat/knowledge/admin/pipeline/meta 拆分的请求函数
      stores/           # Pinia 状态
      views/            # 页面
  docs/                 # PRD、技术设计、AI 开发指令
  resource/database/    # PostgreSQL schema、seed、清库脚本和说明
  docker-compose.services.yml
```

`domain/` 已移除。新业务代码必须进入 `modules/` 或 `infra/`，测试也应 patch 真实模块路径。

## 数据模型

### 用户与会话

- `users`：用户、密码哈希、角色。
- `sessions`：会话元数据、标题、owner、消息数量。
- `conversation_messages`：用户和助手消息，包含真实 `duration_ms`。
- `message_feedback`：助手消息反馈，按 message upsert `vote/reason/comment`，后台可分页查看。
- `conversation_memory_summaries`：短期摘要记忆。
- `conversation_mid_memories`：中期记忆。
- `conversation_long_memories`：长期记忆。

### 知识库与文档

- `knowledge_bases`：知识库基础信息、embedding model、collection name。
- `knowledge_base_route_profiles`：知识库路由画像、示例问题和关键词。
- `knowledge_documents`：文档元数据、上传源文件 `source_uri`、源文件 `source_hash`、解析文本、索引状态、分块配置。
- `knowledge_chunks`：chunk 内容、策略、文档类型、元数据和启停状态。
- `knowledge_document_blocks`：结构化段落、标题、表格、图片说明和页码。
- `knowledge_document_table_cells`：表格 row、col、header 关系。
- `retriflow_chunk_vectors`：pgvector 向量记录，包含 collection 与 embedding 信息。

### 入库与流水线

- `ingestion_pipelines`：后台配置的数据通道，保存节点 JSON。
- `ingestion_tasks`：上传、修改、重建索引产生的入库任务。
- `ingestion_task_nodes`：节点执行日志，对齐 ragent `NodeLog` / `IngestionTaskNodeDO`，包含 `node_id`、`node_type`、`node_order`、`status`、`success`、`message`、`error_message`、`duration_ms` 和 `output_json`。

### 可观测与治理

- `rag_trace_nodes`：RAG 节点级 trace，包含父子节点、类型、状态、输入输出摘要、错误、metadata 和耗时；后台列表通过最新 root 节点支持 trace、session、task、用户、状态和时间筛选。
- `model_health`：provider/model/capability 健康快照，支持重启恢复。
- `admin_intent_nodes`：后台意图树节点。
- `admin_keyword_mappings`：关键词映射配置。
- `admin_sample_questions`：聊天欢迎页示例问题与推荐问法配置，不绑定具体知识库。

## 核心流程

### 聊天 RAG 流程

1. 加载短期、中期、长期会话记忆。
2. 执行 `intent-resolve` 意图识别。
3. 执行 `query-rewrite-and-split` 查询改写和多问题拆分。
4. 进行知识库路由或 MCP 工具路由；当多个真实知识库候选分数接近且问题未明确指向候选时，返回澄清引导，不直接扩展复杂工作流。
5. 通过 `retrieval-engine` 执行检索。
6. 通过 `multi-channel-retrieval` 执行 BM25、向量召回和后处理链。
7. 执行 RRF、rerank 和 final topK。
8. 通过 `RAGPromptService` 按场景模板构建三段式 Prompt。
9. 调用 LLM 生成答案。
10. 执行答案后处理、消息反馈入口、消息持久化、记忆更新和 trace 收尾。

### SSE 流式 Trace 流程

1. `RetriFlowStreamingService` 在真实 SSE 生命周期外层开启 `chat.stream`。
2. `prepare_stream()` 只准备 workflow，不关闭根 trace。
3. 模型 delta 迭代由 detached `generation.answer` 包装。
4. 首个 delta 到达前端时记录 `user-first-packet` / `USER_TTFT`。
5. 正常结束标记 success，异常标记 error，客户端提前断开标记 cancelled。
6. 如果 SSE 在 `done` 前退出，会主动 close delta iterator，避免 `generation.answer` 长期 running。

### 文档入库流程

1. 上传或修改文档时选择分块策略和数据通道。
2. 上传源文件先计算 SHA-256，按同一知识库内 `source_hash` 判重，重复时返回 409 业务错误。
3. 上传源文件通过 `infra/storage` 写入可替换文件存储，本地返回 `local://` URI，RustFS/S3 返回 `s3://bucket/key` URI。
4. 对象 key 使用内容 hash 前缀加保留中文的原始文件名，避免随机乱码名并保持相同内容稳定命名。
5. 从存储重新打开源文件后交给 Tika 检测 MIME 并解析正文、metadata 和结构化块。
6. OCR 和图片说明服务可用时补充图片文本，不可用时降级。
7. 标准化清洗文本、表格和空值。
8. 根据 pipeline 节点配置生成 `RetriFlowIngestionPipeline`。
9. 根据策略生成 source documents、chunk documents 和 chunk metadata。
10. 写入 `knowledge_documents.source_uri/source_hash`、`knowledge_chunks` 和 pgvector。
11. 写入 `ingestion_tasks` 和 `ingestion_task_nodes`，保留节点输出。

### 队列限流流程

1. 开启 `RETRIFLOW_CHAT_QUEUE_ENABLED=true` 后，流式聊天先获取 limiter。
2. SSE 先发送 `event: queue`，payload 来自同一个 limiter 实例的 `snapshot()`。
3. memory backend 使用进程内 FIFO、condition notify 和 cancel cleanup。
4. Redis backend 使用 ZSET 排队、entry TTL、Lua claim、active permit 和 Pub/Sub 唤醒。
5. acquire 成功后执行真实聊天，结束后 release permit。
6. acquire 超时后持久化 reject 消息，并发送 `reject`、`final(status=rejected)`、`done`。

## 关键技术点

1. Trace 使用 `contextvars` 保存 trace id、task id、session id 和节点栈；root span 退出时必须 reset，避免上下文泄漏。
2. 普通 `span()` 在没有 active trace 时必须 no-op，不能产生空 session 的孤儿节点。
3. 流式 `generation.answer` 必须 close-aware，完成、异常、fallback 或取消都要关闭。
4. 检索通过 SearchChannel 和 SearchResultPostProcessor 扩展，当前真实能力为 BM25、向量、RRF、rerank 和 final limit；workflow metadata 暴露 `retrieval_stage_counts` 与 `retrieval_stage_metrics`，用于查看通道耗时、query count、topK 和后处理器输入输出数量；单个通道或后处理器异常时记录 error metrics 并继续后续链路。
5. 意图树 Redis 缓存只缓存真实后台节点，admin create/update/delete 后必须清理；路由时按分数排序保留阈值以上的多个 KB 候选，最多 3 个目标，保留 parent -> child fallback 路径；workflow 会对 rewrite 后的多个 query 分别路由并合并 KB 范围。
6. MCP trace 节点命名为 `mcp.tool.<tool_id>`，metadata 保留 tool、server、transport 和 schema version；远程 server 注册按 ragent 自动配置语义逐个初始化，失败 server 记录 unhealthy/error/tool_count=0 并跳过，不影响内置工具和其他远程 server。
7. 非流式 LLM 调用通过 `_post_json_with_fallback()` 对齐 ragent `ModelRoutingExecutor`，按候选 provider 顺序调用；单个 provider 失败由 `_post_json()` 记录模型健康失败，再继续尝试下一个可用候选。
8. 后台 `AdminView` 继续承担路由级编排，业务面板已按功能下沉到 `components/admin/*`，表单状态已按功能下沉到 `composables/admin/*`；公共弹窗、分页、通知和 toast 统一放在 `components/admin/common`，子组件必须自带局部控件样式或使用明确的全局后台样式。
9. Ingestion pipeline 对齐 ragent 链式执行语义：先校验 `nextNodeId` 是否存在和是否成环，再从第一个起点节点沿链执行，断开的节点不会被记为已执行。
10. Ingestion 条件执行对齐 ragent `ConditionEvaluator`，支持 boolean、JSON `all/any/not/field`、嵌套字段路径和基础比较。
11. Ingestion 输出抽取对齐 ragent `NodeOutputExtractor`，parser/fetcher 暴露文本与来源，enhancer 暴露增强文本、关键词和问题，chunker/enricher 暴露 chunk count 和 chunks，indexer 暴露 settings 和 chunk count。
12. 数据通道执行时如果 pipeline 配置无效，API 返回 `400 Invalid ingestion pipeline`，不让底层校验异常冒成 500。
13. Prompt 模板服务使用 `PromptScene` 和 `PromptBuildPlan` 组织 rewrite、intent、guidance、answer 场景，LLM answer 构建不再散落在调用层硬编码。
14. 文件存储使用 `StoredFile`、`LocalFileStorageService` 和 `S3FileStorageService` 抽象，业务只依赖 `upload_bytes/open_stream/delete_by_uri/delete_bucket`；RustFS/S3 删除 bucket 前会先列举并清空对象。
15. 前端 HTTP 核心集中在 `services/httpClient.ts`，负责 Axios 实例、Bearer Token、401 事件、通用 `request` 和 `requestBlob`；`api.ts` 保留类型和 endpoint 实现，`adminApi/authApi/chatApi/knowledgeApi/metaApi/pipelineApi` 作为领域化导出入口。

## 配置与外部服务

- `.env` / `.env.example` 保存数据库、模型、向量库、Redis、Tika、OCR 和队列配置。
- 文件存储配置：
  - `RETRIFLOW_STORAGE_BACKEND=local`
  - `RETRIFLOW_STORAGE_LOCAL_DIR=backend/data/uploads`
- RustFS/S3 配置：
  - `RETRIFLOW_STORAGE_BACKEND=rustfs`
  - `RETRIFLOW_S3_ENDPOINT`
  - `RETRIFLOW_S3_ACCESS_KEY_ID`
  - `RETRIFLOW_S3_SECRET_ACCESS_KEY`
- PostgreSQL 脚本位于 `resource/database/`：
  - `schema_pg.sql`：建表、索引、扩展和兼容字段。
  - `init_data_pg.sql`：默认管理员、默认 pipeline、意图节点、关键词映射和欢迎页示例问题，不初始化知识库。
  - `drop_all_tables_pg.sql`：用于 HeidiSQL 等客户端清理当前 schema 内业务表。
- 默认管理员：`admin / admin`。

## 验证命令

后端常用回归：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_ingestion_pipeline.py backend/src/tests/retriflow_backend/test_ingestion_api.py backend/src/tests/retriflow_backend/test_chat_api.py backend/src/tests/retriflow_backend/test_chat_rate_limit.py -q
```

前端构建：

```powershell
cd frontend
cmd /c npm.cmd run build
```

涉及后台 UI 时还需要用浏览器自动化检查桌面和窄屏布局。

## 剩余技术差距

- Redis 队列已支持取消清理、快照和拒绝持久化，但缺更细队列位置遥测。
- Ingestion 已有节点结果、条件和输出，但还不是 ragent 那样完整的节点执行引擎。
- 意图树已有 Redis 缓存、基础 fallback、多 KB 候选保留、多 query 路由合并和最小歧义引导，但缺 ragent 完整候选置信度传播和节点级检索参数。
- 检索已抽象 channel/postprocessor，并暴露 stage metrics；缓存、版本过滤和更细治理仍需真实后端支撑。
- MCP 已有工具 trace、schema version 和远程 server 注册健康状态，但缺原生 function calling 与后台治理展示。
- 模型健康已有后端能力、独立后台面板、手动 probe 和非流式当次请求 fallback，但缺定时探测、启动预热和流式首包探针 fallback。
- 后台已拆出 Dashboard、Trace、模型健康、知识库、文档、分块、意图、关键词、数据通道、示例问题、用户和设置面板；后续重点是继续压缩 `AdminView` 的编排代码、补浏览器自动化 UI 回归，并把更多纯状态/表单逻辑下沉到 feature composable。
