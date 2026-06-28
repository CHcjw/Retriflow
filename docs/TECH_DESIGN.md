# RetriFlow 技术设计

## 技术栈

- 前端：Vue 3 + TypeScript + Vite + Vue Router + Pinia。
- 样式：项目内 CSS，后台组件保持统一表格、表单、下拉框和响应式布局。
- 后端：Python 3.12 + FastAPI + Pydantic。
- RAG 编排：LangChain、LangGraph、OpenAI-compatible LLM。
- 数据库：PostgreSQL，测试兼容 SQLite。
- 向量存储：pgvector，测试和降级场景支持 memory vector store。
- 文档解析：Apache Tika，OCR 服务可选。
- 队列依赖：Redis，通过 `docker-compose.services.yml` 提供本地服务。
- 对象存储：本地文件系统或 RustFS/S3，通过 `infra/storage` 抽象。
- 外部模型：支持 Bailian、SiliconFlow、LM Studio、Ollama 等 OpenAI-compatible provider。

## 项目结构

```text
RetriFlow/
  backend/
    src/
      api/              # FastAPI 路由与鉴权依赖
      core/             # 配置、数据库连接、初始化、补表和 seed
      infra/            # LLM、embedding、vector store、document parser、storage
      modules/          # auth、chat、knowledge、ingestion、mcp、memory、rag、admin
      schemas/          # Pydantic 入参、出参和结构化模型
      tests/            # 后端回归测试
  frontend/
    src/
      components/       # chat 与后台功能组件
      composables/      # 可复用状态与业务编排
      router/           # 前端路由
      services/         # HTTP client、API 类型和请求函数
      stores/           # Pinia 状态
      views/            # 页面
  docs/                 # PRD、技术设计、开发指引
  resource/database/    # PostgreSQL schema、seed、清库脚本和说明
  resource/sample_data/ # 本项目样例知识文档
  tools/                # Tika、OCR 等辅助服务
```

`domain/` 已移除。新业务代码必须进入 `modules/` 或 `infra/`，测试也应 patch 真实模块路径。

## 数据模型

### 用户与会话

- `users`：用户、密码哈希、角色和头像。
- `sessions`：会话元数据、标题、owner 和消息数量。
- `conversation_messages`：用户和助手消息，包含真实 `duration_ms`。
- `message_feedback`：助手消息反馈，按 message upsert `vote/reason/comment`。
- `conversation_memory_summaries`：短期摘要记忆。
- `conversation_mid_memories`：中期记忆。
- `conversation_long_memories`：长期记忆。

### 知识库与文档

- `knowledge_bases`：知识库基础信息、embedding model、collection name、owner、创建和更新时间。
- `knowledge_base_route_profiles`：知识库路由画像、示例问题和关键词。
- `knowledge_documents`：文档元数据、上传源文件 URI、源文件 hash、解析文本、索引状态和分块配置。
- `knowledge_chunks`：chunk 内容、策略、文档类型、元数据和启停状态。
- `knowledge_document_blocks`：结构化段落、标题、表格、图片说明和页码。
- `knowledge_document_table_cells`：表格 row、col、header 关系。
- `retriflow_chunk_vectors`：pgvector 向量记录，包含 collection 与 embedding 信息。

### 入库与数据通道

- `ingestion_pipelines`：后台配置的数据通道，保存节点 JSON。
- `ingestion_tasks`：上传、修改、重建索引产生的入库任务。
- `ingestion_task_nodes`：节点执行日志，包含 `node_id`、`node_type`、`node_order`、`status`、`success`、`message`、`error_message`、`duration_ms` 和 `output_json`。

### 可观测与治理

- `rag_trace_nodes`：RAG 节点级 trace，包含父子节点、类型、状态、输入输出摘要、错误、metadata 和耗时。
- `model_health`：provider/model/capability 健康快照，支持重启恢复。
- `admin_intent_nodes`：后台意图树节点。
- `admin_keyword_mappings`：关键词映射配置。
- `admin_sample_questions`：聊天欢迎页示例问题与推荐问法配置。

## 聊天 RAG 流程

1. 加载短期、中期、长期会话记忆。
2. 执行 `query-rewrite-and-split` 查询改写和多问题拆分。
3. 执行 `intent-resolve` 意图识别与候选路径计算。
4. 根据意图树、关键词映射、知识库画像和智能联网开关决策知识库检索或 MCP 工具调用。
5. 通过 `retrieval-engine` 执行检索编排。
6. 通过 `multi-channel-retrieval` 执行 BM25、向量召回和后处理链。
7. 执行 RRF、rerank 和 final topK。
8. 通过 `RAGPromptService` 按场景模板构建三段式 Prompt。
9. 调用 LLM 生成答案。
10. 执行答案后处理、消息反馈入口、消息持久化、记忆更新和 trace 收尾。

## SSE 流式 Trace 流程

1. `RetriFlowStreamingService` 在真实 SSE 生命周期外层开启 `chat.stream`。
2. `prepare_stream()` 只准备 workflow，不关闭根 trace。
3. 模型 delta 迭代由 detached `generation.answer` 包装。
4. 首个 delta 到达前端时记录 `user-first-packet` / `USER_TTFT`。
5. 正常结束标记 success，异常标记 error，客户端提前断开标记 cancelled。
6. 如果 SSE 在 `done` 前退出，会主动 close delta iterator，避免 `generation.answer` 长期 running。

