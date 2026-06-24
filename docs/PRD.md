# RetriFlow PRD

## 产品概述

RetriFlow 是一个面向企业知识问答的 Agentic RAG 系统，使用 Python + FastAPI + LangChain/LangGraph 与 Vue 3 实现，目标是在 Python 技术栈中复现并逐步优化 ragent 的核心能力。

系统支持用户在首页直接提问，由后端自动完成会话记忆、意图识别、知识库路由、查询改写、混合检索、MCP 工具调用、答案生成和链路追踪。后台用于管理知识库、文档、分块、流水线、意图树、模型健康、用户和系统配置。

## 目标用户

- 需要搭建企业知识库问答系统的开发团队。
- 需要维护知识库、文档、分块、索引和检索效果的运营人员。
- 需要从 ragent 迁移到 Python + Vue 技术栈的项目团队。
- 需要在 RAG 问答中接入 MCP 工具、会话记忆、链路追踪和后台配置的 AI 应用开发者。

## 核心功能

### 必须做（当前主链路）

1. 登录与权限

   - 支持注册、登录、Bearer Token 鉴权。
   - 支持普通用户和 admin 角色。
   - 后台管理操作仅 admin 可用，普通用户进入后台时给出明确权限提示。
2. 首页聊天

   - 首页就是聊天入口，不要求用户先选择知识库。
   - 支持 SSE 流式回答和 Markdown 渲染。
   - 支持深度思考开关、引用来源、workflow metadata 和 MCP 调用结果展示。
   - 欢迎页示例问题与推荐问法由后台独立配置，不绑定具体知识库。
   - 支持对助手消息提交 `vote/reason/comment` 反馈，反馈采用 upsert 语义并可在后台查看。
3. 会话与记忆

   - 支持会话创建、列表、删除、历史消息持久化。
   - 支持短期摘要记忆、中期记忆和长期记忆。
   - 记忆链路提供后台诊断接口，便于排查 Prompt 注入内容。
4. 知识库管理

   - 支持知识库新增、修改、列表、搜索和统计。
   - 支持 embedding 模型与 collection name 配置。
   - collection name 仅允许小写英文字母和数字。
   - 新增或修改时校验知识库名称和 collection name 重复，并在前端显示后端业务提示。
   - 删除知识库时同步删除文档、分块、入库任务、向量记录和对应对象存储 bucket。
   - 支持知识库路由画像、示例问题和关键词。
5. 文档管理

   - 支持上传、修改、列表、搜索、重新索引和删除。
   - 文档修改使用与上传一致的表单，只是填入已有配置。
   - 上传时不再手动选择文档类型，而是选择分块策略和数据通道。
   - 上传源文件先进入可替换文件存储，当前支持本地 `local://` 与 RustFS/S3 `s3://bucket/key` source URI，文档列表和详情保留该 URI。
   - 同一知识库内不允许重复上传完全相同的源文件；后端按源文件 SHA-256 判重，前端展示“该文档已上传过”的业务提示。
   - 对象存储 key 使用内容 hash 前缀和原始中文文件名，避免随机乱码名并保持同内容稳定命名。
   - 支持 Tika 解析、结构化块、表格单元格、图片说明、OCR 降级和标准化清洗。
6. 分块管理

   - 支持固定大小、递归、语义、混合和结构感知分块。
   - 默认策略为结构感知分块。
   - 结构感知分块保留 Markdown 标题、段落和代码块边界，默认 overlap 为 0。
   - 列表左下角展示“共 x 条”，后台搜索为点击式下拉跳转，不做输入即跳转。
7. 检索与答案生成

   - 支持 BM25、向量召回、RRF 融合、rerank 和 final topK。
   - 检索流程已抽象为 SearchChannel 和 SearchResultPostProcessor。
   - 意图树路由可保留多个阈值以上的 KB 候选，最多 3 个目标参与后续检索。
   - workflow metadata 暴露检索 stage counts 和 stage metrics，包括通道耗时、query count、topK 与后处理器输入输出数量。
   - 使用三段式 Prompt：System Prompt、Retrieved Context、User Query。
   - Prompt 已由场景化模板服务加载和渲染，覆盖 rewrite、intent、guidance 和 answer 场景。
   - 答案后处理包含引用补齐、来源展示、安全过滤、Markdown 格式整理和兜底回复。
