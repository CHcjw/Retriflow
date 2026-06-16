# Backend Architecture Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 RetriFlow 后端从单一 `domain/` 杂糅结构，渐进式整理为 `modules/` + `infra/` 的 RAG / Agent 项目骨架，同时保持现有 API 行为和测试稳定。

**Architecture:** 采用“新路径实现 + 旧路径兼容代理”的方式迁移。业务能力放入 `modules/`，模型、向量库、文档解析等外部适配放入 `infra/`，第一阶段保留 `domain.*` re-export，避免一次性打断已有导入。

**Tech Stack:** Python 3.12, FastAPI, pytest, PostgreSQL/SQLite, LangChain/LangGraph, pgvector.

---

### Task 1: 创建新骨架目录和包初始化

**Files:**
- Create: `backend/src/modules/__init__.py`
- Create: `backend/src/modules/auth/__init__.py`
- Create: `backend/src/modules/session/__init__.py`
- Create: `backend/src/modules/chat/__init__.py`
- Create: `backend/src/modules/admin/__init__.py`
- Create: `backend/src/modules/knowledge/__init__.py`
- Create: `backend/src/modules/ingestion/__init__.py`
- Create: `backend/src/modules/rag/__init__.py`
- Create: `backend/src/modules/rag/retrieval/__init__.py`
- Create: `backend/src/modules/memory/__init__.py`
- Create: `backend/src/modules/mcp/__init__.py`
- Create: `backend/src/modules/observability/__init__.py`
- Create: `backend/src/infra/__init__.py`
- Create: `backend/src/infra/llm/__init__.py`
- Create: `backend/src/infra/embeddings/__init__.py`
- Create: `backend/src/infra/vector_store/__init__.py`
- Create: `backend/src/infra/document_parser/__init__.py`
- Create: `backend/src/infra/storage/__init__.py`

**Step 1: Create packages**

Add empty `__init__.py` files.

**Step 2: Run import smoke test**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend/src'); import modules, infra"
```

Expected: no output and exit code 0.

---

### Task 2: 迁移 auth 模块并保留兼容代理

**Files:**
- Create: `backend/src/modules/auth/service.py`
- Modify: `backend/src/modules/auth/__init__.py`
- Modify: `backend/src/domain/auth.py`
- Modify: `backend/src/api/routes/auth.py`
- Modify: `backend/src/api/deps/auth.py`
- Test: `backend/src/tests/retriflow_backend/test_admin_api.py`

**Step 1: Move implementation**

Move the full implementation from `domain/auth.py` to `modules/auth/service.py`.

**Step 2: Export public API**

In `modules/auth/__init__.py`:

```python
from modules.auth.service import AuthenticatedUser, RetriFlowAuthService

__all__ = ["AuthenticatedUser", "RetriFlowAuthService"]
```

**Step 3: Keep old import compatibility**

In `domain/auth.py`:

```python
from modules.auth.service import AuthenticatedUser, RetriFlowAuthService

__all__ = ["AuthenticatedUser", "RetriFlowAuthService"]
```

**Step 4: Update API imports**

Change:

```python
from domain.auth import RetriFlowAuthService
```

to:

```python
from modules.auth import RetriFlowAuthService
```

Also update `api/deps/auth.py`.

**Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_admin_api.py -q
```

Expected: pass.

---

### Task 3: 迁移 session 模块并保留兼容代理

**Files:**
- Create: `backend/src/modules/session/service.py`
- Modify: `backend/src/modules/session/__init__.py`
- Modify: `backend/src/domain/session.py`
- Modify: `backend/src/api/routes/session.py`
- Test: `backend/src/tests/retriflow_backend/test_session_api.py`

**Step 1: Move implementation**

Move implementation from `domain/session.py` to `modules/session/service.py`.

**Step 2: Export service**

In `modules/session/__init__.py`:

```python
from modules.session.service import RetriFlowSessionService

__all__ = ["RetriFlowSessionService"]
```

**Step 3: Keep old import compatibility**

In `domain/session.py`:

```python
from modules.session.service import RetriFlowSessionService

__all__ = ["RetriFlowSessionService"]
```

**Step 4: Update API import**

Update `api/routes/session.py` to import from `modules.session`.

**Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_session_api.py -q
```

Expected: pass.

---

### Task 4: 迁移 MCP 子包

**Files:**
- Create: `backend/src/modules/mcp/client.py`
- Create: `backend/src/modules/mcp/executors.py`
- Create: `backend/src/modules/mcp/models.py`
- Create: `backend/src/modules/mcp/parameter_extractor.py`
- Create: `backend/src/modules/mcp/registry.py`
- Create: `backend/src/modules/mcp/service.py`
- Modify: `backend/src/modules/mcp/__init__.py`
- Modify: `backend/src/domain/mcp/*.py`
- Test: `backend/src/tests/retriflow_backend/test_mcp_*.py`

**Step 1: Copy implementations**

Move current `domain/mcp/*` implementation into `modules/mcp/*`.

**Step 2: Update internal imports**

Change `from domain.mcp...` to `from modules.mcp...` inside new MCP files.

**Step 3: Keep compatibility proxies**

Each `domain/mcp/*.py` should re-export from `modules.mcp.*`.

**Step 4: Run MCP tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_mcp_registry.py backend/src/tests/retriflow_backend/test_mcp_service.py backend/src/tests/retriflow_backend/test_mcp_parameter_extractor.py backend/src/tests/retriflow_backend/test_mcp_remote_client.py -q
```

Expected: pass.

---

### Task 5: 迁移 infra 模型与向量存储

**Files:**
- Create: `backend/src/infra/llm/service.py`
- Create: `backend/src/infra/embeddings/service.py`
- Create: `backend/src/infra/vector_store/store.py`
- Modify: `backend/src/infra/llm/__init__.py`
- Modify: `backend/src/infra/embeddings/__init__.py`
- Modify: `backend/src/infra/vector_store/__init__.py`
- Modify: `backend/src/domain/llm.py`
- Modify: `backend/src/domain/embeddings.py`
- Modify: `backend/src/domain/vector_store.py`
- Test: `backend/src/tests/retriflow_backend/test_model_routing.py`
- Test: `backend/src/tests/retriflow_backend/test_vector_store.py`

**Step 1: Move implementations**

Move:

- `domain/llm.py` -> `infra/llm/service.py`
- `domain/embeddings.py` -> `infra/embeddings/service.py`
- `domain/vector_store.py` -> `infra/vector_store/store.py`

**Step 2: Update imports in new files**

Use:

```python
from infra.llm import RetriFlowLLMService
from infra.embeddings import RetriFlowEmbeddingService
from infra.vector_store import resolve_vector_store
```

**Step 3: Keep old compatibility proxies**

Old `domain/*.py` files re-export public classes/functions.

**Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_model_routing.py backend/src/tests/retriflow_backend/test_vector_store.py -q
```

Expected: pass.

---

### Task 6: 迁移 document parser infra

**Files:**
- Create: `backend/src/infra/document_parser/tika_client.py`
- Create: `backend/src/infra/document_parser/parser.py`
- Create: `backend/src/infra/document_parser/normalizer.py`
- Create: `backend/src/infra/document_parser/structure.py`
- Create: `backend/src/infra/document_parser/caption_enrichment.py`
- Modify: `backend/src/infra/document_parser/__init__.py`
- Modify: `backend/src/domain/tika_client.py`
- Modify: `backend/src/domain/document_parser.py`
- Modify: `backend/src/domain/document_normalizer.py`
- Modify: `backend/src/domain/document_structure.py`
- Modify: `backend/src/domain/document_caption_enrichment.py`
- Test: document parser related tests.

**Step 1: Move implementations**

Move document parser related implementations into `infra/document_parser`.

**Step 2: Update internal imports**

Use `infra.document_parser.*` for document parser internals.

**Step 3: Keep old compatibility proxies**

Old `domain/document_*` and `domain/tika_client.py` re-export from `infra.document_parser`.

**Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_tika_client.py backend/src/tests/retriflow_backend/test_document_parser.py backend/src/tests/retriflow_backend/test_document_structure.py backend/src/tests/retriflow_backend/test_document_normalizer.py backend/src/tests/retriflow_backend/test_document_caption_enrichment.py -q
```

Expected: pass.

---

### Task 7: 迁移 RAG 主链路

**Files:**
- Create: `backend/src/modules/rag/intent.py`
- Create: `backend/src/modules/rag/rewrite.py`
- Create: `backend/src/modules/rag/retrieval/engine.py`
- Create: `backend/src/modules/rag/retrieval/channels.py`
- Create: `backend/src/modules/rag/retrieval/postprocessors.py`
- Create: `backend/src/modules/rag/rerank.py`
- Create: `backend/src/modules/rag/postprocess.py`
- Create: `backend/src/modules/rag/workflow.py`
- Create: `backend/src/modules/rag/workflow_adapter.py`
- Modify: corresponding `domain/*.py` compatibility proxies.
- Test: RAG related tests.

**Step 1: Move implementations**

Move RAG files into `modules/rag`.

**Step 2: Update imports**

Update new files to use `modules.rag.*`, `modules.memory`, `modules.mcp`, and `infra.*`.

**Step 3: Keep old compatibility proxies**

Old `domain/retrieval.py`, `domain/workflow.py`, etc. re-export from new modules.

**Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_retrieval_engine.py backend/src/tests/retriflow_backend/test_reranker.py backend/src/tests/retriflow_backend/test_intent_classifier.py backend/src/tests/retriflow_backend/test_answer_postprocessor.py -q
```

Expected: pass.

---

### Task 8: 迁移 memory 模块

**Files:**
- Create: `backend/src/modules/memory/service.py`
- Modify: `backend/src/modules/memory/__init__.py`
- Modify: `backend/src/domain/memory.py`
- Test: `backend/src/tests/retriflow_backend/test_memory_service.py`

**Step 1: Move implementation**

Move `domain/memory.py` to `modules/memory/service.py`.

**Step 2: Update imports**

Use `infra.llm` for LLM dependencies.

**Step 3: Keep compatibility proxy**

`domain/memory.py` re-exports public memory classes.

**Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_memory_service.py -q
```

Expected: pass.

---

### Task 9: 迁移 chat 模块

**Files:**
- Create: `backend/src/modules/chat/service.py`
- Create: `backend/src/modules/chat/streaming.py`
- Modify: `backend/src/modules/chat/__init__.py`
- Modify: `backend/src/domain/chat.py`
- Modify: `backend/src/domain/streaming.py`
- Modify: `backend/src/api/routes/chat.py`
- Test: chat related tests.

**Step 1: Move implementations**

Move chat and streaming implementations into `modules/chat`.

**Step 2: Update imports**

Use `modules.memory`, `modules.session`, `modules.rag.workflow`.

**Step 3: Keep compatibility proxies**

Old domain files re-export services.

**Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_chat_api.py backend/src/tests/retriflow_backend/test_chat_mcp_api.py backend/src/tests/retriflow_backend/test_message_persistence_api.py -q
```

Expected: pass or only known external-model skips/fallbacks.

---

### Task 10: 迁移 ingestion 和 knowledge

**Files:**
- Create: `backend/src/modules/ingestion/service.py`
- Create: `backend/src/modules/knowledge/service.py`
- Modify: `backend/src/modules/ingestion/__init__.py`
- Modify: `backend/src/modules/knowledge/__init__.py`
- Modify: `backend/src/domain/ingestion.py`
- Modify: `backend/src/domain/knowledge.py`
- Modify: `backend/src/api/routes/ingestion.py`
- Modify: `backend/src/api/routes/knowledge.py`
- Test: ingestion and knowledge tests.

**Step 1: Move ingestion implementation**

Move `domain/ingestion.py` to `modules/ingestion/service.py`.

**Step 2: Move knowledge implementation**

Move `domain/knowledge.py` to `modules/knowledge/service.py`.

**Step 3: Update imports**

Use `infra.document_parser`, `infra.vector_store`, and `modules.ingestion`.

**Step 4: Keep compatibility proxies**

Old domain files re-export public classes.

**Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_ingestion_api.py backend/src/tests/retriflow_backend/test_ingestion_pipeline.py backend/src/tests/retriflow_backend/test_knowledge_api.py backend/src/tests/retriflow_backend/test_knowledge_document_api.py backend/src/tests/retriflow_backend/test_knowledge_route.py -q
```

Expected: pass.

---

### Task 11: 拆分 admin 大文件

**Files:**
- Create: `backend/src/modules/admin/service.py`
- Create: `backend/src/modules/admin/dashboard.py`
- Create: `backend/src/modules/admin/trace.py`
- Create: `backend/src/modules/admin/users.py`
- Create: `backend/src/modules/admin/intent.py`
- Create: `backend/src/modules/admin/keyword.py`
- Create: `backend/src/modules/admin/settings.py`
- Modify: `backend/src/modules/admin/__init__.py`
- Modify: `backend/src/domain/admin.py`
- Modify: `backend/src/api/routes/admin.py`
- Test: `backend/src/tests/retriflow_backend/test_admin_api.py`

**Step 1: Move admin implementation into facade**

Start with `modules/admin/service.py` containing the same `RetriFlowAdminService`.

**Step 2: Keep compatibility proxy**

`domain/admin.py` re-exports `RetriFlowAdminService`.

**Step 3: Split by concern**

Gradually move helper logic into dashboard/trace/users/intent/keyword/settings modules while keeping facade API stable.

**Step 4: Run admin tests after each split**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend/test_admin_api.py -q
```

Expected: pass.

---

### Task 12: 更新文档和全量回归

**Files:**
- Modify: `docx/TECH_DESIGN.md`
- Modify: `docx/AGENTS.md`
- Modify: `docx/PRD.md` if user-facing capabilities changed.

**Step 1: Update docs**

Document the new `modules/` and `infra/` structure.

**Step 2: Run backend regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/src/tests/retriflow_backend -q
```

Expected: pass or document unrelated known failures.

**Step 3: Run frontend build**

Run:

```powershell
cd frontend
cmd /c npm.cmd run build
```

Expected: build succeeds.

**Step 4: Run import smoke**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend/src'); from main import create_app; app = create_app(); print(app.title)"
```

Expected: prints app title without traceback.

---

## Notes

- Do not remove old `domain.*` imports in the same pass as moving code unless all tests are updated.
- Prefer one module migration per commit.
- If a migration reveals circular imports, move the lower-level dependency toward `infra/` rather than importing `modules` from `infra`.
- Keep public class names unchanged during this refactor.
