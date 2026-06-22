# RetriFlow AI 开发指令

## 项目概述

RetriFlow 是一个对齐 ragent 的企业知识问答系统，后端使用 Python + FastAPI，前端使用 Vue 3 + TypeScript。项目核心是文档解析、结构化入库、分块、向量化、混合检索、答案生成、MCP 工具调用、多轮记忆、链路 Trace、队列限流和后台运营管理。

开发时必须先阅读 RetriFlow 当前实现，再对照 ragent 源码。不能为了“看起来对齐”而新增没有真实逻辑支撑的空功能。

## 开发规范

- 后端代码放在 `backend/src`。
- 前端代码放在 `frontend/src`。
- 新业务代码优先进入 `modules/`。
- LLM、embedding、vector store、document parser 等基础设施进入 `infra/`。
- `domain/` 已移除，不要恢复 domain facade 或 re-export。
- API 层保持薄，只处理路由、鉴权、参数和 service 调用。
- 配置集中在 `backend/src/core/config.py`。
- 数据库连接、初始化、自动补表和 seed 集中在 `backend/src/core/state.py`。
- 修改接口、数据库、RAG 链路、后台功能或配置后，必须同步更新 `docx/` 对应主题。
- 文档更新不要写日期流水账，要把新状态融入 PRD、技术设计或开发指令的对应章节。

## 代码风格

- Python 保持清晰、低耦合、可测试。
- Pydantic schema 用于 API 入参、出参和关键结构化字段校验。
- 数据库新增字段时要考虑旧库兼容，使用自动补列或幂等 SQL。
- 后端服务类不要在模块导入时创建全局业务单例。
- Vue 使用 Composition API 和 `<script setup lang="ts">`。
- 复杂前端业务逻辑优先放入 composable。
- 常规 HTTP 请求使用 Axios；流式聊天保留 SSE / `fetch + ReadableStream`。
- 后台页面必须基于真实后端数据，不使用无意义假数据。

## 测试要求

- 后端行为变化至少补充或更新 targeted pytest。
- 前端 UI 或 API 类型变化至少运行 `cmd /c npm.cmd run build`。
- 涉及数据库结构时同步检查：
  - `backend/src/core/state.py`
  - `tools/postgres/schema_pg.sql`
  - 相关测试
- 涉及 seed 数据时同步检查：
  - `tools/postgres/init_data_pg.sql`
  - 相关测试
- 测试使用 SQLite 时显式设置：
  - `RETRIFLOW_DATABASE_BACKEND=sqlite`
  - `RETRIFLOW_DB_PATH=<temp db>`
  - `RETRIFLOW_DATABASE_DSN=`
  - `RETRIFLOW_PGVECTOR_DSN=`
  - `RETRIFLOW_VECTOR_STORE_TYPE=memory`
- 声称完成前必须说明实际运行过哪些测试或构建。

## ragent 对齐规则

- 每个优化都要先看 ragent 对应源码，不要凭想象扩展。
- ragent 没有的能力不要伪造；RetriFlow 没有真实后端支撑的能力不要只做前端壳。
- `guidance-detect` 属于 ragent 意图树候选歧义检测，当前 RetriFlow 简单澄清意图不等价，不要添加假节点。
- `conversation-title-gen` 属于 ragent LLM 标题生成，RetriFlow 当前没有真实标题生成能力，不要添加假 trace。
- ragent 当前 rate-limit 配置只有 global enabled/max-concurrent/max-wait/lease/poll；不要凭空新增 user-level 并发限制。
- ES 只有在 ragent 存在真实实现或 RetriFlow 引入真实 Elasticsearch 后端时再做，不要加空服务。

## 八大对齐事项

1. 流式 Trace
   - 保持 `chat.stream` 生命周期在 `RetriFlowStreamingService`。
   - `generation.answer` 必须 detached 且 close-aware。
   - 断流时将运行中节点标记为 `cancelled`。
   - 不要把缺失的 ragent 行为用假节点补齐。

2. Redis 队列
   - 队列工作必须对齐 ragent `FairDistributedRateLimiter` 和 `ChatQueueLimiter`。
   - SSE 队列启用时先发 `event: queue`，payload 使用 limiter `snapshot()`。
   - memory 和 Redis 等待取消都要清理排队项。
   - 超时拒绝要持久化用户问题和助手忙碌回复。
   - 后续只补真实队列状态和队列位置遥测。

3. Ingestion runtime
   - 改动必须对照 ragent `PipelineDefinition`、`NodeConfig`、`IngestionContext`、`NodeLog`、`ConditionEvaluator`、`NodeOutputExtractor`。
   - 当前节点持久化契约是 `node_id`、`node_type`、`node_order`、`status`、`success`、`message`、`error_message`、`duration_ms`、`output`。
   - pipeline 执行必须保持 ragent 链式语义：校验缺失 next 和环，从第一个起点节点沿 `next_node_id` 执行，不执行断开的孤立节点。
   - 数据通道上传或重建索引遇到无效 pipeline 时，应返回清晰的 400 业务错误，不要让校验异常冒成 500。
   - 不要新增 retry/count/input 字段，除非 ragent 源码或产品需求明确。
   - 新节点输出遵循 ragent 输出抽取：parser/fetcher 输出来源和文本，enhancer 输出增强文本、关键词和问题，chunker/enricher 输出 chunk count 与 chunks，indexer 输出 settings 与 chunk count。

