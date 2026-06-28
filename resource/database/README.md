# RetriFlow PostgreSQL Scripts

## 执行顺序

1. `schema_pg.sql`
2. `init_data_pg.sql`
3. 在前端创建需要绑定的知识库，例如发票知识库使用 `collection_name = finance`
4. `init_intent_nodes_pg.sql`

## 脚本说明

- `schema_pg.sql`：初始化当前版本完整表结构，适合全新空数据库。
- `init_data_pg.sql`：初始化管理员、流水线、关键词映射和欢迎页示例问题，不初始化知识库和意图节点。
- `init_intent_nodes_pg.sql`：初始化意图树节点。建议在知识库创建完成后执行，这样发票节点可以自动绑定 `finance` collection 对应的知识库。
- `drop_all_tables_pg.sql`：删除数据库表。
