# RetriFlow Phase 3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move RetriFlow from a LangGraph-ready skeleton to a first runnable streaming workflow with file-upload ingestion and a workflow adapter that can switch to real LangGraph when dependencies are available.

**Architecture:** Preserve the current workflow/retrieval split and extend it in three directions: SSE streaming chat, upload-based ingestion entrypoints, and a dedicated workflow adapter layer. The adapter should support a local fallback implementation now and a LangGraph-backed implementation later without forcing API or UI rewrites.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, Vue 3, TypeScript, Vite, SSE, multipart upload, LangGraph adapter pattern

---

### Task 1: Add Streaming Chat API

**Files:**
- Modify: `backend/src/api/routes/chat.py`
- Modify: `backend/src/schemas/chat.py`
- Create: `backend/src/domain/streaming.py`
- Modify: `backend/src/tests/retriflow_backend/test_chat_api.py`

**Step 1: Write the failing test**

Add a test that calls a new streaming chat endpoint and asserts the response is an event stream containing workflow metadata and at least one assistant delta event.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_chat_api.py -v`
Expected: FAIL because the stream endpoint does not exist yet.

**Step 3: Write minimal implementation**

Add a FastAPI streaming endpoint that emits SSE frames from the current workflow adapter.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_chat_api.py -v`
Expected: PASS.

### Task 2: Add Upload-Based Ingestion

**Files:**
- Modify: `backend/src/api/routes/knowledge.py`
- Modify: `backend/src/domain/knowledge.py`
- Modify: `backend/src/schemas/knowledge.py`
- Modify: `backend/src/tests/retriflow_backend/test_knowledge_document_api.py`

**Step 1: Write the failing test**

Add a test that uploads a text file to a knowledge base and asserts a document, chunks, and ingestion task are created.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_knowledge_document_api.py -v`
Expected: FAIL because no upload endpoint exists.

**Step 3: Write minimal implementation**

Add multipart upload handling for plain text files, create a document from file contents, and reuse the existing ingestion pipeline path.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_knowledge_document_api.py -v`
Expected: PASS.

### Task 3: Add Workflow Adapter Layer

**Files:**
- Create: `backend/src/domain/workflow_adapter.py`
- Modify: `backend/src/domain/workflow.py`
- Modify: `backend/src/core/config.py`
- Modify: `backend/src/tests/retriflow_backend/test_chat_api.py`

**Step 1: Write the failing test**

Add a test asserting workflow metadata now includes the adapter mode and that the fallback adapter is selected when LangGraph is unavailable.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_chat_api.py -v`
Expected: FAIL because adapter metadata is missing.

**Step 3: Write minimal implementation**

Create a workflow adapter abstraction with a fallback implementation and optional LangGraph selection based on config and installed dependencies.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend\src\tests\retriflow_backend\test_chat_api.py -v`
Expected: PASS.

### Task 4: Upgrade Frontend for Streaming and Upload

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/composables/useRetriFlowChat.ts`
- Modify: `frontend/src/composables/useRetriFlowAdmin.ts`
- Modify: `frontend/src/views/ChatView.vue`
- Modify: `frontend/src/views/AdminView.vue`

**Step 1: Define failing verification**

The chat view should be able to consume stream events and the admin view should support uploading a text file into a knowledge base.

**Step 2: Run build to confirm missing features**

Run: `cmd /c npm run build`
Expected: current build passes but no stream/upload support exists.

**Step 3: Write minimal implementation**

Add a stream consumer composable path and a file upload action while preserving thin route views.

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

Document the SSE chat endpoint, upload ingestion, and workflow adapter strategy.