## 文档入库流程

1. 上传或修改文档时选择处理模式、分块策略和数据通道。
2. 上传源文件先计算 SHA-256，按同一知识库内 `source_hash` 判重。
3. 源文件通过 `infra/storage` 写入可替换文件存储，本地返回 `local://` URI，RustFS/S3 返回 `s3://bucket/key` URI。
4. 对象 key 使用内容 hash 前缀加原始中文文件名。
5. 从存储重新打开源文件后交给 Tika 检测 MIME 并解析正文、metadata 和结构化块。
6. OCR 和图片说明服务可用时补充图片文本，不可用时降级。
7. 标准化清洗文本、表格和空值。
8. 根据 pipeline 节点配置生成 `RetriFlowIngestionPipeline`。
9. 根据策略生成 source documents、chunk documents 和 chunk metadata。
10. 写入 `knowledge_documents.source_uri/source_hash`、`knowledge_chunks` 和 pgvector。
11. 写入 `ingestion_tasks` 和 `ingestion_task_nodes`，保留节点输出。

## 队列限流流程

1. 开启 `RETRIFLOW_CHAT_QUEUE_ENABLED=true` 后，流式聊天先获取 limiter。
2. SSE 先发送 `event: queue`，payload 来自同一 limiter 实例的 `snapshot()`。
3. memory backend 使用进程内 FIFO、condition notify 和 cancel cleanup。
4. Redis backend 使用 ZSET 排队、entry TTL、Lua claim、active permit 和 Pub/Sub 唤醒。
5. acquire 成功后执行真实聊天，结束后 release permit。
6. acquire 超时后持久化 reject 消息，并发送 `reject`、`final(status=rejected)`、`done`。

## 关键设计点

1. Trace 使用 `contextvars` 保存 trace id、task id、session id 和节点栈，root span 退出时必须 reset。
2. 普通 `span()` 在没有 active trace 时必须 no-op，不能产生空 session 子节点。
3. 流式 `generation.answer` 必须 close-aware，完成、异常、fallback 或取消都要关闭。
4. 检索通过 SearchChannel 和 SearchResultPostProcessor 扩展；单个通道或后处理器异常时记录 error metrics 并继续后续链路。
5. 意图树 Redis 缓存只缓存真实后台节点，admin create/update/delete 后必须清理。
6. 路由按分数排序保留阈值以上的多个 KB 或 MCP 候选，最多 3 个目标，并保留 parent -> child fallback 路径。
7. MCP 节点读取 `mcp_tool_id` 并交给 MCP 执行器 forced tools，同时读取 `param_prompt_template` 传给参数提取器。
8. 非流式 LLM 调用通过 `_post_json_with_fallback()` 按候选 provider 顺序调用；单个 provider 失败后记录模型健康失败并继续尝试下一个可用候选。
9. Ingestion pipeline 先校验 `nextNodeId` 是否存在和是否成环，再从第一个起点节点沿链执行，断开的节点不会被记为已执行。
10. Ingestion 条件执行支持 boolean、JSON `all/any/not/field`、嵌套字段路径和基础比较。
11. Ingestion 输出抽取保留 parser/fetcher 的文本与来源，enhancer 的增强文本、关键词和问题，chunker/enricher 的 chunk count 与 chunks，indexer 的 settings 与 chunk count。
12. 数据通道配置无效时 API 返回 `400 Invalid ingestion pipeline`，不让底层校验异常冒成 500。
13. Prompt 模板服务使用 `PromptScene` 和 `PromptBuildPlan` 组织 rewrite、intent、guidance、memory、context、answer 场景。
14. 文件存储使用 `StoredFile`、`LocalFileStorageService` 和 `S3FileStorageService` 抽象，业务只依赖 `upload_bytes/open_stream/delete_by_uri/delete_bucket`。
15. 前端 HTTP 核心集中在 `services/httpClient.ts`，业务入口通过 `adminApi/authApi/chatApi/knowledgeApi/metaApi/pipelineApi` 导出。

## 配置与外部服务

- `.env` / `.env.example` 保存数据库、模型、向量库、Redis、Tika、OCR、对象存储和队列配置。
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
  - `init_data_pg.sql`：默认管理员、默认 pipeline、关键词映射和欢迎页示例问题，不初始化知识库。
  - `init_intent_nodes_pg.sql`：意图节点初始化，可在前端建好知识库后按需执行。
  - `drop_all_tables_pg.sql`：用于 HeidiSQL 等客户端清理当前 schema 内业务表。
- 默认管理员：`admin / admin`。

## 验证命令

后端 targeted 回归：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_ingestion_pipeline.py backend/src/tests/retriflow_backend/test_chat_api.py backend/src/tests/retriflow_backend/test_session_api.py -q
```

前端构建：

```powershell
cd frontend
npm run build
```

Markdown 回归：

```powershell
cd frontend
npm run test:markdown
```
