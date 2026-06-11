# AGENTS 指令文件

## 项目概述

RetriFlow 是一个 `Python + Vue` 的 Agentic RAG 项目，目标是将 `ragent` 的核心能力迁移并增强到以下技术栈：

- 后端：LangChain + LangGraph + LangSmith + FastAPI
- 前端：Vue 3 + TypeScript

当前项目已具备或正在完善以下核心能力：

- Tika 文档解析
- 结构化提取与 Pydantic 校验
- 多策略分块
- PostgreSQL 主库存储
- pgvector 向量持久化
- 首页直接聊天
- 知识库意图识别
- 四类意图分类
- 混合检索
- LangGraph 工作流适配
- MCP 第一阶段能力
- 三段式 Prompt 生成与答案后处理
- 短期 / 中期 / 长期记忆
- 查询重写与多意图拆分
- 文档向量索引状态可视化
- 文档重建索引

## 开发规范

- 根目录统一使用 `.venv`
- 后端代码固定在 `backend/src`
- 前端代码固定在 `frontend/src`
- 后端保持 `api / core / domain / schemas / tests` 分层
- API 层尽量薄，业务逻辑集中在 `domain`
- 路由层避免导入时创建全局业务单例，优先按请求创建服务
- 修改接口、结构、配置后，必须同步更新 `docx/` 中的文档
- 手工编辑文件时使用补丁方式，避免覆盖用户已有改动
- 涉及文档分块、向量化、索引重建的变更时，优先复用现有 ingestion 链路
- 涉及查询重写的变更时，必须保证严格 JSON 输出与失败回退

## 测试要求

- 新增或修改后端行为时优先补测试
- 至少保证相关单测通过
- 当前重点回归范围包括：
  - `test_chat_api`
  - `test_chat_mcp_api`
  - `test_mcp_registry`
  - `test_mcp_parameter_extractor`
  - `test_mcp_service`
  - `test_mcp_remote_client`
  - `test_memory_service`
- 前端改动至少保证构建通过
- 涉及登录态改动时，必须同步检查 `stores/auth.ts`、`services/api.ts`、`router/index.ts`
- 涉及后台接口改动时，必须明确区分“仅登录可读”与“仅 admin 可写/可管”
- 在声称“已完成”前，必须说明是否已实际运行测试

## 代码风格

- Python 保持清晰、低耦合、可替换
- 配置读取集中在 `core/config.py`
- 数据库初始化与连接集中在 `core/state.py`
- 检索、路由、rerank、MCP、记忆、工作流等核心逻辑集中在 `domain`
- Vue 使用 Composition API 和 `<script setup lang="ts">`
- 常规 HTTP 请求使用 Axios
- 流式聊天保留 `fetch + ReadableStream`
- 登录态通过 Pinia + localStorage 管理，避免在多个组件内重复保存 token
- 后台页默认做角色感知：普通用户隐藏管理操作，非 `admin` 给出明确只读提示
- 管理员侧后台能力应优先覆盖：新增知识库、文档上传、手动入库、文档 reindex、索引状态可视化
- 优先写可回归测试，再补实现

## 注意事项

### 启动方式

后端通过工厂模式启动：

```powershell
& .\.venv\Scripts\python.exe .\backend\src\main.py
```

### RAG 检索链路

当前标准链路为：

1. 查询重写
2. BM25 Top80
3. 向量 Top80
4. RRF Top50
5. rerank Top10
6. final Top5

调试时优先关注：

- `workflow.rewritten_queries`
- `workflow.rewrite_query_count`
- `workflow.retrieval_stage_counts`
- `vector_index_status`
- `vector_chunk_count`
- `vector_indexed_at`

### 查询重写规则

- 发生在会话记忆加载之后、知识库路由与检索之前
- 优先利用对话历史做：
  - 指代消解
  - 上下文补全
  - 口语转正式表达
  - 多意图拆分
- 必须只输出结构化结果
- 若模型不可用或返回非法 JSON，必须自动回退为原始问题单查询

### 意图识别规则

- 当前支持四类意图：
  - `knowledge_retrieval`
  - `tool_call`
  - `chitchat`
  - `clarification`
- 执行顺序固定为：
  - `memory -> intent -> rewrite -> route/retrieve`
- 采用规则快速过滤 + LLM 精分类
- 分类失败默认回退到 `knowledge_retrieval`
- 当前默认意图识别 provider 为 `ollama`

### 文档索引规则

- 文档创建和文档 reindex 都必须刷新：
  - `vector_index_status`
  - `vector_chunk_count`
  - `vector_indexed_at`
- 文档 reindex 必须先删除该文档旧向量记录，再写入新向量
- 文档 reindex 必须保留历史 ingestion task
- 当前 reindex 基于数据库中已保存的标准化文本和 structured blocks 重建

### 首页直聊规则

- 不要要求用户先进入某个知识库
- 先做意图识别
- 再做知识库路由与 MCP 工具路由
- 高置信度知识库问题走限定召回
- 工具型问题可走 `mcp_only`
- 同时命中知识库和工具时走 `mixed`

### 会话记忆规则

- 短期记忆采用“摘要 + 最近 N 轮”
- 中期记忆当前提取：
  - `goal`
  - `constraint`
  - `resolved_item`
  - `open_item`
- 长期记忆当前提取：
  - `preference`
  - `constraint`
  - `profile`
  - `stable_fact`
- 中期 / 长期记忆都已支持：
  - TTL 过期控制
  - Prompt 注入上限
  - 基于 query 的相关性排序注入
- 长期记忆优先使用 `sessions.owner_id` 作为 owner
- 若同一 owner 下出现新的同类型长期记忆，旧 active 记录应置为 inactive
- 当前只清理记忆摘要和中长期记忆表，不删除完整消息历史
- 长期记忆当前已支持 owner 维度，但还未完成更深层的冲突合并和用户画像治理

### MCP 规则

- 当前 MCP 是程序控制调用，不是模型原生 function calling
- 默认内置工具包括：
  - `weather_query`
  - `sales_query`
- 支持远程 MCP Server 自动发现与调用
- 支持单轮命中多个 MCP 工具
- 执行模式支持：
  - `sequential`
  - `parallel`
- 容错规则支持：
  - 单工具失败不影响其他工具
  - `fail_fast=true` 时提前停止

### 答案生成规则

- 使用三段式 Prompt：
  - System Prompt
  - Retrieved Context
  - User Query
- MCP 命中时补充工具结果上下文
- 记忆命中时补充记忆上下文
- 默认 `temperature = 0.1`
- 最终答案必须经过后处理：
  - 引用补齐
  - 参考来源补全
  - 冲突提示
  - 基础安全过滤

### 数据库规则

- 正式运行默认主库是 PostgreSQL
- SQLite 仅用于测试和兼容模式
- 默认向量表是 `retriflow_chunk_vectors`

### 外部依赖

- Tika、OCR、PostgreSQL + pgvector 建议通过 Docker Desktop 管理
- 外部服务不可用时，系统应优先降级，而不是直接崩溃
