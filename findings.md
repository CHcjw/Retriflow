# Findings & Decisions

## Requirements
- Read the whole RetriFlow project context before changing behavior.
- Use `docx/AGENTS.md`, `docx/PRD.md`, and `docx/TECH_DESIGN.md` as the documentation baseline.
- Keep the structure of those three Markdown documents unchanged.
- Add future functionality or requirements only under the corresponding existing headings.
- Use the enhancement plan in `docs/plans` as the implementation driver.
- Implement items one by one.
- Base behavior on the existing `ragent` project code logic.
- Do not invent behavior or casually expand scope.

## Research Findings
- `docx/AGENTS.md` headings: 项目概述, 开发规范, 代码风格, 测试要求, ragent 对齐规则, 八大对齐事项, 模块边界, 推荐验证命令, 注意事项.
- `docx/PRD.md` headings: 产品概述, 目标用户, 核心功能/必须做, 后续继续对齐 ragent, 后台界面设计, 产品边界.
- `docx/TECH_DESIGN.md` headings: 技术栈, 项目结构, 数据模型, 核心流程, 关键技术点, 配置与外部服务, 验证命令, 剩余技术差距.
- `docs/plans/ragent-followup-enhancement-plan.md` scope items: 消息反馈闭环, Trace 分页与筛选, 意图澄清/引导, Prompt 模板服务, 文件存储抽象.
- Enhancement execution order: backend feedback table/API/service/tests; frontend feedback entry/admin list; trace query params/pagination/frontend filters; prompt template service and replacement; minimal intent clarification loop; file storage abstraction and upload integration; targeted backend tests and frontend build.
- Acceptance constraints: backend API/unit tests for each backend capability; frontend changes must pass `npm run build`; do not introduce Milvus; do not implement ES without ragent code evidence; keep ragent-style UI density without long explanatory copy.
- PowerShell `Get-Content` displayed UTF-8 docs as mojibake; Python `-X utf8` reads them correctly. Treat shell display乱码 as a tooling boundary issue, not file corruption.
- RetriFlow current structure includes backend modules for admin/auth/chat/ingestion/knowledge/mcp/memory/rag/session and frontend admin/chat components.
- Existing RetriFlow traces already show implementation artifacts for several plan items: `message_feedback` table/index in `core/state.py`, chat feedback route/service, admin feedback list route, trace list pagination fields, and `modules/rag/prompt.py`.
- ragent reference locations found for the plan items: message feedback controller/service/entity/schema; trace page request/query service; guidance service/checker/decision; prompt template loader/build plan/scene/RAG prompt service; file storage service/S3 implementation.
- Message feedback status: RetriFlow has `message_feedback` tables for SQLite/Postgres, unique `(message_id,user_id)` index, `POST /api/v1/chat/messages/{message_id}/feedback`, assistant-message validation, upsert of `vote/reason/comment`, frontend chat feedback buttons, admin list endpoint, and backend tests in `test_chat_api.py`.
- Trace pagination status: RetriFlow admin route supports `q`, `user_query`, `status`, `page`, `page_size`; service returns `total/page/page_size`. Current status filter is coarse (`SUCCESS` means message_count > 0, `EMPTY` means message_count = 0) and does not yet filter by trace node state/time.
- Prompt template status: RetriFlow already has `modules/rag/prompt.py` with loader, section parsing, slot rendering, and prompt files used by rewrite/intent/LLM service.
- Intent clarification status: RetriFlow intent classifier already has a `clarification` intent and workflow short-circuit response, but the ragent-style multi-candidate ambiguity guidance service still needs comparison before any implementation.
- File storage status: `backend/src/infra/storage/__init__.py` is only a placeholder; knowledge upload currently reads multipart bytes and passes them directly into parsing/service logic.
- ragent Trace filtering fields are `traceId`, `conversationId`, `taskId`, and `status` over `RagTraceRunDO`. RetriFlow currently lacks a separate run table and uses sessions/messages plus trace nodes; an incremental equivalent should filter by session/trace id, owner, status derived from persisted root trace nodes, and time where available.
- ragent Guidance only triggers for exactly one sub-question, two or more candidate intent node scores, near score ratio/margin, explicit-domain skip, optional LLM confirmation, and then returns a prompt decision. RetriFlow should not add fake `guidance-detect` nodes unless it has real candidate scores from route resolution.
- ragent FileStorageService boundary includes upload overloads, reliable upload, openStream, and deleteByUrl. RetriFlow should start with local storage implementing the same minimal boundary used by upload parsing, with S3-shaped configuration names but no fake S3 behavior unless real dependencies are introduced.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Discovery before implementation | Needed to map plan items to real RetriFlow and ragent code. |
| Close remaining ragent gaps except Milvus | User confirmed this scope on 2026-06-21. |
| Implement gaps as vertical slices | Reduces risk and keeps each ragent-aligned capability testable end to end. |

## ragent Gap Closure Findings
- Remaining gap plan saved to `docs/plans/2026-06-21-ragent-gap-closure.md`.
- Design saved to `docs/plans/2026-06-21-ragent-gap-closure-design.md`.
- Milvus is explicitly excluded.
- Priority order: user management, document preview/file, chunk logs, schedules, trace run table, eval endpoint, dashboard metric split, MCP server, admin frontend decomposition, docs/final verification.

## Issues Encountered
| Issue | Resolution |
|-------|------------|

## Resources
- `docx/AGENTS.md`
- `docx/PRD.md`
- `docx/TECH_DESIGN.md`
- `docs/plans/`
- `ragent/`

## Visual/Browser Findings
- Not applicable yet.
