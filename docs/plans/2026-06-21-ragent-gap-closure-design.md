# RetriFlow ragent Gap Closure Design

## Goal
Close the remaining practical gaps between RetriFlow and the local `ragent` project, excluding Milvus and unverified Elasticsearch behavior.

## Scope
This round follows ragent's implemented modules, not feature names alone. The target gaps are user management, document source preview/file access, chunk logs, document schedules, trace run records, RAG evaluation, dashboard metrics, MCP server support, and frontend admin decomposition.

## Architecture
Implementation stays incremental. Each capability adds the smallest backend boundary first, covers it with targeted tests, then adds frontend UI only where the backend behavior is stable.

RetriFlow keeps its Python/FastAPI/Vue architecture. ragent's Java concepts are translated into RetriFlow's existing modules:

- ragent `UserController/UserService` -> `modules.auth`, `modules.admin`, and admin UI user table.
- ragent `KnowledgeDocumentController` preview/file/chunk logs -> `modules.knowledge`, `infra.storage`, and document/chunk admin panels.
- ragent schedule tables and processors -> a RetriFlow-local scheduler service with explicit API-triggered tests first.
- ragent `t_rag_trace_run` -> RetriFlow `rag_trace_runs` while keeping existing trace node details.
- ragent `/rag/eval` -> RetriFlow eval endpoint that exposes retrieval and intent diagnostics.
- ragent dashboard split -> RetriFlow admin service methods and dashboard panel data.
- ragent `mcp-server` module -> lightweight RetriFlow MCP server entrypoint reusing current MCP executors.

## Data Flow
Document upload already persists `source_uri`. Preview/file endpoints read through `resolve_file_storage()` and never expose raw storage paths as public URLs.

Chunk log rows are written during ingestion/reindex around parser, chunker, embedding, and persistence phases. Ingestion task nodes remain the per-node execution timeline; chunk logs become document-level history.

Schedules store remote-source metadata, lock state, and execution records. Initial implementation supports local and HTTP-compatible source checks only; S3 stays a future storage backend unless real dependencies are added.

Trace runs are written at root span lifecycle. Existing `rag_trace_nodes` remain the detailed tree. Admin trace listing can read run rows first and fall back to root nodes for compatibility during migration.

## Error Handling
All new persistence should be idempotent where ragent does so: feedback/user/document updates use clear upsert/update paths; schedule execution records must capture failed state and error text; preview/file endpoints return 404 for missing documents or missing source files.

## Testing
Each task starts with backend tests that fail against the current code. Frontend tasks must pass `cmd /c npm.cmd run build`. Full verification should include affected targeted tests plus final frontend build.

