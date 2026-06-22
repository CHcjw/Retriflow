# RetriFlow ragent Gap Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the remaining ragent-aligned RetriFlow gaps except Milvus.

**Architecture:** Add one vertical capability at a time. Preserve existing RetriFlow APIs unless a new endpoint is needed. Use ragent behavior as a reference, but translate it to the current FastAPI, SQLite/PostgreSQL, and Vue 3 structure.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite/PostgreSQL compatibility, Vue 3 Composition API, TypeScript, Vite.

---

### Task 1: User Management Completion

**Files:**
- Modify: `backend/src/schemas/admin.py`
- Modify: `backend/src/api/routes/admin.py`
- Modify: `backend/src/modules/admin/service.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/composables/useRetriFlowAdmin.ts`
- Modify: `frontend/src/views/AdminView.vue`
- Test: `backend/src/tests/retriflow_backend/test_admin_api.py`

**Step 1:** Add failing tests for admin updating username/avatar/role, deleting a user, changing own password, and paginating/filtering users.

**Step 2:** Add request/response schemas for user update, password change, and paginated user list.

**Step 3:** Add admin routes for user update/delete and current-user password change.

**Step 4:** Implement service methods with password hashing, duplicate username checks, and admin protection rules.

**Step 5:** Update frontend API/composable/admin user modal to edit/delete/change password and keep table pagination at 10 rows.

**Step 6:** Run targeted admin tests and frontend build.

### Task 2: Document Preview and Source File Access

**Files:**
- Modify: `backend/src/api/routes/knowledge.py`
- Modify: `backend/src/modules/knowledge/service.py`
- Modify: `backend/src/schemas/knowledge.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/views/AdminView.vue`
- Test: `backend/src/tests/retriflow_backend/test_knowledge_document_api.py`

**Step 1:** Add failing tests for previewing parsed markdown/text and streaming the original uploaded source file through storage.

**Step 2:** Add service methods to resolve document by id and open `source_uri` through storage.

**Step 3:** Add preview and file endpoints with content type and safe filename headers.

**Step 4:** Add compact document actions in admin UI for preview/file access.

**Step 5:** Run document API tests and frontend build.

### Task 3: Document Chunk Logs

**Files:**
- Modify: `backend/src/core/state.py`
- Modify: `tools/postgres/schema_pg.sql`
- Modify: `tools/postgres/init_data_pg.sql`
- Modify: `backend/src/schemas/knowledge.py`
- Modify: `backend/src/modules/knowledge/service.py`
- Modify: `backend/src/api/routes/knowledge.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/views/AdminView.vue`
- Test: `backend/src/tests/retriflow_backend/test_knowledge_document_api.py`

**Step 1:** Add failing tests asserting upload/reindex writes a chunk log with phase durations, status, chunk count, and error message on failure.

**Step 2:** Add SQLite/Postgres schema for `knowledge_document_chunk_logs`.

**Step 3:** Instrument ingestion/reindex around extraction, chunking, embedding, and persistence.

**Step 4:** Add paginated chunk-log endpoint.

**Step 5:** Add backend admin/document UI section to view recent logs.

**Step 6:** Run targeted tests and frontend build.

### Task 4: Document Schedule Refresh

**Files:**
- Modify: `backend/src/core/state.py`
- Modify: `tools/postgres/schema_pg.sql`
- Modify: `backend/src/core/config.py`
- Create: `backend/src/modules/knowledge/schedule.py`
- Modify: `backend/src/modules/knowledge/service.py`
- Modify: `backend/src/api/routes/knowledge.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/views/AdminView.vue`
- Test: `backend/src/tests/retriflow_backend/test_knowledge_schedule.py`

**Step 1:** Add failing tests for creating/updating a document schedule, detecting unchanged HTTP metadata, recording execution, and reindexing changed content.

**Step 2:** Add schedule and schedule execution tables.

**Step 3:** Implement cron/interval validation, lock acquisition, execution recording, and stuck-running recovery.

**Step 4:** Implement local/HTTP source refresh without S3 dependency.

**Step 5:** Add admin UI controls for schedule enablement and execution history.

**Step 6:** Run schedule tests and frontend build.

### Task 5: Trace Run Table

