# RetriFlow

RetriFlow 是一个从零构建的企业级 Agentic RAG 系统。项目使用 Python + FastAPI + Vue 3 + TypeScript，覆盖文档解析、结构化入库、智能分块、向量化、混合检索、意图识别、问题重写、MCP 工具调用、多轮记忆、流式回答、来源引用、链路追踪和后台运营管理。

它不是一个最小 RAG Demo，而是一套可本地启动、可配置、可观测、可扩展的企业知识问答工程链路。

## 功能概览

- 对话入口：支持新建会话、流式回答、Markdown 渲染、深度思考、智能联网、来源引用、反馈、复制和重新生成。
- RAG 编排：通过 LangGraph 串联问题重写、意图识别、路由、混合检索、rerank、工具调用、答案生成和后处理。
- 企业知识库：支持知识库、文档、分块、路由画像、示例问题、关键词映射和意图树配置。
- 文档入库：支持 Tika 解析、结构化块、表格、图片说明、OCR 降级、重复文件判重和 RustFS/S3 对象存储。
- 检索增强：支持 BM25、向量召回、RRF、rerank、final topK 和可追溯来源片段。
- MCP 工具：支持远程 MCP Server、百度搜索、天气查询、参数抽取和节点级 trace。
- 多轮记忆：支持会话上下文、短期摘要、中长期记忆和后台诊断。
- 可观测性：内置后台链路追踪，可选接入 LangSmith tracing。
- 后台管理：Dashboard、用户、知识库、文档、分块、流水线、意图管理、关键词、示例问题、模型健康、Trace 和系统设置。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router、markdown-it、markstream-vue |
| 后端 | Python 3.12、FastAPI、Pydantic、Uvicorn、httpx |
| RAG 编排 | LangGraph、LangChain Core、LangSmith 可选 tracing |
| 存储 | PostgreSQL、pgvector、Redis、RustFS/S3 |
| 文档处理 | Apache Tika、OCR 服务、结构化解析与归一化 |
| 检索 | BM25、向量检索、RRF、rerank、来源后处理 |
| 工具调用 | MCP Client、远程 MCP Server、内置工具执行器 |

## 项目结构

