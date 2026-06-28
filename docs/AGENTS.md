# RetriFlow AI 开发指引

## 项目概述

RetriFlow 是一个从零构建的企业级知识问答系统，后端使用 Python + FastAPI，前端使用 Vue 3 + TypeScript。项目核心是文档解析、结构化入库、分块、向量化、混合检索、答案生成、MCP 工具调用、多轮记忆、链路 Trace、队列限流和后台运营管理。

开发时必须先阅读 RetriFlow 当前实现，理解真实数据模型、接口和链路状态，再做最小必要改动。不要为了“看起来完整”而新增没有真实逻辑支撑的空功能。

## 开发规范

- 后端代码放在 `backend/src`。
- 前端代码放在 `frontend/src`。
- 新业务代码优先进入 `modules/`。
- LLM、embedding、vector store、document parser、storage 等基础设施进入 `infra/`。
- `domain/` 已移除，不要恢复 domain facade 或 re-export。
- API 层保持薄，只处理路由、鉴权、参数和 service 调用。
- 配置集中在 `backend/src/core/config.py`。
- 数据库连接、初始化、自动补表和 seed 集中在 `backend/src/core/state.py`。
- 修改接口、数据库、RAG 链路、后台功能或配置后，必须同步更新 `docs/` 对应主题。
- 文档更新不要写日期流水账，要把新状态融入 PRD、技术设计或开发指引的对应章节。

## 代码风格

- Python 保持清晰、低耦合、可测试。
- Pydantic schema 用于 API 入参、出参和关键结构化字段校验。
- 数据库新增字段时考虑旧库兼容，使用自动补列或幂等 SQL。
- 后端服务类不要在模块导入时创建全局业务单例。
- Vue 使用 Composition API 和 `<script setup lang="ts">`。
- 复杂前端业务逻辑优先放入 composable。
- 常规 HTTP 请求使用 Axios；流式聊天保留 SSE / `fetch + ReadableStream`。
- 后台页面必须基于真实后端数据，不使用无意义假数据。

## 测试要求

- 后端行为变化至少补充或更新 targeted pytest/unittest。
- 前端 UI 或 API 类型变化至少运行 `npm run build`。
- 涉及 Markdown 渲染时运行 `npm run test:markdown`。
- 涉及数据库结构时同步检查：
  - `backend/src/core/state.py`
  - `resource/database/schema_pg.sql`
  - 相关测试
- 涉及 seed 数据时同步检查：
  - `resource/database/init_data_pg.sql`
  - `resource/database/init_intent_nodes_pg.sql`
  - 相关测试
- 测试使用 SQLite 时显式设置：
  - `RETRIFLOW_DATABASE_BACKEND=sqlite`
  - `RETRIFLOW_DB_PATH=<temp db>`
  - `RETRIFLOW_DATABASE_DSN=`
  - `RETRIFLOW_PGVECTOR_DSN=`
  - `RETRIFLOW_VECTOR_STORE_TYPE=memory`
- 声称完成前必须说明实际运行过哪些测试或构建。

## 工程原则

- 不新增没有真实后端支撑的前端壳。
- 不伪造 trace 节点、队列状态、模型健康或检索结果。
- 不用时间戳差值假装链路耗时，必须记录真实节点耗时。
- 外部服务不可用时优先降级并给出明确错误，不要静默失败或长时间卡死。
- 新功能应沿用现有模块边界和数据流，不做无关重构。
- 工作区可能有用户或前序任务的未提交改动，禁止回滚无关文件。

## 重点模块约束

### 流式 Trace

- 保持 `chat.stream` 生命周期在 `RetriFlowStreamingService`。
- `generation.answer` 必须 detached 且 close-aware。
- 断流时将运行中节点标记为 `cancelled`。
- Trace 详情保持执行耗时表，避免恢复杂乱树详情卡片。

### Redis 队列

- SSE 队列启用时先发 `event: queue`，payload 使用 limiter `snapshot()`。
- memory 和 Redis 等待取消都要清理排队项。
- 超时拒绝要持久化用户问题和助手拒绝回复。
- 队列状态和请求级队列位置必须来自 limiter/ticket 真实状态，不要前端估算。

### Ingestion runtime

- 当前节点持久化契约是 `node_id`、`node_type`、`node_order`、`status`、`success`、`message`、`error_message`、`duration_ms`、`output`。
- pipeline 执行必须校验缺失 next 和环，从第一个起点节点沿 `next_node_id` 执行，不执行断开的孤立节点。
- 节点执行必须通过执行器注册表按 `node_type` 分发；未知节点类型要失败并停止链路，不要伪造成成功日志。
- 数据通道上传或重建索引遇到无效 pipeline 时，应返回清晰的 400 业务错误。
- 不要新增 retry/count/input 字段，除非产品需求给出字段语义。
- 新节点输出遵循现有抽取协议：parser/fetcher 输出来源和文本，enhancer 输出增强文本、关键词和问题，chunker/enricher 输出 chunk count 与 chunks，indexer 输出 settings 与 chunk count。

