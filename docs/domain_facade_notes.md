# RetriFlow Domain Removal Notes

`backend/src/domain` has been removed from the backend architecture.

The real implementation now lives in:

- `backend/src/modules`: application/business modules.
- `backend/src/infra`: infrastructure adapters such as LLM, embeddings, vector store, and document parser.

## Current rule

- Application code imports business services from `modules/`.
- Application code imports external adapters from `infra/`.
- Tests patch and import canonical `modules.*` / `infra.*` paths.
- Do not reintroduce `domain/` as a dumping ground or compatibility patch layer.

## Removed compatibility layer

The old `domain/` package used to re-export modules such as auth, chat, knowledge, memory, retrieval, workflow, and MCP. It was deleted after backend code and tests were migrated away from `domain.*` imports.

If legacy external scripts still import `domain.*`, update them to the canonical paths:

- `modules.auth`
- `modules.chat`
- `modules.ingestion`
- `modules.knowledge`
- `modules.memory`
- `modules.mcp`
- `modules.rag`
- `infra.document_parser`
- `infra.embeddings`
- `infra.llm`
- `infra.vector_store`

## Verification

Before claiming architecture cleanup is complete, run:

```powershell
rg "from domain|import domain|domain\." backend/src -n
```

The command should return no matches.
