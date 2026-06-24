-- RetriFlow PostgreSQL destructive reset script for HeidiSQL / DBeaver / pgAdmin.
-- Plain SQL only: no psql commands, no DO blocks, no explicit transaction.
--
-- Target schema: public
-- If your RetriFlow schema is not public, replace every "public." prefix below.
--
-- HeidiSQL note:
-- If a previous failed statement left the session in "current transaction is aborted",
-- run ROLLBACK first. Keeping it here is harmless when no transaction is active.

ROLLBACK;

DROP TABLE IF EXISTS public.message_feedback CASCADE;
DROP TABLE IF EXISTS public.conversation_long_memories CASCADE;
DROP TABLE IF EXISTS public.conversation_mid_memories CASCADE;
DROP TABLE IF EXISTS public.conversation_memory_summaries CASCADE;
DROP TABLE IF EXISTS public.rag_trace_nodes CASCADE;
DROP TABLE IF EXISTS public.conversation_messages CASCADE;
DROP TABLE IF EXISTS public.ingestion_task_nodes CASCADE;
DROP TABLE IF EXISTS public.ingestion_tasks CASCADE;
DROP TABLE IF EXISTS public.ingestion_pipelines CASCADE;
DROP TABLE IF EXISTS public.knowledge_document_table_cells CASCADE;
DROP TABLE IF EXISTS public.knowledge_document_blocks CASCADE;
DROP TABLE IF EXISTS public.knowledge_chunks CASCADE;
DROP TABLE IF EXISTS public.knowledge_documents CASCADE;
DROP TABLE IF EXISTS public.knowledge_base_route_profiles CASCADE;
DROP TABLE IF EXISTS public.admin_keyword_mappings CASCADE;
DROP TABLE IF EXISTS public.admin_intent_nodes CASCADE;
DROP TABLE IF EXISTS public.model_health CASCADE;
DROP TABLE IF EXISTS public.retriflow_chunk_vectors CASCADE;
DROP TABLE IF EXISTS public.knowledge_bases CASCADE;
DROP TABLE IF EXISTS public.sessions CASCADE;
DROP TABLE IF EXISTS public.users CASCADE;