```text
RetriFlow/
├─ backend/                              # Python 后端工程
│  ├─ pyproject.toml                     # 后端包定义与核心依赖
│  └─ src/
│     ├─ main.py                         # FastAPI app 工厂入口：main:create_app
│     ├─ api/                            # HTTP API 层
│     │  ├─ router.py                    # API 路由汇总
│     │  ├─ deps/                        # 鉴权等 FastAPI 依赖
│     │  └─ routes/                      # auth/chat/session/knowledge/admin/ingestion 路由
│     ├─ core/                           # 全局配置、应用状态
│     │  ├─ config.py                    # .env 配置读取与默认值
│     │  └─ state.py                     # 应用运行时状态容器
│     ├─ infra/                          # 基础设施适配层
│     │  ├─ document_parser/             # Tika、OCR、结构解析、内容归一化、图片说明
│     │  ├─ embeddings/                  # Embedding provider 封装
│     │  ├─ llm/                         # OpenAI-compatible LLM 调用、健康检查、监控
│     │  ├─ storage/                     # RustFS/S3 源文件对象存储
│     │  ├─ vector_store/                # pgvector 写入与检索
│     │  └─ distributed_lock.py          # 分布式锁
│     ├─ modules/                        # 业务模块
│     │  ├─ admin/                       # 后台聚合查询、配置管理、统计数据
│     │  ├─ auth/                        # 登录、用户与权限
│     │  ├─ chat/                        # 对话服务、流式输出、限流、反馈
│     │  ├─ ingestion/                   # 文档流水线、任务、节点执行
│     │  ├─ knowledge/                   # 知识库、文档、分块、路由画像、意图缓存
│     │  ├─ mcp/                         # MCP registry/client/service、参数抽取、执行器
│     │  ├─ memory/                      # 会话记忆与摘要
│     │  ├─ observability/               # 观测辅助模块
│     │  ├─ rag/                         # RAG 主链路
│     │  │  ├─ workflow.py               # LangGraph 工作流
│     │  │  ├─ workflow_adapter.py       # 流式/非流式链路适配
│     │  │  ├─ rewrite.py                # 问题重写与拆分
│     │  │  ├─ intent.py                 # 意图识别
│     │  │  ├─ retrieval/                # 检索通道、召回引擎、后处理
│     │  │  ├─ rerank.py                 # rerank 逻辑
│     │  │  ├─ prompt.py                 # Prompt 装载与渲染
│     │  │  ├─ postprocess.py            # 答案与来源后处理
│     │  │  ├─ trace.py                  # RAG 节点追踪
│     │  │  ├─ langsmith.py              # LangSmith 可选集成
│     │  │  └─ prompts/                  # answer/context/intent/memory/rewrite/route Prompt
│     │  └─ session/                     # 会话列表、消息持久化
│     ├─ schemas/                        # Pydantic 请求/响应模型
│     └─ tests/retriflow_backend/        # 后端单元与接口测试
│
├─ frontend/                             # Vue 前端工程
│  ├─ package.json                       # 前端依赖与 npm scripts
│  ├─ vite.config.ts                     # Vite 配置
│  └─ src/
│     ├─ main.ts                         # Vue 应用入口
│     ├─ App.vue                         # 顶层布局
│     ├─ router/                         # 路由定义
│     ├─ stores/                         # Pinia 状态：auth/app
│     ├─ services/                       # axios API 客户端：chat/admin/knowledge/session 等
│     ├─ composables/                    # 页面与业务组合逻辑
│     │  ├─ useRetriFlowChat.ts          # 聊天页状态、流式问答、反馈、会话管理
│     │  ├─ useRetriFlowAdmin.ts         # 后台数据编排
│     │  └─ admin/                       # 后台表单、分页、导航、Dashboard 等细分逻辑
│     ├─ views/                          # 页面级组件
│     │  ├─ HomeView.vue                 # 首页
│     │  ├─ LoginView.vue                # 登录页
│     │  ├─ ChatView.vue                 # 对话页
│     │  └─ AdminView.vue                # 后台管理页
│     ├─ components/
│     │  ├─ chat/                        # 聊天输入框、会话列表、消息正文
│     │  └─ admin/                       # 后台模块组件
│     │     ├─ chunks/                   # 分块表格与编辑
│     │     ├─ common/                   # 通知、Toast 等通用组件
│     │     ├─ dashboard/                # Dashboard 与模型健康
│     │     ├─ documents/                # 文档表格、上传、预览
│     │     ├─ intent/                   # 意图树、意图列表、节点弹窗
│     │     ├─ keyword/                  # 关键词映射
│     │     ├─ knowledge/                # 知识库表格与弹窗
│     │     ├─ pipeline/                 # 流水线管理
│     │     ├─ samples/                  # 欢迎页示例问题配置
│     │     ├─ settings/                 # 系统设置与 MCP 状态
│     │     ├─ trace/                    # 链路追踪列表与详情
│     │     └─ users/                    # 用户管理
│     ├─ utils/markdownRenderer.ts       # Markdown 流式渲染兼容处理
│     ├─ assets/                         # 全局样式
│     └─ tests/markdown-renderer-regression.mjs
│
├─ resource/
│  ├─ database/
│  │  ├─ schema_pg.sql                   # PostgreSQL 表结构
│  │  ├─ init_data_pg.sql                # 基础初始化数据，不包含业务知识库
│  │  ├─ init_intent_nodes_pg.sql        # 可选：意图树初始化脚本
│  │  ├─ drop_all_tables_pg.sql          # 清库脚本
│  │  └─ README.md                       # 数据库脚本说明
│  └─ sample_data/                       # 可用于试跑的业务/集团样例文档
│     ├─ biz/
│     └─ group/
│
├─ tools/
│  ├─ tika/                              # Tika Dockerfile、样例生成、上传验证
│  └─ ocr/                               # OCR 辅助服务
│
├─ docs/
│  ├─ PRD.md                             # 产品需求文档
│  ├─ TECH_DESIGN.md                     # 技术设计文档
│  └─ AGENTS.md                          # AI 开发协作约束
│
├─ docker-compose.services.yml           # PostgreSQL/Redis/RustFS/Tika/OCR 本地依赖
├─ requirements.txt                      # 后端开发安装依赖入口
├─ .env.example                          # 环境变量模板
└─ README.md
```

### 推荐阅读顺序

如果你是第一次接触项目，建议按这个顺序看代码：

