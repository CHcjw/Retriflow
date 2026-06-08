# RetriFlow 本地依赖服务说明

## 当前运行方式

- `backend`：本机运行
- `frontend`：本机运行
- `tika`：Docker 运行
- `ocr`：Docker 运行
- `postgresql + pgvector`：Docker 运行

## 启动依赖服务

在项目根目录执行：

```powershell
docker compose -f .\docker-compose.services.yml up -d
```

查看状态：

```powershell
docker compose -f .\docker-compose.services.yml ps
```

停止服务：

```powershell
docker compose -f .\docker-compose.services.yml down
```

## PostgreSQL 连接信息

- Host: `127.0.0.1`
- Port: `5433`
- Database: `retriflow`
- Username: `retriflow`
- Password: `retriflow`
- Schema: `public`

## SQL 脚本入口

主要使用这 3 个脚本：

- `tools/postgres/schema_pg.sql`
- `tools/postgres/init_data_pg.sql`
- `tools/postgres/inspect_pg.sql`

推荐顺序：

1. 执行 `schema_pg.sql`
2. 执行 `init_data_pg.sql`
3. 执行 `inspect_pg.sql`

## 当前数据库结构

业务数据和向量数据都在 PostgreSQL 中：

- `sessions`
- `conversation_messages`
- `knowledge_bases`
- `knowledge_documents`
- `knowledge_chunks`
- `knowledge_document_blocks`
- `knowledge_document_table_cells`
- `ingestion_tasks`
- `ingestion_task_nodes`
- `retriflow_chunk_vectors`

## 后端启动

```powershell
& .\.venv\Scripts\python.exe .\backend\src\main.py
```

## 前端启动

```powershell
cd .\frontend
cmd /c npm run dev
```

## 健康检查

### PostgreSQL + pgvector

```powershell
docker ps --filter "name=retriflow-pgvector"
```

### Tika

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9998/tika
```

### OCR

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9889/healthz
```

## 当前 RAG 检索链路

- BM25 Top80
- 向量 Top80
- RRF Top50
- rerank Top10
- 最终返回 Top5

首页聊天不要求先选知识库，后端会先做知识库意图路由，再决定限定检索还是全局检索。
