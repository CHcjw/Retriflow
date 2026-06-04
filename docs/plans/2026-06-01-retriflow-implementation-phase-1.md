# RetriFlow Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first runnable implementation skeleton for the RetriFlow migration, including a Python backend foundation and a Vue frontend foundation named for the RetriFlow project.

**Architecture:** Start with a repo-local `retriflow_backend` Python service and `retriflow_web` Vue app structure. Implement minimal typed APIs, domain boundaries, and app shells that reflect the approved migration documents without pretending to complete the full `ragent` migration in one step.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Vue 3, TypeScript, Vite, Vue Router, Pinia

---

### Task 1: Create Backend Skeleton

**Files:**
- Create: `retriflow_backend/pyproject.toml`
- Create: `retriflow_backend/src/retriflow_backend/__init__.py`
- Create: `retriflow_backend/src/retriflow_backend/main.py`
- Create: `retriflow_backend/src/retriflow_backend/api/__init__.py`
- Create: `retriflow_backend/src/retriflow_backend/api/router.py`
- Create: `retriflow_backend/src/retriflow_backend/core/__init__.py`
- Create: `retriflow_backend/src/retriflow_backend/core/config.py`
- Test: `retriflow_backend/tests/test_app.py`

**Step 1: Write the failing test**

Write a test asserting the backend app exposes a health endpoint and a named API root.

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest retriflow_backend/tests/test_app.py -v`
Expected: FAIL because the backend package does not exist yet.

**Step 3: Write minimal implementation**

Create a FastAPI app with `/healthz` and `/api/v1/meta` endpoints and typed config values.

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest retriflow_backend/tests/test_app.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add retriflow_backend
git commit -m "feat: scaffold retriflow backend"
```

### Task 2: Add Domain and Chat API Skeleton

**Files:**
- Create: `retriflow_backend/src/retriflow_backend/domain/__init__.py`
- Create: `retriflow_backend/src/retriflow_backend/domain/chat.py`
- Create: `retriflow_backend/src/retriflow_backend/schemas/__init__.py`
- Create: `retriflow_backend/src/retriflow_backend/schemas/chat.py`
- Create: `retriflow_backend/src/retriflow_backend/api/routes/chat.py`
- Test: `retriflow_backend/tests/test_chat_api.py`

**Step 1: Write the failing test**

Write tests asserting the chat bootstrap endpoint returns the RetriFlow capability summary and that a stream placeholder endpoint responds successfully.

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest retriflow_backend/tests/test_chat_api.py -v`
Expected: FAIL because the routes and schemas are missing.

**Step 3: Write minimal implementation**

Add a typed chat domain service and minimal chat routes that expose the agreed migration capability surface.

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest retriflow_backend/tests/test_chat_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add retriflow_backend
git commit -m "feat: add retriflow chat api skeleton"
```

### Task 3: Add Knowledge and Session API Skeleton

**Files:**
- Create: `retriflow_backend/src/retriflow_backend/domain/knowledge.py`
- Create: `retriflow_backend/src/retriflow_backend/domain/session.py`
- Create: `retriflow_backend/src/retriflow_backend/schemas/knowledge.py`
- Create: `retriflow_backend/src/retriflow_backend/schemas/session.py`
- Create: `retriflow_backend/src/retriflow_backend/api/routes/knowledge.py`
- Create: `retriflow_backend/src/retriflow_backend/api/routes/session.py`
- Test: `retriflow_backend/tests/test_knowledge_api.py`
- Test: `retriflow_backend/tests/test_session_api.py`

**Step 1: Write the failing test**

Write tests asserting the session and knowledge bootstrap endpoints return typed seed data.

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest retriflow_backend/tests/test_knowledge_api.py retriflow_backend/tests/test_session_api.py -v`
Expected: FAIL because the modules are missing.

**Step 3: Write minimal implementation**

Add placeholder domain services and typed endpoints for sessions and knowledge bases.

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest retriflow_backend/tests/test_knowledge_api.py retriflow_backend/tests/test_session_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add retriflow_backend
git commit -m "feat: add retriflow session and knowledge skeleton"
```

### Task 4: Create Frontend Skeleton

**Files:**
- Create: `retriflow_web/package.json`
- Create: `retriflow_web/tsconfig.json`
- Create: `retriflow_web/vite.config.ts`
- Create: `retriflow_web/index.html`
- Create: `retriflow_web/src/main.ts`
- Create: `retriflow_web/src/App.vue`
- Create: `retriflow_web/src/router/index.ts`
- Create: `retriflow_web/src/stores/app.ts`
- Create: `retriflow_web/src/views/HomeView.vue`
- Create: `retriflow_web/src/views/ChatView.vue`
- Create: `retriflow_web/src/views/AdminView.vue`
- Create: `retriflow_web/src/assets/main.css`

**Step 1: Write the failing test**

Define the first verification target: the frontend project structure exists and route entry files are present.

**Step 2: Run test to verify it fails**

Run: inspect `retriflow_web/`
Expected: files do not exist yet.

**Step 3: Write minimal implementation**

Create a Vue 3 + TypeScript app shell using Composition API and thin route views.

**Step 4: Run test to verify it passes**

Run: inspect `retriflow_web/`
Expected: files exist and app structure is coherent.

**Step 5: Commit**

```bash
git add retriflow_web
git commit -m "feat: scaffold retriflow web app"
```

### Task 5: Final Verification

**Files:**
- Modify: `retriflow_backend/*`
- Modify: `retriflow_web/*`

**Step 1: Write the failing test**

Define the final phase target: backend tests pass and frontend skeleton files align with the migration plan and RetriFlow naming.

**Step 2: Run test to verify it fails**

Run: backend test suite before final fixes
Expected: any remaining integration mismatch fails.

**Step 3: Write minimal implementation**

Resolve naming or routing inconsistencies and align files with the phase-1 architecture.

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest retriflow_backend/tests -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add retriflow_backend retriflow_web
git commit -m "feat: complete retriflow phase 1 skeleton"
```
