# RetriFlow Phase 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade RetriFlow from a single-path retrieval skeleton to a `ragent`-inspired ingestion and retrieval architecture with task node logs, multi-channel retrieval, and a LangGraph-ready chat orchestration layer.

**Architecture:** Keep the current `backend/src` and `frontend` layout, but introduce a light version of `ragent`'s ingestion and retrieval boundaries. Ingestion will record per-node execution logs for the default pipeline, retrieval will be split into channels plus post-processors, and chat orchestration will call into a dedicated workflow layer so LangGraph can replace the placeholder implementation incrementally.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, Vue 3, TypeScript, Vite, LangChain/LangGraph-ready abstractions

---

### Task 1: Add Ingestion Task Node Logs

**Files:**
- Modify: `backend/src/core/state.py`
- Modify: `backend/src/schemas/knowledge.py`
- Modify: `backend/src/domain/knowledge.py`
- Modify: `backend/src/domain/ingestion.py`
- Modify: `backend/src/api/routes/ingestion.py`
- Create: `backend/src/tests/retriflow_backend/test_ingestion_api.py`

**Step 1: Write the failing test**

Add tests asserting that creating a document records node-level ingestion logs for the default pipeline stages such as `normalize`, `chunk`, and `index`.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_ingestion_api.py -v`
Expected: FAIL because task node logs do not exist yet.

**Step 3: Write minimal implementation**

Add an `ingestion_task_nodes` table, persist node execution rows during document ingestion, and expose a task-node query endpoint.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_ingestion_api.py -v`
Expected: PASS.

### Task 2: Add Multi-Channel Retrieval Engine

**Files:**
- Create: `backend/src/domain/retrieval.py`
- Create: `backend/src/domain/retrieval_channels.py`
- Create: `backend/src/domain/retrieval_postprocessors.py`
- Modify: `backend/src/domain/chat.py`
- Modify: `backend/src/tests/retriflow_backend/test_chat_api.py`

**Step 1: Write the failing test**

Add tests asserting retrieval combines more than one search strategy and returns deduplicated, sorted sources.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_chat_api.py -v`
Expected: FAIL because retrieval is still a single inline query path.

**Step 3: Write minimal implementation**

Extract a retrieval engine that runs at least two channels, merges results, and applies post-processing.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_chat_api.py -v`
Expected: PASS.

### Task 3: Add LangGraph-Ready Workflow Layer

**Files:**
- Create: `backend/src/domain/workflow.py`
- Modify: `backend/src/domain/chat.py`
- Modify: `backend/src/schemas/chat.py`
- Modify: `docx/TECH_DESIGN.md`

**Step 1: Write the failing test**

Add tests asserting chat responses carry workflow metadata describing the retrieval phase and current workflow name.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_chat_api.py -v`
Expected: FAIL because workflow metadata is not returned.

**Step 3: Write minimal implementation**

Introduce a workflow service that orchestrates retrieval and answer assembly, and return metadata that can later map to a real LangGraph graph.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_chat_api.py -v`
Expected: PASS.

### Task 4: Upgrade Frontend Admin and Chat Views

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/composables/useRetriFlowAdmin.ts`
- Modify: `frontend/src/composables/useRetriFlowChat.ts`
- Modify: `frontend/src/views/AdminView.vue`
- Modify: `frontend/src/views/ChatView.vue`
- Modify: `frontend/src/assets/main.css`

**Step 1: Define failing verification**

The admin view should surface ingestion task node logs and the chat view should show retrieval workflow metadata and grouped sources.

**Step 2: Run build to verify missing UI state**

Run: `cmd /c npm run build`
Expected: current build passes, but UI features are not present yet.

**Step 3: Write minimal implementation**

Expose ingestion task node details in admin and workflow/retrieval details in chat while keeping route views thin.

**Step 4: Run build to verify it passes**

Run: `cmd /c npm run build`
Expected: PASS.

### Task 5: Final Verification and Documentation

**Files:**
- Modify: `docx/PRD.md`
- Modify: `docx/TECH_DESIGN.md`
- Modify: `docx/AGENTS.md`

**Step 1: Run full backend verification**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest discover -s backend\src\tests -p 'test_*.py' -v`
Expected: PASS.

**Step 2: Run frontend build verification**

Run: `cmd /c npm run build`
Expected: PASS.

**Step 3: Update docs**

Document the ingestion node logs, retrieval engine, and workflow layer.