8. MCP 工具调用

   - 支持内置工具和远程 MCP Server。
   - 支持单轮多工具顺序或并行执行。
   - 远程 MCP Server 初始化失败时只标记该 server 不健康并跳过，不影响内置工具和其他远程工具注册。
   - 保留远程 MCP Server 健康状态、注册工具数量和错误信息，便于后台后续治理展示。
   - 工具调用失败应返回结构化错误，不应拖垮整个问答链路。
   - 工具执行接入节点级 trace，并记录 server、transport 和 schema version。
9. 模型健康

   - 支持 provider/model 级健康快照、失败计数、healthy/open/half_open 三态熔断。
   - 支持持久化恢复、主动探测接口、半开并发保护和 provider fallback。
   - 非流式 LLM 调用按 ragent 候选模型执行语义进行当次请求 fallback，首选 provider 调用失败后记录失败并继续尝试下一个健康候选。
   - 后台已有模型健康 API 和可视化面板，后续继续补定时探测、启动预热和流式首包探针。
10. 链路 Trace

- 支持 `rag_trace_nodes` 节点级 trace。
- 同步和流式聊天均记录真实运行节点。
- 后台 Trace 列表支持按 trace id、session id、task id、用户、状态和起止时间分页筛选。
- 流式 `chat.stream` 覆盖 SSE 生命周期，`generation.answer` 在完成、异常或取消时关闭。
- 检索节点命名对齐 ragent：`retrieval-engine`、`multi-channel-retrieval`。
- 意图和改写节点命名对齐 ragent：`intent-resolve`、`query-rewrite-and-split`。

11. 队列限流

- 支持内存 FIFO 队列和 Redis 队列。
- Redis 使用 Docker 服务，基于 ZSET、entry TTL、Lua claim、active permit 和 release publish。
- SSE 会先发 `event: queue`，内容来自 limiter snapshot。
- 超时拒绝会持久化用户问题和助手忙碌回复，并发送 `reject`、`final`、`done`。
- 等待中断开连接会清理 memory/Redis 等待项。

### 后续继续对齐 ragent

1. Redis 队列还缺更细的队列位置遥测；用户级并发只有在 ragent 或产品需求明确后再做。
3. Ingestion runtime 还需继续贴近 ragent 的节点上下文、条件执行和输出抽取。
4. 意图树 resolver 已支持多 KB 候选保留、父节点 fallback、多 query 路由合并和接近分数下的澄清引导；但还需要更深的置信度传播、节点级参数和完整 trace。
5. 检索插件体系已具备 channel/postprocessor 抽象和 stage metrics，但还缺缓存、版本过滤和更完整治理。
6. MCP 已具备远程 server 注册健康状态和失败跳过机制，但还缺原生模型 function calling 与更完整的远程治理展示。
7. 模型健康已有后台 API、独立后台面板、手动 probe、熔断、持久化和非流式当次请求 fallback；还缺定时探测、启动预热和流式首包探针 fallback。
8. 后台 UI 已按功能拆出 Dashboard、模型健康、Trace、知识库、文档、分块、意图、关键词、数据通道、示例问题、用户和设置等面板，并将公共弹窗、分页、toast 与表单控件下沉到 `components/admin/common`；`AdminView` 仍需要继续瘦身为更纯粹的路由级编排。

## 后台界面设计

- 后台保持左侧侧边栏布局，缩放和窄屏时侧边栏不能跳到顶部。
- 侧边栏每个入口都需要有清晰 icon。
- 知识库、文档、分块等列表统一在左下角展示“共 x 条”。
- 搜索框只有在 focus 且输入内容后显示下拉结果，鼠标离开或失焦后隐藏。
- 下拉结果由用户点击后跳转，不进行输入实时跳转。
- 所有下拉框需要使用统一的产品化样式，避免浏览器原生选择框的突兀感。
- Trace 详情采用 ragent 风格的执行耗时表，不堆叠无关调试卡片。
- 系统设置页已拆成独立后台面板；模型健康已独立展示 provider/model 状态汇总、手动探测表单和快照表格。

## 产品边界

- 不新增 ragent 源码没有体现、RetriFlow 也没有真实支撑的空功能。
- ES 只在存在真实后端实现后接入；当前不添加空 Elasticsearch 服务。
- `guidance-detect` 属于 ragent 意图树候选歧义检测，RetriFlow 当前简单澄清意图不等价，不能伪造 trace 节点。
- `conversation-title-gen` 属于 ragent 的 LLM 标题生成，RetriFlow 当前是请求/手动标题，不添加伪 trace。
