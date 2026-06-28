# RetriFlow

RetriFlow 是一个从零构建的企业级 Agentic RAG 系统。项目使用 Python + FastAPI + Vue 3 + TypeScript，提供文档解析、结构化入库、智能分块、向量化、混合检索、意图识别、问题重写、MCP 工具调用、多轮记忆、流式回答、来源引用、链路追踪和后台运营管理能力。

## 功能概览

- 首页直接对话：无需用户先选择知识库，后端自动完成意图识别、知识库路由、工具路由和答案生成。
- 企业知识库：支持知识库、文档、分块、路由画像、示例问题和关键词配置。
- 文档入库：支持 Tika 解析、结构化块、表格、图片说明、OCR 降级、重复文件判重和对象存储。
- 检索增强：支持 BM25、向量召回、RRF、rerank、final topK 和来源引用。
- MCP 工具：支持内置工具、远程 MCP Server、天气查询、联网搜索和节点级 trace。
- 多轮记忆：支持短期摘要、中期记忆、长期记忆和后台诊断。
- LangGraph 编排：聊天主链路通过真实 `StateGraph` 执行，非流式和流式准备阶段分别编译 graph。
- LangSmith 观测：可选开启外部 tracing，默认不影响本地运行。
- 后台管理：Dashboard、用户、知识库、文档、分块、流水线、意图树、关键词、示例问题、模型健康、Trace 和系统设置。
- 可观测链路：完整记录 RAG 每个阶段的耗时、输入摘要、输出摘要、错误和 metadata。

## 项目结构

```text
RetriFlow/
  backend/                 # FastAPI 后端
  frontend/                # Vue 3 前端
  docs/                    # PRD、技术设计、AI 开发指引
  resource/database/       # PostgreSQL schema、初始化和清库脚本
  resource/sample_data/    # 样例知识文档
  tools/                   # Tika、OCR 等辅助服务
  docker-compose.services.yml
```

## 环境要求

- Python 3.12+
- Node.js 20+
- Docker Desktop
- PostgreSQL 客户端工具，任选其一：HeidiSQL、psql、DataGrip 等

可选：

- LM Studio、Ollama、DashScope/百炼、SiliconFlow 等 OpenAI-compatible 模型服务
- RustFS/S3 对象存储，项目 docker compose 已提供 RustFS

## 1. 克隆项目

```bash
git clone <your-retriflow-repo-url>
cd RetriFlow
```

## 2. 启动依赖服务

项目提供 PostgreSQL + pgvector、Redis、RustFS、Tika、OCR 的本地 Docker 服务。

```bash
docker compose -f docker-compose.services.yml up -d
```

服务端口：

- PostgreSQL/pgvector：`localhost:5433`
- Redis：`localhost:6379`
- RustFS API：`http://localhost:9000`
- RustFS Console：`http://localhost:9001`
- Tika：`http://localhost:9998`
- OCR：`http://localhost:9889`

PostgreSQL 默认连接：

```text
host=127.0.0.1
port=5433
database=retriflow
user=retriflow
password=retriflow
```

## 3. 初始化数据库

全新数据库按以下顺序执行：

1. `resource/database/schema_pg.sql`
2. `resource/database/init_data_pg.sql`

可以用 HeidiSQL 打开脚本后直接执行，也可以用 `psql`：

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

## 4. 配置环境变量

复制环境变量模板：

```powershell
Copy-Item .env.example .env
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

需要接入 LangSmith 时，在 `.env` 中设置 `LANGSMITH_TRACING=true`、`LANGSMITH_PROJECT=<你的项目名>` 和 `LANGSMITH_API_KEY=<你的 key>`。不开启时，RetriFlow 仍使用后台“链路追踪”记录完整 RAG 节点耗时。

## 5. 安装并启动后端

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

## 6. 安装并启动前端

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

## 7. 跑一次完整问答链路

### 7.1 登录后台

打开 `http://127.0.0.1:5173`，使用默认管理员登录：

```text
admin / admin
```

进入后台管理。

### 7.2 创建知识库

进入“知识库管理”，新建一个知识库：

```text
名称：保险系统
collection：insurance
embedding 模型：选择项目已配置的 embedding provider
```

保存后确认列表中 collection 显示为 `insurance`。

### 7.3 上传文档

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

### 7.4 执行切块与索引

在文档列表中点击“切块”或“重建索引”。完成后：

- 文档状态应变为已索引或切块成功。
- 分块管理中可以看到该文档的 chunk。
- RustFS 中可以看到对应知识库 bucket 和源文件对象。

### 7.5 提问

进入“对话”页面，输入：

```text
保险系统的数据安全要求有哪些？
```

预期链路：

1. 前端创建或选中会话。
2. 后端进入 LangGraph 工作流，先加载会话记忆，再执行问题重写、意图识别和知识库路由。
3. 检索 `insurance` 知识库。
4. 执行 BM25、向量召回、RRF、rerank 和 final topK。
5. LLM 基于检索上下文生成 Markdown 回答。
6. 页面展示答案、来源引用、复制/重新生成/点赞/点踩操作。
7. 后台 Trace 页面可以查看每个 RAG 阶段耗时。

### 7.6 验证 Trace

进入后台“链路追踪”，搜索最新会话或 trace id。详情页应看到类似阶段：

- `chat.stream`
- `query-rewrite-and-split`
- `intent-resolve`
- `retrieval-engine`
- `multi-channel-retrieval`
- `generation.answer`

每个阶段都应展示真实耗时、状态、输入摘要和输出摘要。

## 常用命令

前端构建：

```bash
cd frontend
npm run build
```

Markdown 回归：

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

## 文档

- [PRD](docs/PRD.md)
- [技术设计](docs/TECH_DESIGN.md)
- [AI 开发指引](docs/AGENTS.md)
- [数据库脚本说明](resource/database/README.md)

## 说明

RetriFlow 的目标不是演示一个最小 RAG Demo，而是提供一条可维护、可观测、可配置、可扩展的企业级 RAG 工程链路。新增功能应优先保持真实后端支撑、清晰模块边界和可回归测试。