### 意图树 resolver

- 保持 Redis intent tree cache 的 get/save/clear/exists 语义。
- admin intent node create/update/delete 后必须清缓存。
- 父节点命中但没有绑定知识库时，可以 fallback 到子知识库节点，并保留完整路径。
- 意图树路由可保留多个阈值以上的 KB 或 MCP 候选，最多 3 个；不要退回只取第一名。
- MCP 类型节点必须通过 `mcp_tool_id` 路由到真实 MCP 工具执行。
- MCP 类型节点的 `param_prompt_template` 必须传给参数提取器。
- workflow 路由要覆盖 rewrite 后的全部子 query，并合并 KB/MCP 范围。

### 检索插件体系

- 新检索能力优先实现 `SearchChannel.is_enabled()` / `search(SearchContext)`。
- 新后处理能力优先实现 `SearchResultPostProcessor`，通过 order 控制顺序。
- 当前真实能力为 BM25、semantic vector、RRF、rerank、final limit。
- 修改检索链路时保持 `retrieval_stage_counts` 和 `retrieval_stage_metrics` 同步。
- 单个 SearchChannel 失败时返回空通道结果并记录 error metrics，不中断整条检索链。
- 单个 SearchResultPostProcessor 失败时跳过该处理器并继续后续处理器。

### MCP

- MCP 工具执行必须保留 `mcp.tool.<tool_id>` 节点级 trace。
- `McpToolDefinition` 的 `server_name`、`transport`、`schema_version` 要有明确值。
- 远程 MCP Server 注册必须按 server 隔离失败；单个 server `list_tools` 失败时记录 unhealthy/error/tool_count=0 并跳过。
- 工具失败返回结构化 `McpToolCallResult(is_error=True)`，并记录 trace error。
- 不要新增权限治理字段，除非产品需求给出字段语义。

### 模型健康

- 保持 provider/model/capability 级健康快照。
- 保持 healthy/open/half_open 三态和半开并发保护。
- 指定 provider 熔断时仍应按 fallback order 降级。
- 非流式 LLM 调用失败时继续尝试下一个健康候选，不要只在调用前选择一次 provider。
- 定时探测和启动预热通过 `infra/llm/monitor.py` 挂到 FastAPI lifespan，默认关闭。

### 后台 UI

- 后台侧边栏必须保持响应式左侧布局，缩放不能跳到顶部。
- 侧边栏入口必须有 icon。
- 列表统一显示分页和总数。
- 搜索下拉只在 focus 且有输入时显示，点击结果后跳转。
- 知识库、文档、分块具备真实修改入口；后续调整必须继续走真实后端接口。
- 下拉框样式要统一，不使用突兀原生样式。
- 欢迎页示例问题与推荐问法使用 `admin_sample_questions` 独立配置。
- 新建知识库、上传文档等操作遇到后端 409/400 业务错误时，前端必须显示后端 `detail`。
- 新后台面板优先放到 `components/admin/<feature>/`，公共控件放到 `components/admin/common/`。
- 后台表单状态和纯 UI 状态优先放到 `composables/admin/<feature>/`，通用分页、格式化和 toast 放到 `composables/admin/common/`。

## 模块边界

- `modules/auth`：认证、密码哈希、Token。
- `modules/session`：会话、消息列表、删除和 owner 权限。
- `modules/chat`：非流式聊天、流式聊天、消息持久化、队列限流。
- `modules/chat/feedback.py`：助手消息反馈 upsert 与后台反馈列表查询。
- `modules/knowledge`：知识库、文档、分块、结构化块、路由画像。
- `modules/ingestion`：入库流水线、分块策略、任务和节点日志。
- `modules/memory`：短期、中期、长期记忆。
- `modules/mcp`：MCP 工具注册、参数提取、远程客户端和执行编排。
- `modules/rag`：意图识别、查询改写、歧义引导、Prompt 模板、检索、rerank、答案后处理、workflow、trace。
- `modules/admin`：Dashboard、用户、意图树、关键词、流水线、trace、系统设置。
- `frontend/src/services/httpClient.ts`：前端 Axios 实例、Bearer Token、401 事件、通用 `request` 和 `requestBlob`。
- `infra/llm`：模型调用、模型路由、模型健康。
- `infra/embeddings`：embedding provider。
- `infra/vector_store`：pgvector 和 memory vector store。
- `infra/document_parser`：Tika、OCR、结构化提取和标准化。
- `infra/storage`：上传源文件存储抽象，支持本地 `local://` 与 RustFS/S3 `s3://bucket/key`。

## 推荐验证命令

后端针对性回归：

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
