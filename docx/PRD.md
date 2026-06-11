# 产品需求文档（PRD）

## 产品概述

RetriFlow 是一个基于 `Python + FastAPI + LangChain + LangGraph + LangSmith + Vue 3` 的 Agentic RAG 项目，用于将原有 `ragent` 的核心能力迁移到 Python 技术栈，并在此基础上增强文档解析、混合检索、工具调用、多轮会话记忆与可观测性能力。

它面向“文档驱动问答”场景，覆盖从文档导入、解析、结构化提取、分块、索引、检索、重排、答案生成到来源回溯的完整链路。

## 目标用户

- 需要搭建企业知识库问答系统的开发者
- 需要维护知识库、文档和检索效果的运营人员
- 需要把 `ragent` 迁移成 Python 版本的项目团队
- 希望在 RAG 问答中接入工具调用、会话记忆和可观测能力的 AI 应用开发者

## 核心功能

- 首页直接聊天
- 登录认证
  - 用户注册
  - 用户登录
  - 当前用户信息
  - Bearer Token 鉴权
  - 前端登录页
  - 路由守卫
  - 顶部用户态展示与退出登录
  - 后台知识库与 ingestion 管理接口按角色控制
- 会话与消息持久化
- 会话支持 `owner_id`
- 文档上传、解析与结构化提取
- 文档分块与重建索引
- PostgreSQL + pgvector 持久化
- 混合检索
  - BM25 Top80
  - 向量 Top80
  - RRF Top50
  - rerank Top10
  - final Top5
- 意图识别
  - 知识检索
  - 工具调用
  - 闲聊对话
  - 引导澄清
- 查询重写与多意图拆分
- MCP 工具调用
- 三段式 Prompt 答案生成
- 答案后处理
  - 引用补齐
  - 来源链接
  - 安全过滤
  - Markdown 美化
- 多层会话记忆
  - 短期记忆：摘要 + 最近 N 轮
  - 中期记忆：目标、约束、已解决项、待确认项
  - 长期记忆：偏好、稳定约束、身份画像、稳定事实

## 功能优先级

### P0

- FastAPI + Vue 3 主架构
- 根目录统一 `.venv`
- 最小登录模块
- 首页直接聊天
- 会话与消息持久化
- Tika 文档解析与结构化提取
- 文档分块
- PostgreSQL 主库
- pgvector 向量持久化
- 混合检索主链路
- LangGraph 最小工作流
- MCP 第一阶段能力
- 三段式 Prompt 生成与答案后处理
- 短期记忆
- 中期记忆第二版
  - 独立 TTL
  - Prompt 注入上限
  - 基于 query 的相关性注入
- 长期记忆第二版
  - 独立 TTL
  - Prompt 注入上限
  - 基于 query 的相关性注入
  - 支持 owner 维度归属
  - 同类型偏好覆盖旧 active 记录
- 文档重建索引

### P1

- 更完整的 LangGraph 节点编排
- 中期记忆冲突合并与状态流转
- 长期记忆冲突合并、重要性评分与用户级持久化
- 更强的知识库画像与意图识别
- 更丰富的 MCP 工具与工具编排
- LangSmith 深度接入

### P2

- 多租户与权限体系
- 异步任务队列
- 批量导入与评测系统
- 管理后台监控面板

## 界面设计

### 首页 / 聊天页

- 默认就是聊天入口
- 左侧展示会话列表
- 中间展示消息流
- 底部固定输入框
- 右侧或下方展示来源片段、命中知识库、工作流元数据、MCP 调用结果
- 支持查看 rewritten queries
- 支持流式回答
- 助手消息支持 Markdown

### 管理页

- 展示知识库列表
- 展示文档列表
- 支持手动新建和文件上传
- 支持对已有文档执行 reindex
- 支持配置分块策略参数
- 支持 chunk 预览
- 支持查看 structured block、表格结构、ingestion 节点日志
- 非 `admin` 用户进入后台页时展示只读模式提示，隐藏新增知识库、手动入库、上传文档等管理操作
- `admin` 用户可在后台页直接对当前文档执行 reindex，并查看向量索引状态、chunk 数与最近索引时间

## 技术栈建议

- 后端：`Python 3.12`、`FastAPI`、`LangChain`、`LangGraph`、`LangSmith`、`Pydantic`、`httpx`
- 前端：`Vue 3`、`TypeScript`、`Vite`、`Vue Router`、`Axios`
- 前端登录态：`Pinia` + `localStorage` + Axios 请求拦截器
- 数据库：`PostgreSQL`
- 向量存储：`pgvector`
- 本地服务：`Apache Tika`、`OCR 服务`、`PostgreSQL + pgvector`
- 容器管理：`Docker Desktop`

## 代码风格和架构模式

- 后端采用 `api / core / domain / schemas / tests` 分层
- API 层保持薄，业务逻辑集中在 `domain`
- 配置统一收敛到 `core/config.py`
- 数据库连接与初始化统一收敛到 `core/state.py`
- 前端使用 Vue 3 Composition API 和 `<script setup lang="ts">`
- 常规接口调用统一使用 Axios
- 流式聊天保留 `fetch + ReadableStream`
- 受保护页面通过 Vue Router `meta.requiresAuth` + 全局路由守卫控制访问
- 优先测试驱动，保证链路可回归

## 限制条件和边界场景

- 正式运行默认使用 PostgreSQL，不以 SQLite 作为主库
- SQLite 仅用于测试与兼容模式
- pgvector 维度必须和 embedding 模型一致
- Tika 不可用时，文本类文档允许 UTF-8 fallback
- OCR 不可用时，图片说明抽取能力会退化
- LLM 或 reranker 不可用时，系统允许降级，但效果会下降
- 查询重写失败时必须自动回退到原问题，不阻断主检索链路
- 文档 reindex 优先基于数据库中已保存的标准化文本和 structured blocks 重建
- 短期记忆只清理摘要和中长期记忆表，不删除完整历史消息
- 中期记忆当前已具备 TTL 与 query 相关性注入，但还未完成冲突合并与版本治理
- 长期记忆当前已具备 TTL、query 相关性注入、owner 维度归属与同类型覆盖，但还未完成更完整的用户级画像治理
- 当前 MCP 采用程序控制调用，不是模型原生 function calling
- 当前认证采用 Bearer Token 方案，已具备用户表、登录态和当前用户上下文
- 当前前端已具备 `/login` 页面、Token 持久化、当前用户恢复、401 自动退出与跳转
- 当前后台接口权限：
  - `sessions`、`chat`、`knowledge` 读取需要登录
  - `knowledge` 写操作与 `ingestion` 查看需要 `admin`
- 当前前端后台页权限：
  - 普通登录用户可浏览知识库、文档与 chunk
  - `admin` 用户可执行知识库维护与 ingestion 任务查看
