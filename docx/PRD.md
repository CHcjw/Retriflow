# 产品需求文档（PRD）

## 产品概述

RetriFlow 是一个基于 `Python + LangChain + LangGraph + LangSmith + Vue` 的 Agentic RAG 项目，用于承接并升级原 `ragent` 的知识库问答能力。系统围绕“文档解析、结构化提取、清洗校验、分块、向量化、混合检索、重排序、答案生成”构建完整链路，目标是提供可追溯、可扩展、可落地的知识增强问答平台。

## 目标用户

- 企业内部知识问答使用者
- 知识库维护和运营人员
- AI 应用开发者
- 需要将 `ragent` 迁移到 Python 技术栈的项目团队

## 核心功能

- 首页直接聊天
  - 用户无需先进入某个知识库
  - 后端先做知识库意图路由，再决定限定检索或全局检索
- 会话管理
  - 新建会话
  - 查看历史消息
  - 持久化用户与助手消息
- 知识库管理
  - 创建知识库
  - 查看知识库列表与文档数量
  - 查看文档、chunk、结构化 block
- 文档入库
  - 手动录入文本
  - 上传文件入库
  - Apache Tika 解析
  - OCR 辅助图片文本或图片说明提取
  - Pydantic 结构校验
- 结构化提取
  - 标题层级
  - 正文段落
  - 表格结构
  - 图片说明
  - 页码信息
- 分块引擎
  - 固定大小分块
  - 重叠分块
  - 递归分块
  - 语义分块
  - 混合分块
- RAG 检索
  - BM25 关键词检索
  - 纯向量检索
  - RRF 融合
  - rerank 重排序
  - 返回可追溯来源
- 聊天工作流
  - 同步问答
  - 流式问答
  - LangGraph 工作流适配
  - LLM 不可用时降级回答
  - 三段式 Prompt 生成
  - 引用与参考来源后处理

## 功能优先级

### P0

- FastAPI + Vue 项目骨架
- 根目录统一 `.venv`
- 首页直接聊天
- 会话与消息持久化
- 文档上传与手动入库
- Tika 解析与结构化抽取
- 分块引擎
- PostgreSQL 主库
- pgvector 向量持久化
- 混合检索主链路
  - BM25 Top80
  - 向量 Top80
  - RRF Top50
  - rerank Top10
  - 最终 Top5
- LangGraph 最小工作流
- 答案生成与后处理

### P1

- 更强的知识库路由配置与样例管理
- 独立 reranker 服务治理
- 更完整的 LangGraph 节点编排
- LangSmith 追踪增强
- 更多文档格式深度优化
- 更强的答案安全审查与冲突分析

### P2

- 多租户与权限体系
- 异步任务队列
- 批量导入与评测
- 运营监控面板

## 界面设计

### 首页 / 聊天页

- 默认就是聊天入口
- 左侧为会话列表
- 中间为消息流
- 右侧或下方展示来源片段、命中知识库、工作流元数据
- 支持流式回答
- 助手消息支持 Markdown 展示

### 管理页

- 知识库列表
- 文档列表
- 文档上传与手动新建
- 分块策略配置
- chunk 预览
- ingestion 节点日志与结构化 block 查看

## 技术栈建议

- 后端：Python 3.12、FastAPI、LangChain、LangGraph、LangSmith、Pydantic、httpx
- 前端：Vue 3、TypeScript、Vite、Vue Router、Axios
- 数据库：PostgreSQL
- 向量存储：pgvector
- 本地依赖服务：Docker Desktop 启动 Tika、OCR、PostgreSQL + pgvector

## 代码风格和架构模式

- 后端采用 `api / core / domain / schemas / tests` 分层
- API 层保持薄，业务逻辑集中在 `domain`
- 配置和数据库初始化集中在 `core`
- 前端使用 Vue 3 Composition API 与 `<script setup lang="ts">`
- 普通接口请求使用 Axios
- 流式聊天保留 `fetch + ReadableStream`

## 限制条件和边界场景

- 正式运行默认使用 PostgreSQL，不再以 SQLite 作为主库
- SQLite 仅保留给测试和兼容场景
- pgvector 维度必须与当前 embedding 模型一致
- 当 pgvector 不可用时，系统回退到内存向量检索
- 当 Tika 不可用时，文本类文件允许 UTF-8 fallback
- 当 LLM 或 reranker 不可用时，系统允许降级，但回答质量会下降
- 当前知识库意图路由以知识库画像为核心，可选启用 LLM 路由，失败时回退到本地画像匹配
