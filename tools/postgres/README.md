# RetriFlow PostgreSQL Scripts

## 执行顺序

如果你是新建空库：

1. `tools/postgres/schema_pg.sql`
2. `tools/postgres/init_data_pg.sql`
3. `tools/postgres/inspect_pg.sql` 仅用于检查

如果你是已有旧库升级：

1. `tools/postgres/migrate_legacy_pg.sql`
2. `tools/postgres/init_data_pg.sql`
3. `tools/postgres/inspect_pg.sql` 仅用于检查

## 每个脚本的作用

- `schema_pg.sql`
  - 初始化当前版本完整表结构
  - 适合全新空数据库

- `migrate_legacy_pg.sql`
  - 给旧版本数据库补字段、补新表、补索引
  - 可重复执行

- `init_data_pg.sql`
  - 插入演示管理员、演示会话、演示知识库、演示文档与入库任务
  - 不是必须脚本

- `inspect_pg.sql`
  - 查看当前表、数据量、文档向量状态、记忆表状态
  - 不会修改数据

## 常见问题

### 1. 运行 `init_data_pg.sql` 报字段不存在

说明你当前不是新空库，而是旧库。

先执行：

```sql
\i tools/postgres/migrate_legacy_pg.sql
```

或者在 GUI 工具里直接运行 `migrate_legacy_pg.sql`，再执行 `init_data_pg.sql`。

### 2. 后端页面打开时报 500，提示某个列不存在

这通常也是旧库结构落后导致的。除了后端启动时会做一部分兼容迁移，建议仍然手工执行一次：

- `tools/postgres/migrate_legacy_pg.sql`

这样数据库结构会和当前代码保持一致。