1. `README.md`：跑通本地环境。
2. `docs/PRD.md`：理解产品边界。
3. `docs/TECH_DESIGN.md`：理解模块设计与数据流。
4. `backend/src/modules/rag/workflow.py`：理解 RAG 主链路。
5. `backend/src/modules/chat/service.py` 与 `backend/src/modules/chat/streaming.py`：理解问答入口和流式响应。
6. `backend/src/modules/knowledge/service.py` 与 `backend/src/modules/ingestion/service.py`：理解知识库、文档和切块入库。
7. `frontend/src/views/ChatView.vue` 与 `frontend/src/composables/useRetriFlowChat.ts`：理解聊天页。
8. `frontend/src/views/AdminView.vue` 与 `frontend/src/composables/useRetriFlowAdmin.ts`：理解后台管理。

## 环境要求

必需：

- Python 3.12+
- Node.js 20+
- Docker Desktop
- PostgreSQL 客户端工具，任选其一：HeidiSQL、psql、DataGrip 等

可选：

- LM Studio、Ollama、DashScope/百炼、SiliconFlow 等 OpenAI-compatible 模型服务
- LangSmith 账号，用于外部 tracing

## 快速开始

### 1. 克隆项目

```bash
git clone <your-retriflow-repo-url>
cd RetriFlow
```

### 2. 启动依赖服务

项目提供 PostgreSQL + pgvector、Redis、RustFS、Tika、OCR 的本地 Docker 服务。

```bash
docker compose -f docker-compose.services.yml up -d
```

服务端口：

| 服务 | 地址 |
| --- | --- |
| PostgreSQL/pgvector | `127.0.0.1:5433` |
| Redis | `127.0.0.1:6379` |
| RustFS API | `http://127.0.0.1:9000` |
| RustFS Console | `http://127.0.0.1:9001` |
| Tika | `http://127.0.0.1:9998` |
| OCR | `http://127.0.0.1:9889` |

PostgreSQL 默认连接：

```text
host=127.0.0.1
port=5433
database=retriflow
user=retriflow
password=retriflow
```

### 3. 初始化数据库

全新数据库按以下顺序执行：

1. `resource/database/schema_pg.sql`
2. `resource/database/init_data_pg.sql`

HeidiSQL 用户可以直接打开脚本执行。也可以用 `psql`：

```bash
psql "postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow" -f resource/database/schema_pg.sql
psql "postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow" -f resource/database/init_data_pg.sql
```

默认管理员账号：

```text
username: admin
password: admin
```

`init_intent_nodes_pg.sql` 是可选脚本。建议先在后台创建需要绑定的知识库，再执行该脚本初始化意图树节点。

### 4. 配置环境变量

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

Linux / macOS：

```bash
cp .env.example .env
```

最小本地运行建议：

```env
RETRIFLOW_DATABASE_BACKEND=pg
RETRIFLOW_DATABASE_DSN=postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow
RETRIFLOW_VECTOR_STORE_TYPE=pgvector
RETRIFLOW_PGVECTOR_DSN=postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow

RETRIFLOW_REDIS_URL=redis://127.0.0.1:6379/0
RETRIFLOW_TIKA_URL=http://127.0.0.1:9998
RETRIFLOW_OCR_URL=http://127.0.0.1:9889

RETRIFLOW_STORAGE_BACKEND=rustfs
RETRIFLOW_S3_ENDPOINT=http://127.0.0.1:9000
RETRIFLOW_S3_ACCESS_KEY_ID=rustfsadmin
RETRIFLOW_S3_SECRET_ACCESS_KEY=rustfsadmin

LANGSMITH_TRACING=false
LANGSMITH_PROJECT=retriflow
```

模型配置取决于你的本地或云端服务。项目支持 OpenAI-compatible provider，默认配置集中在 `.env` 与 `backend/src/core/config.py`。

需要接入 LangSmith 时，在 `.env` 中设置：

```env
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=retriflow
LANGSMITH_API_KEY=<your-langsmith-api-key>
```

不开启 LangSmith 时，RetriFlow 仍会使用后台“链路追踪”记录完整 RAG 节点耗时。

### 5. 安装并启动后端

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .\backend --no-deps
$env:PYTHONPATH = "backend/src"
.\.venv\Scripts\python.exe -m uvicorn main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Linux / macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e ./backend --no-deps
export PYTHONPATH=backend/src
python -m uvicorn main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

