# 产品需求文档（PRD）

## 产品概述

RetriFlow 是一个基于 Python + LangChain + LangGraph + LangSmith + Vue 的 Agentic RAG 平台，用于承接并升级 `ragent` 的知识库问答能力。系统围绕“文档解析 -> 结构化提取 -> 清洗标准化 -> 分块 -> 向量化 -> 检索 -> 生成回答”形成完整链路，并默认采用 PostgreSQL 主库 + pgvector 同库的架构。

## 目标用户

- 企业内部知识问答使用者
- 知识库运营和维护人员
- AI 平台研发与运维人员
- 需要从 `ragent` 迁移能力的开发者

## 核心功能

- 会话管理
  - 新建会话
  - 查看历史消息
  - 持久化用户与助手消息
- RAG 聊天
  - 同步问答
  - 流式问答
  - 展示命中来源
  - 展示工作流元数据
- 知识库管理
  - 新建知识库
  - 查看知识库文档数
  - 查看文档列表
- 文档入库
  - 手动录入文本
  - 上传文件入库
  - Apache Tika 解析
  - OCR 辅助图片说明提取
  - 结构化 block 持久化
- 分块引擎
  - 固定大小分块
  - 重叠分块
  - 递归分块
  - Embedding 语义分块
  - 递归 + 语义混合分块
  - 自动策略选择
- 向量化与向量存储
  - chunk embedding
  - PostgreSQL + pgvector 持久化
  - 内存 fallback 检索
- 检索
  - keyword 通道
  - document title 通道
  - semantic 通道
  - 去重与排序

## 功能优先级

### P0

- FastAPI + Vue 项目骨架
- 会话与消息持久化
- 知识库、文档、chunk、ingestion task 管理
- Tika 文档解析链路
- 分块引擎
- 向量化
- PostgreSQL 主库存储
- pgvector 同库向量持久化
- 同步与流式聊天
- LangGraph 最小工作流 `retrieve -> generate`

### P1

- rerank
- 更完整的 LangGraph 节点编排
- 会话摘要与长期记忆
- 更多文件格式深度解析优化
- LangSmith trace 深化

### P2

- 多租户
- 权限体系
- 异步任务队列
- 批量导入与评测
- 监控与运维面板

## 界面设计

### 聊天页

- 左侧会话列表
- 中间消息流
- 展示来源片段和工作流信息
- 支持流式增量显示

### 管理台

- 知识库卡片列表
- 文档列表
- 文档上传与手动创建
- 分块策略配置面板
- chunk 预览
- ingestion 节点日志

## 技术栈建议

- 后端：Python 3.12、FastAPI、LangChain、LangGraph、LangSmith、Pydantic
- 前端：Vue 3、TypeScript、Vite、Vue Router、Axios
- 主数据库：PostgreSQL
- 向量存储：pgvector
- 本地依赖服务：Docker Compose 启动 Tika、OCR、PostgreSQL + pgvector

## 代码风格和架构模式

- 后端分层：`api / core / domain / schemas / tests`
- API 层保持薄
- 业务逻辑集中在 `domain`
- 数据库连接与初始化集中在 `core`
- 前端采用 Vue 3 Composition API + `<script setup lang="ts">`
- 普通 API 请求走 axios，流式聊天保留 fetch + ReadableStream

## 限制条件和边界场景

- 默认业务主库已切换为 PostgreSQL，不再以 SQLite 作为正式业务主库
- SQLite 仅保留兼容模式和测试隔离用途
- pgvector 表的维度需要与当前 embedding 模型保持一致
- 当 pgvector 不可用时，系统仍会回退到本地内存语义检索，保证功能不中断
- 当 Tika 不可用时，`txt/md/html` 等文本类文件会自动回退到 UTF-8 文本解析
- 当前 rerank 尚未接入
- 当前 LangGraph 仍是最小工作流，不含复杂工具规划链
