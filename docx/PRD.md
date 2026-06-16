# 产品需求文档（PRD）

## 产品概述

RetriFlow 是一个基于 `Python + FastAPI + LangChain + LangGraph + LangSmith + Vue 3` 的 Agentic RAG 项目，用于复现并优化原 `ragent` 项目的核心能力。系统面向“文档驱动问答”场景，用户可以在首页直接提问，系统根据会话记忆、意图识别、查询重写、知识库路由、混合检索和工具调用自动完成回答。

当前产品已形成完整 RAG 主链路：文档解析、结构化提取、标准化清洗、分块、向量化、pgvector 持久化、BM25 + 向量混合检索、RRF 融合、rerank、三段式 Prompt 生成、答案后处理、流式 Markdown 输出、引用来源展示、会话记忆和链路追踪。

## 目标用户

- 需要搭建企业知识库问答系统的开发者。
- 需要维护知识库、文档、切块、索引和检索效果的运营人员。
- 需要从 `ragent` 迁移到 Python + Vue 技术栈的项目团队。
- 需要在 RAG 问答中接入 MCP 工具、会话记忆、链路追踪和后台配置的 AI 应用开发者。

## 核心功能

- 登录认证：注册、登录、Bearer Token 鉴权、用户角色、admin 权限控制。
- 首页直接聊天：用户不需要先选择知识库，系统自动做意图识别和知识库路由。
- 流式回答：聊天页默认 SSE 流式输出，前端按 Markdown 样式渲染回答。
- 会话管理：会话创建、会话列表、历史消息持久化、会话删除、用户隔离。
- 多轮记忆：短期记忆使用“摘要 + 最近 N 轮”，中期和长期记忆支持 TTL、相关性筛选和 Prompt 注入上限。
- 意图识别：知识检索、工具调用、闲聊对话、引导澄清四类意图，规则快速过滤 + LLM 精确分类，失败默认知识检索。
- 查询重写：在记忆之后、检索之前执行指代消解、上下文补全、口语转正式、多意图拆分。
- 文档解析：基于 Apache Tika 做 MIME 检测和文档解析，支持 PDF、DOC、DOCX、Markdown、文本和表格类文档。
- 结构化提取：保留标题层级、正文段落、表格 row/col/header 关系、图片说明、页码。
- OCR / 图片说明：支持本地 OCR 服务，优先从文档内嵌图片抽取说明；OCR 不可用时降级。
- 标准化清洗：统一编码、单位格式、空值和异常值处理，关键字段使用 Pydantic schema 校验。
- 文档分块：固定大小、重叠、递归、语义、混合分块，支持自定义 chunk size、overlap 和递归分隔符。
- 向量持久化：使用 PostgreSQL + pgvector 存储 chunk 向量，测试环境支持内存向量存储。
- 混合检索：BM25 Top80 + 向量 Top80，RRF Top50，rerank Top10，最终 Top5。
- 重排序：支持 OpenAI-compatible reranker，例如 `Qwen/Qwen3-Reranker-8B`。
- 答案生成：三段式 Prompt，包括 System Prompt、Retrieved Context、User Query，低 temperature 抑制幻觉。
- 答案后处理：引用补齐、来源展示、安全过滤、Markdown 格式整理、兜底回复。
- MCP 工具调用：支持内置工具和远程 MCP Server，支持顺序/并行执行、单轮多工具和失败容错。
- 后台管理：Dashboard、知识库管理、文档管理、切块管理、意图树、关键词映射、流水线管理、链路追踪、用户管理、系统设置。

## 功能优先级

### P0：必做

- FastAPI + Vue 3 主架构。
- 根目录统一 `.venv`。
- 登录认证与角色权限。
- 首页直接聊天、流式输出、Markdown 渲染。
- 会话与消息持久化。
- Apache Tika 文档解析与结构化提取。
- 文档分块、向量化、pgvector 持久化。
- BM25 + 向量混合检索、RRF、rerank、Top5 返回。
- LangGraph 工作流适配。
- 三段式 Prompt 生成与答案后处理。
- 短期/中期/长期记忆第一版。
- 意图识别和查询重写。
- 后台知识库、文档、切块、索引、用户、系统设置基础管理。
- PostgreSQL 初始化脚本和默认管理员账号。
- 链路追踪真实耗时记录。

### P1：增强

