# RetriFlow PostgreSQL Scripts

## 执行顺序

1. `schema_pg.sql`
2. `init_data_pg.sql`



1. `drop_all_tables_pg.spg.sql`

## 每个脚本的作用

- `schema_pg.sql`

  - 初始化当前版本完整表结构
  - 适合全新空数据库
- `init_data_pg.sql`

  - 插入演示管理员、演示会话、演示知识库、演示文档与入库任务
  - 不是须脚本
- `drop_all_tables_pg.spg.sql`

  - 删除数据库表
