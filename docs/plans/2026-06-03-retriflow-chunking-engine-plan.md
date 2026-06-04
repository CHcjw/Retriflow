# RetriFlow Chunking Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade RetriFlow from a single recursive chunker to a configurable multi-strategy chunking engine that supports fixed-size, overlap, recursive, embedding-semantic, and hybrid chunking.

**Architecture:** Keep the current ingestion entrypoint and replace the hard-coded splitter in `RetriFlowIngestionPipeline` with a strategy-driven chunking layer. Pass document type and structured metadata into the chunker, run optional post-processing, and persist chunk metadata so retrieval and debugging stay aligned.

**Tech Stack:** Python 3.12, FastAPI, LangChain, langchain-text-splitters, Pydantic, sqlite3, unittest

---

### Task 1: Lock The New Chunking Behaviors With Tests

**Files:**
- Modify: `backend/src/tests/retriflow_backend/test_ingestion_pipeline.py`
- Modify: `backend/src/tests/retriflow_backend/test_knowledge_document_api.py`

**Step 1: Write the failing tests**

Add tests for:
- explicit fixed-size chunking
- recursive chunking with configurable separators
- semantic chunking metadata
- recursive + semantic hybrid chunking
- auto strategy selection by document type
- post-processing that merges tiny chunks and preserves metadata

**Step 2: Run tests to verify they fail**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_ingestion_pipeline backend.src.tests.retriflow_backend.test_knowledge_document_api -v`
Expected: FAIL because the current pipeline only supports one recursive splitter.

**Step 3: Write minimal implementation**

Add only the minimum interfaces and assertions required to express the desired behavior.

**Step 4: Re-run the tests**

Expected: still FAIL, but now for missing implementation rather than missing expectations.

### Task 2: Introduce Strategy-Driven Chunking Models

**Files:**
- Modify: `backend/src/core/config.py`
- Create: `backend/src/schemas/chunking.py`
- Modify: `backend/src/domain/ingestion.py`

**Step 1: Write the failing test**

Add tests expecting:
- a default chunking strategy of `auto`
- chunk results to carry strategy and document-type metadata

**Step 2: Run test to verify it fails**

Run the targeted ingestion tests.
Expected: FAIL because the schema/config does not exist yet.

**Step 3: Write minimal implementation**

Add:
- chunking config settings
- chunk strategy request/result models
- metadata-aware chunk result objects

**Step 4: Run test to verify it passes**

Expected: PASS for config/model coverage.

### Task 3: Implement Core Chunking Strategies

**Files:**
- Modify: `backend/src/domain/ingestion.py`
- Test: `backend/src/tests/retriflow_backend/test_ingestion_pipeline.py`

**Step 1: Write the failing test**

Add tests for:
- fixed-size chunking
- overlap chunking
- recursive chunking with custom separators
- code/log/html-aware chunking helpers

**Step 2: Run test to verify it fails**

Expected: FAIL because the pipeline cannot switch strategies.

**Step 3: Write minimal implementation**

Implement:
- fixed-size splitter
- overlap splitter
- recursive splitter with configurable separator list
- code/log/html helper preprocessing where needed

**Step 4: Run test to verify it passes**

Expected: PASS.

### Task 4: Implement Embedding-Semantic And Hybrid Chunking

**Files:**
- Create: `backend/src/domain/embedding.py`
- Modify: `backend/src/domain/ingestion.py`
- Test: `backend/src/tests/retriflow_backend/test_ingestion_pipeline.py`

**Step 1: Write the failing test**

Add tests expecting:
- semantic chunking to group semantically adjacent units
- hybrid recursive + semantic chunking to preserve coarse structure first
- graceful fallback metadata when real embeddings are unavailable

**Step 2: Run test to verify it fails**

Expected: FAIL because semantic chunking is not implemented.

**Step 3: Write minimal implementation**

Implement:
- embedding service interface
- provider-backed embedding calls when configured
- lexical fallback when provider is unavailable
- semantic boundary scoring
- hybrid recursive + semantic chaining

**Step 4: Run test to verify it passes**

Expected: PASS.

### Task 5: Add Auto Strategy Selection And Post-Processing

**Files:**
- Modify: `backend/src/domain/ingestion.py`
- Test: `backend/src/tests/retriflow_backend/test_ingestion_pipeline.py`

**Step 1: Write the failing test**

Add tests for:
- manuals/knowledge-base content selecting recursive chunking
- FAQ selecting recursive chunking
- contracts selecting semantic chunking
- logs selecting fixed/line chunking
- OCR-like noisy text selecting overlap or semantic chunking
- post-processing merging tiny chunks and splitting oversized chunks

**Step 2: Run test to verify it fails**

Expected: FAIL because `auto` does not make strategy decisions yet.

**Step 3: Write minimal implementation**

Add:
- document-type inference
- strategy recommendation map
- post-processing for merge/split/metadata completion

**Step 4: Run test to verify it passes**

Expected: PASS.

### Task 6: Wire Chunk Metadata Into Persistence And API

**Files:**
- Modify: `backend/src/core/state.py`
- Modify: `backend/src/schemas/knowledge.py`
- Modify: `backend/src/domain/knowledge.py`
- Modify: `backend/src/domain/retrieval_channels.py`
- Test: `backend/src/tests/retriflow_backend/test_knowledge_document_api.py`

**Step 1: Write the failing test**

Add tests expecting chunk API responses to include strategy/document-type metadata and uploaded structured docs to preserve page/block metadata on chunks.

**Step 2: Run test to verify it fails**

Expected: FAIL because `knowledge_chunks` stores only plain text today.

**Step 3: Write minimal implementation**

Add:
- `metadata_json`, `strategy`, and `document_type` persistence fields
- backward-compatible schema hydration
- retrieval row loading that keeps metadata available for later ranking/debugging

**Step 4: Run test to verify it passes**

Expected: PASS.

### Task 7: Final Verification

**Files:**
- Verify only

**Step 1: Run targeted tests**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_ingestion_pipeline backend.src.tests.retriflow_backend.test_knowledge_document_api backend.src.tests.retriflow_backend.test_ingestion_api -v`
Expected: PASS.

**Step 2: Run full backend suite**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest discover -s backend\src\tests`
Expected: PASS.

**Step 3: Run smoke verification**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' 'tools\tika\verify_tika_uploads.py'`
Expected: PASS with stable structured parsing output.
