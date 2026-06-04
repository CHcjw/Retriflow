# RetriFlow 数据库初始化指南

## 适用范围

这份指南用于本地初始化 RetriFlow 的 PostgreSQL 主库。

只需要使用这 3 个 SQL 脚本：

- `tools/postgres/schema_pg.sql`
- `tools/postgres/init_data_pg.sql`
- `tools/postgres/inspect_pg.sql`

## 连接信息

在 DBeaver、DataGrip、Navicat、pgAdmin 中使用以下配置连接：

- Host: `127.0.0.1`
- Port: `5433`
- Database: `retriflow`
- Username: `retriflow`
- Password: `retriflow`
- Schema: `public`

## 初始化步骤

### 1. 启动数据库容器

在项目根目录执行：

```powershell
docker compose -f .\docker-compose.services.yml up -d
```

### 2. 打开 SQL 编辑器

连接到 `retriflow` 数据库后，新建一个 SQL Console / 查询窗口。

### 3. 执行建表脚本

执行：

- `tools/postgres/schema_pg.sql`

这一步会创建业务表结构。

### 4. 执行初始化数据脚本

执行：

- `tools/postgres/init_data_pg.sql`

这一步会写入 demo 数据，例如：

- `session-demo-1`
- `kb-demo-1`

### 5. 执行巡检脚本

执行：

- `tools/postgres/inspect_pg.sql`

如果结果正常，你应该能看到：

- 业务表列表
- 各表行数
- demo 会话和 demo 知识库数据

### 6. 让后端自动创建向量表

启动后端后，真正执行一次知识库入库或文档上传，后端会按当前 embedding 模型的真实维度自动创建：

- `retriflow_chunk_vectors`

## DBeaver 具体操作

### 新建连接

1. 点击 `Database` -> `New Database Connection`
2. 选择 `PostgreSQL`
3. 填入上面的连接信息
4. 点击 `Test Connection`
5. 成功后点击 `Finish`

### 执行脚本

1. 右键连接后的数据库
2. 选择 `SQL Editor` -> `Open SQL Console`
3. 依次打开并执行：
   - `schema_pg.sql`
   - `init_data_pg.sql`
   - `inspect_pg.sql`

## 初始化成功后重点查看

左侧表列表里重点看：

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

## 常见问题

### 看不到向量表

这是正常的，只跑完 `schema_pg.sql` 和 `init_data_pg.sql` 时，向量表还不会出现。

需要你：

1. 启动后端
2. 真正执行一次知识库入库或上传文档

之后后端会自动创建 `retriflow_chunk_vectors`。

### 已经建过错误维度的向量表

删除旧的 `retriflow_chunk_vectors` 后，重新执行一次真实入库：

1. 启动后端
2. 上传文档或新建知识库文档

### 后端启动了但数据没进 PostgreSQL

优先检查：

- Docker 中 `retriflow-pgvector` 是否真的在运行
- `.env` 中是否是：

```env
RETRIFLOW_DATABASE_BACKEND=pg
RETRIFLOW_DATABASE_DSN=postgresql://retriflow:retriflow@127.0.0.1:5433/retriflow
```
