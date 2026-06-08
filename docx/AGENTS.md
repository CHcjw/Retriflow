# AGENTS 指令文件

## 项目概述

RetriFlow 是一个 `Python + Vue` 的 Agentic RAG 项目，目标是把 `ragent` 的核心能力迁移到：

- 后端：LangChain + LangGraph + LangSmith + FastAPI
- 前端：Vue 3 + TypeScript

当前项目已经具备：

- Tika 文档解析
- 结构化提取与 Pydantic 校验
- 多策略分块
- PostgreSQL 主库存储
- pgvector 向量持久化
- 首页直接聊天
- 知识库意图路由
- 混合检索
- LangGraph 最小工作流
- 三段式 Prompt 生成与答案后处理

## 开发规范

- 根目录统一使用 `.venv`
- 后端代码固定在 `backend/src`
- 前端代码固定在 `frontend/src`
- 后端保持 `api / core / domain / schemas / tests` 分层
- API 层尽量薄，业务逻辑集中在 `domain`
- 路由层避免导入时创建全局业务单例，优先按请求创建服务
- 修改接口、结构、配置后，必须同步更新 `docx/` 与 `docs/`

## 测试要求

- 新增或修改后端行为时，优先补测试
- 至少保证相关单测通过
- 本轮重点回归范围：
  - `test_retrieval_engine`
  - `test_chat_api`
  - `test_answer_postprocessor`
  - `test_knowledge_route`
- 前端改动至少保证 `npm run build` 可通过

## 代码风格

- Python 保持清晰、低耦合、可替换
- 配置读取集中在 `core/config.py`
- 数据库初始化与连接集中在 `core/state.py`
- 检索、路由、rerank、工作流等核心逻辑集中在 `domain`
- Vue 使用 Composition API 与 `<script setup lang="ts">`
- 普通 HTTP 请求使用 Axios
- 流式聊天保留 `fetch + ReadableStream`

## 注意事项

### 启动方式

- 后端应通过工厂模式启动
- 推荐命令：

```powershell
& .\.venv\Scripts\python.exe .\backend\src\main.py
```

### RAG 检索链路

当前标准链路为：

1. BM25 Top80
2. 向量 Top80
3. RRF Top50
4. rerank Top10
5. 最终返回 Top5

### 首页直聊规则

- 不要要求用户先进入某个知识库
- 先做知识库意图路由
- 高置信度限定知识库召回
- 低置信度走全局召回

### 生成答案规则

- 使用三段式 Prompt：
  - System Prompt
  - Retrieved Context
  - User Query
- 低温度生成，默认 `temperature = 0.1`
- 最终答案必须经过后处理：
  - 引用补齐
  - 参考来源追加
  - 冲突提示
  - 基础安全过滤

### 数据库

- 正式运行默认主库是 PostgreSQL
- SQLite 仅用于测试和兼容模式
- 默认向量表是 `retriflow_chunk_vectors`

### 外部依赖

- Tika、OCR、PostgreSQL + pgvector 建议通过 Docker Desktop 管理
- 如果外部服务不可用，系统应尽量降级而不是直接崩溃