4. 意图树 resolver
   - 保持 Redis intent tree cache 的 get/save/clear/exists 语义。
   - admin intent node create/update/delete 后必须清缓存。
   - 父节点命中但没有绑定知识库时，可以 fallback 到子知识库节点，并保留完整路径。
   - 意图树路由可保留多个阈值以上的 KB 候选，最多 3 个；不要退回只取第一名的实现。
   - workflow 路由要覆盖 rewrite 后的全部子 query，并合并 KB 范围；不要只使用第一条 rewritten query。
   - deeper resolver 需要基于 ragent 的置信度、候选和歧义逻辑实现。

5. 检索插件体系
   - 新检索能力优先实现 `SearchChannel.is_enabled()` / `search(SearchContext)`。
   - 新后处理能力优先实现 `SearchResultPostProcessor`，通过 order 控制顺序。
   - 当前真实能力为 BM25、semantic vector、RRF、rerank、final limit。
   - 修改检索链路时保持 `retrieval_stage_counts` 和 `retrieval_stage_metrics` 同步，metrics 至少保留 records；通道还应保留 latency、query count 和 topK。
   - 单个 SearchChannel 失败时应按 ragent 语义返回空通道结果并记录 error metrics，不能中断整条检索链。
   - 单个 SearchResultPostProcessor 失败时应跳过该处理器并继续后续处理器，不能中断整条检索链。
   - ES、缓存、版本过滤、指标必须等真实后端或 ragent 实现明确后再做。

6. MCP
   - MCP 工具执行必须保留 `mcp.tool.<tool_id>` 节点级 trace。
   - `McpToolDefinition` 的 `server_name`、`transport`、`schema_version` 要有明确值。
   - 远程 MCP Server 注册必须按 server 隔离失败；单个 server `list_tools` 失败时记录 unhealthy/error/tool_count=0 并跳过，不能影响内置工具或其他远程 server。
   - 工具失败返回结构化 `McpToolCallResult(is_error=True)`，并记录 trace error。
   - 不要新增权限治理字段，除非 ragent 或产品需求给出字段语义。

7. 模型健康
   - 保持 provider/model/capability 级健康快照。
   - 保持 healthy/open/half_open 三态和半开并发保护。
   - 指定 provider 熔断时仍应按 fallback order 降级。
   - 非流式 LLM 调用失败时应按 ragent `ModelRoutingExecutor` 语义继续尝试下一个健康候选，不要只在调用前选择一次 provider。
   - 后续补后台面板、定时探测和启动预热前，先核对 ragent 对应实现。

8. 后台 UI
   - 后台侧边栏必须保持响应式左侧布局，缩放不能跳到顶部。
   - 侧边栏入口必须有 icon。
   - 列表统一展示“共 x 条”。
   - 搜索下拉只在 focus 且有输入时显示，点击结果后跳转。
   - 知识库、文档、分块需要真实修改功能。
   - 下拉框样式要统一，不使用突兀原生样式。
   - Trace 详情保持 ragent 风格的执行耗时表，不恢复杂乱树详情卡片。
   - 新后台面板优先放到 `components/admin/`，`AdminView` 只负责组合；子组件如果使用按钮、输入框、表格，要自带 scoped 样式或明确使用全局样式，不能依赖父组件 scoped CSS 穿透。

## 模块边界

- `modules/auth`：认证、密码哈希、Token。
- `modules/session`：会话、消息列表、删除和 owner 权限。
- `modules/chat`：非流式聊天、流式聊天、消息持久化、队列限流。
- `modules/chat/feedback.py`：助手消息反馈 upsert 与后台反馈列表查询，反馈只绑定 assistant 消息。
- `modules/knowledge`：知识库、文档、分块、结构化块、路由画像。
- `modules/ingestion`：入库流水线、分块策略、任务和节点日志。
- `modules/memory`：短期、中期、长期记忆。
- `modules/mcp`：MCP 工具注册、参数提取、远程客户端和执行编排。
- `modules/rag`：意图识别、查询改写、歧义引导、Prompt 模板、检索、rerank、答案后处理、workflow、trace。
- `modules/admin`：Dashboard、用户、意图树、关键词、流水线、trace、系统设置。
- `infra/llm`：模型调用、模型路由、模型健康。
- `infra/embeddings`：embedding provider。
- `infra/vector_store`：pgvector 和 memory vector store。
- `infra/document_parser`：Tika、OCR、结构化提取和标准化。
- `infra/storage`：上传源文件存储抽象，当前只实现本地 `local://` URI，不伪造 S3 后台能力。

## 推荐验证命令

后端针对性回归：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_ingestion_pipeline.py backend/src/tests/retriflow_backend/test_ingestion_api.py backend/src/tests/retriflow_backend/test_chat_api.py backend/src/tests/retriflow_backend/test_chat_rate_limit.py -q
```

前端构建：

```powershell
cd frontend
cmd /c npm.cmd run build
```

后台 UI 改动后还需要使用浏览器自动化检查桌面和窄屏截图。

## 注意事项

- 不要要求用户先选择知识库再聊天，首页必须直接可问。
- 不要让删除、修改、搜索只在前端假生效。
- 不要在来源中暴露内部路由、冗长路径或调试字段。
- 上传文档的 `source_uri` 是后端存储 URI，前端可用于后台诊断展示，但不要当作公开下载地址直接暴露给普通用户。
- 不要让 Markdown 回答退化成纯文本。
- 不要用时间戳差假装链路耗时，新链路必须记录真实耗时。
- 外部服务不可用时优先降级并给出明确错误，不要静默失败或长时间卡死。
- 工作区可能有用户或前序任务的未提交改动，禁止回滚无关文件。
