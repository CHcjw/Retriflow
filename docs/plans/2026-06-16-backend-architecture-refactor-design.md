# RetriFlow Backend Architecture Refactor Design

## 背景

当前 `backend/src/domain/` 已经承载了认证、会话、聊天、文档解析、入库、知识库、检索、模型、记忆、MCP、后台管理、工作流等几乎全部业务逻辑。随着 RAG 链路、后台配置和可观测能力继续扩展，单层 `domain` 会导致文件变大、依赖方向混乱、测试定位困难和后续拆分成本升高。

本次重构目标不是改变业务行为，而是优化项目骨架，使 RetriFlow 更接近可持续演进的 RAG / Agent 项目结构。

## 参考

本地 `ragent` 项目的后端结构按能力拆分为：

- `admin`
- `core`
- `ingestion`
- `knowledge`
- `rag`
- `user`
- `infra-ai`

其中 `rag/core` 继续细分为 `intent`、`memory`、`prompt`、`retrieve`、`rewrite`、`vector`、`mcp` 等。GitHub 上常见 FastAPI + LangGraph + RAG 模板也倾向把 API、业务模块、模型/向量库/外部服务适配分开。

## 设计目标

- 让业务模块按领域聚合，而不是所有文件堆在 `domain/`。
- 明确区分应用业务能力与基础设施适配。
- 保留现有功能行为和 API 响应不变。
- 采用渐进式迁移，避免一次性修改所有 import 导致大范围故障。
- 第一阶段保留 `domain.*` 兼容导入，降低测试和已有代码迁移风险。
- 更新文档和测试，保证重构可回归。

## 推荐结构

```text
backend/src/
|-- api/
|   |-- deps/
|   `-- routes/
|-- core/
|-- modules/
|   |-- auth/
|   |-- session/
|   |-- chat/
|   |-- admin/
|   |-- knowledge/
|   |-- ingestion/
|   |-- rag/
|   |-- memory/
|   |-- mcp/
|   `-- observability/
|-- infra/
|   |-- llm/
|   |-- embeddings/
|   |-- vector_store/
|   |-- document_parser/
|   `-- storage/
|-- schemas/
`-- tests/
```

## 模块职责

### `modules/auth`

负责用户注册、登录、Token、当前用户、角色判断。

迁移来源：

- `domain/auth.py`

### `modules/session`

负责会话创建、会话列表、会话删除、消息读取、owner 权限。

迁移来源：

- `domain/session.py`

### `modules/chat`

负责聊天入口、流式输出、消息持久化、会话记忆更新触发。

迁移来源：

- `domain/chat.py`
- `domain/streaming.py`

### `modules/admin`

负责后台业务能力。后续应继续拆分为：

- `dashboard.py`
- `trace.py`
- `users.py`
- `intent.py`
- `keyword.py`
- `settings.py`

迁移来源：

- `domain/admin.py`

### `modules/knowledge`

负责知识库、文档、chunk、route profile、样例导入。

后续应继续拆分为：

- `knowledge_base_service.py`
- `document_service.py`
- `chunk_service.py`
- `route_profile_service.py`

迁移来源：

- `domain/knowledge.py`
- `domain/knowledge_route.py` 中偏知识库画像的部分

### `modules/ingestion`

负责文档入库、解析编排、分块、重建索引、流水线任务记录。

后续可继续细分为：

- `pipeline.py`
- `task_service.py`
- `chunking.py`
- `reindex.py`

迁移来源：

- `domain/ingestion.py`

### `modules/rag`

负责 RAG 主链路和 Agent 工作流。

建议子结构：

```text
modules/rag/
|-- intent.py
|-- rewrite.py
|-- retrieval/
|   |-- engine.py
|   |-- channels.py
|   `-- postprocessors.py
|-- rerank.py
|-- prompt.py
|-- postprocess.py
|-- workflow.py
`-- workflow_adapter.py
```

迁移来源：

- `domain/intent_classifier.py`
- `domain/query_rewrite.py`
- `domain/retrieval.py`
- `domain/retrieval_channels.py`
- `domain/retrieval_postprocessors.py`
- `domain/reranker.py`
- `domain/answer_postprocessor.py`
- `domain/workflow.py`
- `domain/workflow_adapter.py`

### `modules/memory`

负责短期、中期、长期记忆。

迁移来源：

- `domain/memory.py`

### `modules/mcp`

负责 MCP 工具注册、参数提取、远程客户端、执行编排。

迁移来源：

- `domain/mcp/*`

### `modules/observability`

负责链路追踪、耗时聚合、未来 LangSmith / trace event 扩展。

第一阶段可以只作为预留目录；现有 trace 仍在 `modules/admin/trace.py` 或兼容 `admin.py` 中。

### `infra/llm`

负责 LLM provider、OpenAI-compatible 调用、Ollama 调用、JSON 提取等。

迁移来源：

- `domain/llm.py`

### `infra/embeddings`

负责 embedding 调用。

迁移来源：

- `domain/embeddings.py`

### `infra/vector_store`

负责 pgvector / memory vector store 适配。

迁移来源：

- `domain/vector_store.py`

### `infra/document_parser`

负责 Tika、OCR、文档结构提取、标准化、图片说明增强。

迁移来源：

- `domain/tika_client.py`
- `domain/document_parser.py`
- `domain/document_structure.py`
- `domain/document_normalizer.py`
- `domain/document_caption_enrichment.py`

## 兼容策略

第一阶段采用“新路径为主、旧路径代理”的方式：

```python
# backend/src/domain/auth.py
from modules.auth.service import AuthenticatedUser, RetriFlowAuthService

__all__ = ["AuthenticatedUser", "RetriFlowAuthService"]
```

这样已有测试中 `from domain.auth import RetriFlowAuthService` 仍可工作，API 层可以逐步切换到 `modules.*`。

## 迁移顺序

1. 创建 `modules/` 和 `infra/` 目录骨架。
2. 迁移低耦合模块：auth、session。
3. 迁移 MCP 子包。
4. 迁移 infra：llm、embeddings、vector_store、document_parser。
5. 迁移 RAG 主链路：intent、rewrite、retrieval、rerank、postprocess、workflow。
6. 迁移 chat 和 streaming。
7. 迁移 ingestion。
8. 迁移 knowledge。
9. 拆分 admin 大文件。
10. 更新文档和测试导入。
11. 逐步删除旧 `domain` 兼容代理。

## 风险与应对

- 风险：import 路径改错导致启动失败。
  - 应对：每批迁移后运行相关 pytest 和 `main.py` import 检查。

- 风险：循环依赖暴露。
  - 应对：基础设施服务放 `infra`，业务服务放 `modules`，避免 `infra` 反向依赖 `modules`。

- 风险：一次性迁移太多导致难以定位问题。
  - 应对：按模块分批迁移，每批提交和回归。

- 风险：测试仍依赖旧路径。
  - 应对：第一阶段保留 `domain.*` 兼容代理。

## 验收标准

- 后端应用可正常启动。
- 现有 API 路径不变。
- 关键测试通过。
- 前端构建不受影响。
- 文档同步更新。
- `domain/` 不再承载主要实现代码，而是逐步变为兼容层。