**Files:**
- Modify: `backend/src/core/state.py`
- Modify: `tools/postgres/schema_pg.sql`
- Modify: `backend/src/modules/rag/trace.py`
- Modify: `backend/src/modules/admin/service.py`
- Modify: `backend/src/schemas/admin.py`
- Test: `backend/src/tests/retriflow_backend/test_rag_trace.py`
- Test: `backend/src/tests/retriflow_backend/test_admin_api.py`

**Step 1:** Add failing tests that root span writes a run row and node rows, updates run status/duration/error on exit, and admin list can read run rows.

**Step 2:** Add `rag_trace_runs` schema and indexes.

**Step 3:** Update trace service root lifecycle to write/update run rows.

**Step 4:** Update admin trace listing/detail to prefer run table and remain compatible with existing node-only data.

**Step 5:** Run trace/admin tests.

### Task 6: RAG Evaluation Endpoint

**Files:**
- Create: `backend/src/schemas/eval.py`
- Create: `backend/src/api/routes/eval.py`
- Modify: `backend/src/api/router.py`
- Create: `backend/src/modules/rag/eval.py`
- Test: `backend/src/tests/retriflow_backend/test_rag_eval_api.py`

**Step 1:** Add failing tests for an eval endpoint returning rewrite output, route/intent metadata, retrieved chunk ids/docs/context snippets, MCP context flags, and latency.

**Step 2:** Implement eval service by reusing rewrite, routing/intent, MCP, and retrieval services.

**Step 3:** Register route behind an explicit config flag defaulting to disabled unless tests enable it.

**Step 4:** Run eval tests and affected chat/retrieval tests.

### Task 7: Dashboard Metric Split

**Files:**
- Modify: `backend/src/schemas/admin.py`
- Modify: `backend/src/modules/admin/service.py`
- Modify: `backend/src/api/routes/admin.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/components/admin/AdminDashboardPanel.vue`
- Test: `backend/src/tests/retriflow_backend/test_admin_api.py`

**Step 1:** Add failing tests for overview, performance, and trends metric endpoints.

**Step 2:** Split admin dashboard service methods while preserving existing dashboard response where used.

**Step 3:** Update frontend dashboard panel to consume richer data without adding decorative UI.

**Step 4:** Run admin tests and frontend build.

### Task 8: Lightweight MCP Server

**Files:**
- Create: `backend/src/mcp_server.py`
- Create: `backend/src/modules/mcp/server.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/src/tests/retriflow_backend/test_mcp_server.py`

**Step 1:** Add failing tests that the server lists Weather/Sales/Ticket tools and can call one tool using the existing executor contract.

**Step 2:** Implement a lightweight MCP-compatible JSON-RPC surface using current `RetriFlowMcpRegistry`.

**Step 3:** Add an entrypoint command or documented module invocation.

**Step 4:** Run MCP server tests.

### Task 9: Admin Frontend Decomposition

**Files:**
- Create: `frontend/src/components/admin/AdminKnowledgePanel.vue`
- Create: `frontend/src/components/admin/AdminDocumentsPanel.vue`
- Create: `frontend/src/components/admin/AdminChunksPanel.vue`
- Create: `frontend/src/components/admin/AdminIntentPanel.vue`
- Create: `frontend/src/components/admin/AdminKeywordPanel.vue`
- Create: `frontend/src/components/admin/AdminPipelinePanel.vue`
- Create: `frontend/src/components/admin/AdminUsersPanel.vue`
- Create: `frontend/src/components/admin/AdminSettingsPanel.vue`
- Modify: `frontend/src/views/AdminView.vue`
- Test: frontend build

**Step 1:** Move one panel at a time from `AdminView.vue` into focused components with props/events.

**Step 2:** Keep behavior and visual layout unchanged while reducing `AdminView.vue` responsibility.

**Step 3:** Run `cmd /c npm.cmd run build` after each group.

### Task 10: Documentation and Final Verification

**Files:**
- Modify: `docx/AGENTS.md`
- Modify: `docx/PRD.md`
- Modify: `docx/TECH_DESIGN.md`
- Modify: `progress.md`

**Step 1:** Add final implemented state under existing docx headings only.

**Step 2:** Run targeted backend tests from all tasks.

**Step 3:** Run frontend build.

**Step 4:** Record results in `progress.md`.