后端健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/meta
```

### 6. 安装并启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

## 跑一次完整问答链路

### 1. 登录后台

打开 `http://127.0.0.1:5173`，使用默认管理员登录：

```text
admin / admin
```

进入后台管理。

### 2. 创建知识库

进入“知识库管理”，新建一个知识库：

```text
名称：保险系统
collection：insurance
embedding 模型：选择项目已配置的 embedding provider
```

保存后确认列表中 collection 显示为 `insurance`。

### 3. 上传文档

进入“文档管理”，选择刚创建的知识库并上传文档。可以使用项目自带样例：

```text
resource/sample_data/biz/biz-ins/互联网保险系统数据安全规范.md
```

上传弹窗中建议：

```text
处理模式：切块策略
切块策略：结构感知分块
chunk size：按默认值
overlap：0
```

上传后源文件会进入对象存储，文档解析结果用于预览和后续切块。

### 4. 执行切块与索引

在文档列表中点击“切块”或“重建索引”。完成后：

- 文档状态应变为已索引或切块成功。
- 分块管理中可以看到该文档的 chunk。
- RustFS 中可以看到对应知识库 bucket 和源文件对象。

### 5. 提问

进入“对话”页面，输入：

```text
保险系统的数据安全要求有哪些？
```

预期链路：

1. 前端创建或选中会话。
2. 后端进入 LangGraph 工作流。
3. 加载会话记忆。
4. 执行问题重写与拆分。
5. 执行意图识别和知识库路由。
6. 检索 `insurance` 知识库。
7. 执行 BM25、向量召回、RRF、rerank 和 final topK。
8. LLM 基于检索上下文生成 Markdown 回答。
9. 前端展示答案、来源引用、复制、重新生成、点赞、点踩。
10. 后台 Trace 页面记录每个 RAG 阶段耗时。

### 6. 验证 Trace

进入后台“链路追踪”，搜索最新会话或 trace id。详情页应看到类似阶段：

- `chat.stream`
- `query-rewrite-and-split`
- `intent-resolve`
- `retrieval-engine`
- `multi-channel-retrieval`
- `generation.answer`

每个阶段都会展示状态、耗时、输入摘要、输出摘要和 metadata。

## 常用命令

前端构建：

```bash
cd frontend
npm run build
```

Markdown 渲染回归：

```bash
cd frontend
npm run test:markdown
```

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend -q
```

清空数据库表：

```bash
psql "postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow" -f resource/database/drop_all_tables_pg.sql
```

停止依赖服务：

```bash
docker compose -f docker-compose.services.yml down
```

## 常见问题

### 数据库导入后没有示例问题

确认已执行 `resource/database/init_data_pg.sql`，示例问题属于欢迎页推荐问法配置，不依赖具体知识库。

### 上传文档失败

优先检查：

- 后端是否启动在 `127.0.0.1:8000`。
- Tika 服务是否可访问：`http://127.0.0.1:9998`。
- RustFS 是否可访问：`http://127.0.0.1:9001`。
- `.env` 中数据库、RustFS、Tika、OCR 地址是否和 Docker 端口一致。

### 回答没有检索到知识库内容

优先检查：

- 文档是否已经完成切块或重建索引。
- 知识库 collection 是否和创建时填写一致。
- 意图节点或关键词映射是否绑定了正确知识库。
- 后台 Trace 中检索阶段是否有召回结果。

### MCP 搜索或天气不可用

优先检查：

- `.env` 中 MCP Server 配置是否启用。
- 对应 MCP Server 的 API Key 是否配置。
- 后台“模型与工具状态”中 MCP 是否健康。
- Trace 中工具调用阶段是否有错误信息。

## 文档

- [PRD](docs/PRD.md)
- [技术设计](docs/TECH_DESIGN.md)
- [AI 开发指引](docs/AGENTS.md)
- [数据库脚本说明](resource/database/README.md)

## 开发约定

- 新增接口优先补充 Pydantic schema、service 和测试。
- 新增前端功能优先放入对应 `components/<feature>` 与 `composables/<feature>`。
- 新增数据库结构需要同步更新 `schema_pg.sql` 和必要的初始化脚本。
- 新增 RAG 阶段需要记录 trace，便于后台链路追踪定位问题。
- 新增文档入库能力需要考虑源文件对象存储、解析结果、分块、索引状态和重复上传处理。
