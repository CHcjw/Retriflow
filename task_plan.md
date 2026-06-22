# Task Plan: RetriFlow Enhancement Implementation

## Goal
Read the RetriFlow and ragent projects, preserve the structure of the three `docx/*.md` documents, and implement the enhancement plan in `docs/plans` step by step using ragent logic as the reference source.

## Current Phase
Phase 6

## Phases

### Phase 1: Requirements & Discovery
- [x] Capture user constraints.
- [x] Read `docx/AGENTS.md`, `docx/PRD.md`, and `docx/TECH_DESIGN.md`.
- [x] Read the enhancement plan under `docs/plans`.
- [x] Inventory RetriFlow backend/frontend structure.
- [x] Inventory relevant ragent source structure.
- [x] Document findings in `findings.md`.
- **Status:** complete

### Phase 2: Design Confirmation
- [x] Identify exact enhancement items and map each to RetriFlow modules.
- [x] Compare against ragent behavior before proposing implementation.
- [x] Present a scoped design and proceed after user approval to keep going.
- **Status:** complete

### Phase 3: Implementation Plan
- [x] Write a detailed implementation plan under `docs/plans`.
- [x] Add required doc updates under existing `docx/*.md` headings only.
- [x] Define TDD checkpoints for each enhancement.
- **Status:** complete

### Phase 4: TDD Implementation
- [x] Implement each approved enhancement with failing tests first.
- [x] Keep changes scoped to the plan and ragent reference logic.
- [x] Update progress after each completed item.
- **Status:** complete

### Phase 5: Verification & Delivery
- [x] Run targeted backend tests.
- [x] Run targeted frontend build/tests when frontend changes exist.
- [x] Summarize implemented items, skipped items, and verification results.
- **Status:** complete

### Phase 6: ragent Gap Closure
- [x] Delete completed docs/plans implementation documents.
- [x] Compare RetriFlow against local ragent and identify remaining gaps excluding Milvus.
- [x] Write ragent gap closure design and implementation plan.
- [x] Implement Task 1: User Management Completion.
- [x] Implement Task 2: Document Preview and Source File Access.
- [x] Implement Task 3: Document Chunk Logs.
- [ ] Implement Task 4: Document Schedule Refresh.
- [ ] Implement Task 5: Trace Run Table.
- [ ] Implement Task 6: RAG Evaluation Endpoint.
- [ ] Implement Task 7: Dashboard Metric Split.
- [ ] Implement Task 8: Lightweight MCP Server.
- [ ] Implement Task 9: Admin Frontend Decomposition.
- [ ] Implement Task 10: Documentation and Final Verification.
- **Status:** in_progress

## Key Questions
1. Which enhancement plan is authoritative if multiple `docs/plans` files exist?
2. Which ragent modules correspond to each RetriFlow enhancement item?
3. Which docx headings should receive requirement/design additions without changing document structure?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Do not write business code before design approval | Required by the brainstorming workflow and reduces risk on this large task. |
| Use ragent as behavioral reference, not as a license to broaden scope | The user explicitly asked not to invent or casually expand features. |
| Preserve `docx/*.md` heading structure | The user explicitly required future additions under existing headings. |
| Exclude Milvus from gap closure | User explicitly confirmed all remaining ragent gaps except Milvus should be implemented. |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|

## Notes
- Existing working tree already contains many user modifications; do not revert unrelated changes.
- Current task must proceed through discovery, design approval, plan, then implementation.
