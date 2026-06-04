# Tika Structured Parsing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Tika-driven document parsing layer to RetriFlow that extracts structured blocks, normalizes them, validates them with Pydantic, and feeds them into the existing LangChain ingestion pipeline.

**Architecture:** Keep RetriFlow as a Python backend and treat Apache Tika as an external parsing engine. Add a new document parsing pipeline in `domain` that calls Tika, converts XHTML into structured blocks, normalizes and validates the data, then expands the result into the existing ingestion flow.

**Tech Stack:** Python 3.12, FastAPI, httpx, Pydantic, LangChain, Apache Tika Server, unittest

---

### Task 1: Add Tika Configuration and Client Contracts

**Files:**
- Modify: `backend/src/core/config.py`
- Modify: `.env.example`
- Create: `backend/src/schemas/document_structure.py`
- Create: `backend/src/domain/tika_client.py`
- Test: `backend/src/tests/retriflow_backend/test_tika_client.py`

**Step 1: Write the failing test**

Add tests that expect a `RetriFlowTikaClient` to parse a file response into a `RawParsedDocument` model and to reject malformed responses.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_tika_client -v`
Expected: FAIL because the client and schema do not exist yet.

**Step 3: Write minimal implementation**

Add Tika endpoint settings, define raw parse schemas, and implement a client that accepts bytes, filename, and content type and returns validated models.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_tika_client -v`
Expected: PASS.

### Task 2: Add Structured XHTML Extraction

**Files:**
- Create: `backend/src/domain/document_structure.py`
- Modify: `backend/src/schemas/document_structure.py`
- Test: `backend/src/tests/retriflow_backend/test_document_structure.py`

**Step 1: Write the failing test**

Add tests that feed minimal XHTML and expect heading, paragraph, and table blocks with page and header metadata to be extracted.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_document_structure -v`
Expected: FAIL because no extractor exists.

**Step 3: Write minimal implementation**

Implement an XHTML extractor that walks simple page containers and emits structured blocks with stable metadata.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_document_structure -v`
Expected: PASS.

### Task 3: Add Normalization and Schema Validation

**Files:**
- Create: `backend/src/domain/document_normalizer.py`
- Modify: `backend/src/schemas/document_structure.py`
- Test: `backend/src/tests/retriflow_backend/test_document_normalizer.py`

**Step 1: Write the failing test**

Add tests covering whitespace cleanup, unit normalization, empty-value handling, and table shape validation.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_document_normalizer -v`
Expected: FAIL because no normalizer exists.

**Step 3: Write minimal implementation**

Implement structure-preserving normalization and Pydantic validation for headings, paragraphs, tables, captions, and page metadata.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_document_normalizer -v`
Expected: PASS.

### Task 4: Integrate Structured Parsing Into Upload Ingestion

**Files:**
- Modify: `backend/src/domain/knowledge.py`
- Modify: `backend/src/domain/ingestion.py`
- Modify: `backend/src/api/routes/knowledge.py`
- Modify: `backend/src/tests/retriflow_backend/test_knowledge_document_api.py`

**Step 1: Write the failing test**

Add upload tests that simulate a parsed structured document and assert the upload path creates documents and chunks from structured content instead of direct UTF-8 decode.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_knowledge_document_api -v`
Expected: FAIL because upload still only supports raw UTF-8 text.

**Step 3: Write minimal implementation**

Replace the direct decode path with the Tika parse -> extract -> normalize pipeline and flatten normalized blocks into ingestion-ready text.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_knowledge_document_api -v`
Expected: PASS.

### Task 5: Add Ingestion Node Visibility for Parse Stages

**Files:**
- Modify: `backend/src/domain/ingestion.py`
- Modify: `backend/src/domain/knowledge.py`
- Modify: `backend/src/tests/retriflow_backend/test_ingestion_api.py`

**Step 1: Write the failing test**

Add a test expecting upload-based ingestion tasks to include `parse` and `extract` nodes before `normalize`, `segment`, `chunk`, and `index`.

**Step 2: Run test to verify it fails**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_ingestion_api -v`
Expected: FAIL because task logs do not include parse stages.

**Step 3: Write minimal implementation**

Allow ingestion node logs to be augmented with parser/extractor stage results produced by the upload pipeline.

**Step 4: Run test to verify it passes**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest backend.src.tests.retriflow_backend.test_ingestion_api -v`
Expected: PASS.

### Task 6: Final Verification and Documentation

**Files:**
- Modify: `docx/PRD.md`
- Modify: `docx/TECH_DESIGN.md`
- Modify: `docx/AGENTS.md`

**Step 1: Run full backend verification**

Run: `& 'D:\code\program\RetriFlow\.venv\Scripts\python.exe' -m unittest discover -s backend\src\tests -p 'test_*.py' -v`
Expected: PASS.

**Step 2: Update docs**

Document Tika configuration, structured parsing responsibilities, normalization rules, and the new ingestion stages.

**Step 3: Verify frontend remains unaffected**

Run: `cmd /c npm run build`
Expected: PASS.
