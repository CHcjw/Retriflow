# RetriFlow 本地依赖服务说明

## 当前运行模式

- `backend`：本机运行
- `frontend`：本机运行
- `tika`：Docker 运行
- `ocr`：Docker 运行
- `postgresql + pgvector`：Docker 运行

## 启动本地依赖服务

在项目根目录执行：

```powershell
docker compose -f .\docker-compose.services.yml up -d
```

当前会启动以下容器：

- `retriflow-pgvector`
- `retriflow-tika`
- `retriflow-ocr`

查看状态：

```powershell
docker compose -f .\docker-compose.services.yml ps
```

停止服务：

```powershell
docker compose -f .\docker-compose.services.yml down
```

重建并启动：

```powershell
docker compose -f .\docker-compose.services.yml up -d --build
```

## PostgreSQL 连接信息

可以直接用 DBeaver、DataGrip、Navicat、pgAdmin 连接：

- Host: `127.0.0.1`
- Port: `5433`
- Database: `retriflow`
- Username: `retriflow`
- Password: `retriflow`
- Schema: `public`

## 当前数据库架构

RetriFlow 现在默认采用：

- PostgreSQL 作为业务主库
- pgvector 作为同库内的向量存储层

也就是说，这些数据现在都在同一个 PostgreSQL 库里：

- 会话 `sessions`
- 会话消息 `conversation_messages`
- 知识库 `knowledge_bases`
- 文档 `knowledge_documents`
- 分块 `knowledge_chunks`
- 结构化块 `knowledge_document_blocks`
- 表格单元格 `knowledge_document_table_cells`
- 入库任务 `ingestion_tasks`
- 入库节点 `ingestion_task_nodes`
- 向量表 `retriflow_chunk_vectors`

`SQLite` 现在只保留为兼容模式和测试隔离用途，不再是默认业务主库。

## 你现在真正要用的 SQL 脚本

只保留这 3 个主入口：

- `tools/postgres/schema_pg.sql`
- `tools/postgres/init_data_pg.sql`
- `tools/postgres/inspect_pg.sql`

如果你想看一步一步的 GUI 操作说明，直接看：

- `docs/database-init-guide.md`

它们分别用于：

- `schema_pg.sql`
  - 初始化 PostgreSQL 业务表和向量表结构
- `init_data_pg.sql`
  - 插入 demo 种子数据
- `inspect_pg.sql`
  - 在 GUI 客户端里巡检业务表和向量表状态

## 初始化顺序

### 1. 建表

先执行：

- `tools/postgres/schema_pg.sql`

### 2. 初始化数据

再执行：

- `tools/postgres/init_data_pg.sql`

### 3. 巡检

最后如果你想确认是否成功，执行：

- `tools/postgres/inspect_pg.sql`

## 向量表说明

`retriflow_chunk_vectors` 不再由 `schema_pg.sql` 手动创建。

原因是为了兼容 HeidiSQL 这类对 `DO $$` 执行不稳定的客户端。

现在统一改为：

- 业务表由 `schema_pg.sql` 创建
- 向量表由后端在首次成功写入 embedding 时自动创建
- 向量维度由运行时模型真实返回值决定

## 建议的 GUI 查看路径

连接后建议重点看这些表：

- `public.sessions`
- `public.conversation_messages`
- `public.knowledge_bases`
- `public.knowledge_documents`
- `public.knowledge_chunks`
- `public.knowledge_document_blocks`
- `public.knowledge_document_table_cells`
- `public.ingestion_tasks`
- `public.ingestion_task_nodes`
- `public.retriflow_chunk_vectors`

如果你想快速确认向量写入是否成功，优先执行：

```sql
SELECT
    document_title,
    COUNT(*) AS chunk_vector_count
FROM retriflow_chunk_vectors
GROUP BY document_title
ORDER BY chunk_vector_count DESC, document_title ASC;
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

## 本地 `.env` 关键配置

```env
RETRIFLOW_DATABASE_BACKEND=pg
RETRIFLOW_DATABASE_DSN=postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow
RETRIFLOW_DATABASE_SCHEMA=public

RETRIFLOW_VECTOR_STORE_TYPE=pg
RETRIFLOW_PGVECTOR_DSN=postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow
RETRIFLOW_PGVECTOR_TABLE=retriflow_chunk_vectors

RETRIFLOW_TIKA_ENABLED=true
RETRIFLOW_TIKA_ENDPOINT=http://127.0.0.1:9998

RETRIFLOW_TIKA_OCR_ENABLED=true
RETRIFLOW_TIKA_OCR_SERVICE_ENDPOINT=http://127.0.0.1:9889
```

## 启动后端

```powershell
& .\.venv\Scripts\python.exe .\backend\src\main.py
```

## 启动前端

```powershell
cd .\frontend
cmd /c npm run dev
```