- 更完整的 LangGraph 节点级编排和节点级耗时。
- 更强的意图树可视化编辑和版本管理。
- 中长期记忆冲突合并、重要性评分和生命周期治理。
- 更完整的 MCP 工具编排和模型原生 function calling 适配。
- LangSmith 深度接入。
- Dashboard 更丰富的运营指标和可视化图表。

### P2：远期

- 多租户与细粒度 RBAC。
- 异步任务队列。
- 批量导入和评测系统。
- 多模态文档理解和图片说明生成。
- 更完整的审计日志和告警体系。

## 界面设计

### 首页 / 聊天页

- 默认就是聊天入口，不要求用户先进入某个知识库。
- 左侧展示会话列表，支持创建和删除会话。
- 空会话展示示例问题，引导用户开始提问。
- 中间展示消息流，AI 回答以流式 Markdown 格式输出。
- 输入区支持深度思考开关。
- 回答下方展示参考来源，避免直接暴露内部 API 路由或冗长路径。
- 可展示 rewritten queries、命中来源、工作流元数据和 MCP 调用结果。

### 后台管理页

- 普通用户进入后台时隐藏管理操作，并给出明确的无权限提示。
- admin 用户可管理知识库、文档、切块、索引、用户和系统配置。
- 知识库管理采用“知识库 -> 文档 -> 切块”的层级体验。
- 文档列表展示来源、状态、索引状态、chunk 数、上传时间、最近索引时间。
- 切块表格避免文字挤压成竖排，长文本可换行展示。
- Dashboard 支持 24h / 7d / 30d 范围切换，并联动图表和统计卡片。
- 链路追踪展示 trace 列表、详情、消息节点、真实耗时、平均耗时和 P95。

## 技术栈建议

- 后端：`Python 3.12`、`FastAPI`、`LangChain`、`LangGraph`、`LangSmith`、`Pydantic`、`httpx`、`psycopg`。
- 前端：`Vue 3`、`TypeScript`、`Vite`、`Vue Router`、`Pinia`、`Axios`。
- 数据库：`PostgreSQL`，测试兼容 `SQLite`。
- 向量存储：`pgvector`，测试兼容内存向量存储。
- 文档解析：`Apache Tika`。
- OCR：本地 OCR 服务，推荐通过 Docker Desktop 管理。
- 本地模型：`Ollama` 可用于意图识别、查询重写、路由和记忆摘要等轻量任务。
- 在线模型：支持 OpenAI-compatible API，例如 SiliconFlow、DashScope、DeepSeek 等。

## 代码风格和架构模式

- 后端采用 `api / core / modules / infra / schemas / tests` 分层。
- `modules/` 存放业务模块：auth、chat、session、knowledge、ingestion、memory、mcp、rag、admin。
- `infra/` 存放基础设施适配：llm、embeddings、vector_store、document_parser。
- `domain/` 已移除；新业务代码和测试必须从 `modules` 或 `infra` 导入。
- API 层保持薄，只做参数接收、鉴权依赖和 service 调用。
- 配置集中在 `backend/src/core/config.py`。
- 数据库连接、初始化、自动补表和 seed 集中在 `backend/src/core/state.py`。
- 前端常规 HTTP 请求使用 Axios，流式聊天保留 SSE / `fetch + ReadableStream`。
- Vue 使用 Composition API 和 `<script setup lang="ts">`。
- 修改接口、数据库、RAG 链路、后台能力或配置后，需要同步更新 `docx/` 文档。

## 限制条件和边界场景

- 正式运行默认使用 PostgreSQL；SQLite 仅用于测试和兼容模式。
- 默认向量存储是 pgvector；测试中应显式设置 `RETRIFLOW_VECTOR_STORE_TYPE=memory`，避免连接外部 PostgreSQL。
- pgvector 向量维度必须与 embedding 模型一致。
- Tika 不可用时，文本类文档允许 UTF-8 fallback；复杂文档解析能力会下降。
- OCR 不可用时，图片说明能力会退化。
- LLM、embedding 或 reranker 不可用时允许降级，但检索和生成质量会下降。
- 查询重写失败时必须回退到原始问题，不能阻断主检索链路。
- 意图识别失败时默认走知识检索。
- 新消息必须写入 `conversation_messages.duration_ms`；历史消息没有耗时时，链路追踪才允许回退到时间戳估算。
- 默认 PostgreSQL seed 管理员账号为 `admin / admin`，密码哈希必须与当前 Python 校验算法一致。
