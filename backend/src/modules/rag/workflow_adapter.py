from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import re

from infra.llm import RetriFlowLLMService
from modules.knowledge import RetriFlowKnowledgeRouteService
from modules.knowledge.routing import KnowledgeRouteCandidate, KnowledgeRouteDecision
from modules.mcp import RetriFlowMcpService
from modules.memory import RetriFlowConversationMemoryService
from modules.rag.guidance import RetriFlowIntentGuidanceService
from modules.rag.intent import IntentDecision
from modules.rag.intent import RetriFlowIntentClassifier
from modules.rag.postprocess import RetriFlowAnswerPostprocessor
from modules.rag.retrieval.engine import RetriFlowRetrievalEngine
from modules.rag.trace import RetriFlowTraceService
from modules.rag.rewrite import RetriFlowQueryRewriteService
from schemas.chat import ChatMcpCallItem, ChatSourceItem


@dataclass
class WorkflowAdapterResult:
    adapter: str
    intent: str
    intent_confidence: float
    intent_reason: str
    intent_source: str
    retrieval_channels: list[str]
    retrieval_stage_counts: dict[str, int]
    retrieval_stage_metrics: dict[str, dict[str, object]]
    rewritten_queries: list[str]
    pipeline_stages: list[str]
    sources: list[ChatSourceItem]
    assistant_message: str
    route_mode: str
    route_confidence: float
    route_top_k: int | None
    route_candidates: list[dict[str, object]]
    mcp_calls: list[ChatMcpCallItem]


@dataclass
class WorkflowStreamAdapterResult:
    adapter: str
    intent: str
    intent_confidence: float
    intent_reason: str
    intent_source: str
    retrieval_channels: list[str]
    retrieval_stage_counts: dict[str, int]
    retrieval_stage_metrics: dict[str, dict[str, object]]
    rewritten_queries: list[str]
    pipeline_stages: list[str]
    sources: list[ChatSourceItem]
    deltas: Iterable[str]
    route_mode: str
    route_confidence: float
    route_top_k: int | None
    route_candidates: list[dict[str, object]]
    mcp_calls: list[ChatMcpCallItem]


@dataclass
class PreparedWorkflowContext:
    intent: str = "knowledge_retrieval"
    intent_confidence: float = 0.0
    intent_reason: str = ""
    intent_source: str = "fallback"
    rewritten_queries: list[str] | None = None
    pipeline_stages: list[str] | None = None
    route_mode: str = "global"
    route_confidence: float = 0.0
    route_top_k: int | None = None
    route_candidates: list[dict[str, object]] | None = None
    retrieval_channels: list[str] | None = None
    retrieval_stage_counts: dict[str, int] | None = None
    retrieval_stage_metrics: dict[str, dict[str, object]] | None = None
    sources: list[ChatSourceItem] | None = None
    extra_context: str = ""
    mcp_calls: list[ChatMcpCallItem] | None = None
    assistant_message_override: str = ""


class TracedAnswerDeltaIterator:
    def __init__(
        self,
        *,
        span,
        source: Iterable[str],
        fallback_factory,
        success_prefix: str = "",
    ) -> None:
        self.span = span
        self.source = iter(source)
        self.fallback_factory = fallback_factory
        self.success_prefix = success_prefix
        self.chunk_count = 0
        self.char_count = 0
        self.yielded_any = False
        self.finished = False

    def __iter__(self) -> "TracedAnswerDeltaIterator":
        return self

    def __next__(self) -> str:
        if self.finished:
            raise StopIteration

        try:
            delta = next(self.source)
        except StopIteration:
            if not self.yielded_any:
                fallback = self.fallback_factory()
                self._finish_success_with_delta("fallback", fallback)
                return fallback
            self.finished = True
            prefix = f"{self.success_prefix}; " if self.success_prefix else ""
            self.span.finish_success(output_summary=f"{prefix}chunks={self.chunk_count}; chars={self.char_count}")
            raise
        except Exception:
            fallback = self.fallback_factory()
            self._finish_success_with_delta("fallback", fallback)
            return fallback
        except BaseException as exc:
            self.finished = True
            self.span.finish_error(exc)
            raise

        self.yielded_any = True
        self.chunk_count += 1
        self.char_count += len(delta)
        return delta

    def close(self) -> None:
        if self.finished:
            return
        self.finished = True
        close = getattr(self.source, "close", None)
        if callable(close):
            close()
        self.span.finish_cancelled_if_running()

    def _finish_success_with_delta(self, prefix: str, delta: str) -> None:
        self.finished = True
        self.yielded_any = True
        self.chunk_count += 1
        self.char_count += len(delta)
        self.span.finish_success(output_summary=f"{prefix}; chunks={self.chunk_count}; chars={self.char_count}")


class WorkflowAdapter:
    name = "langgraph"

    def run(
        self,
        question: str,
        *,
        session_id: str = "",
        deep_thinking: bool = False,
        smart_search: bool = False,
    ) -> WorkflowAdapterResult:
        raise NotImplementedError

    def stream(
        self,
        question: str,
        *,
        session_id: str = "",
        deep_thinking: bool = False,
        smart_search: bool = False,
    ) -> WorkflowStreamAdapterResult:
        raise NotImplementedError


class LangGraphWorkflowAdapter(WorkflowAdapter):
    name = "langgraph"

    def __init__(self) -> None:
        self.retrieval_engine = RetriFlowRetrievalEngine()
        self.intent_classifier = RetriFlowIntentClassifier()
        self.route_service = RetriFlowKnowledgeRouteService()
        self.mcp_service = RetriFlowMcpService()
        self.memory_service = RetriFlowConversationMemoryService()
        self.guidance_service = RetriFlowIntentGuidanceService()
        self.query_rewrite_service = RetriFlowQueryRewriteService()
        self.llm_service = RetriFlowLLMService()
        self.answer_postprocessor = RetriFlowAnswerPostprocessor()
        self.trace_service = RetriFlowTraceService()

    def run(
        self,
        question: str,
        *,
        session_id: str = "",
        deep_thinking: bool = False,
        smart_search: bool = False,
    ) -> WorkflowAdapterResult:
        with self.trace_service.span(
            name="memory.load_prompt_messages",
            node_type="MEMORY",
            input_summary=f"session={session_id}",
        ) as span:
            memory_messages = self.memory_service.load_prompt_messages(
                session_id=session_id,
                query=question,
            )
            span.finish_success(output_summary=f"messages={len(memory_messages)}")
        context = self._prepare_context(question, memory_messages=memory_messages, smart_search=smart_search)
        assistant_message = self._generate_answer(
            question=question,
            sources=context.sources or [],
            extra_context=context.extra_context,
            mcp_calls=context.mcp_calls or [],
            memory_messages=memory_messages,
            assistant_message_override=context.assistant_message_override,
            intent=context.intent,
            deep_thinking=deep_thinking,
        )
        return WorkflowAdapterResult(
            adapter=self.name,
            intent=context.intent,
            intent_confidence=context.intent_confidence,
            intent_reason=context.intent_reason,
            intent_source=context.intent_source,
            retrieval_channels=context.retrieval_channels or [],
            retrieval_stage_counts=context.retrieval_stage_counts or {},
            retrieval_stage_metrics=context.retrieval_stage_metrics or {},
            rewritten_queries=context.rewritten_queries or [],
            pipeline_stages=context.pipeline_stages or self._default_pipeline_stages(context),
            sources=context.sources or [],
            assistant_message=assistant_message,
            route_mode=context.route_mode,
            route_confidence=context.route_confidence,
            route_top_k=context.route_top_k,
            route_candidates=context.route_candidates or [],
            mcp_calls=context.mcp_calls or [],
        )

    def stream(
        self,
        question: str,
        *,
        session_id: str = "",
        deep_thinking: bool = False,
        smart_search: bool = False,
    ) -> WorkflowStreamAdapterResult:
        with self.trace_service.span(
            name="memory.load_prompt_messages",
            node_type="MEMORY",
            input_summary=f"session={session_id}",
        ) as span:
            memory_messages = self.memory_service.load_prompt_messages(
                session_id=session_id,
                query=question,
            )
            span.finish_success(output_summary=f"messages={len(memory_messages)}")
        context = self._prepare_context(question, memory_messages=memory_messages, smart_search=smart_search)
        return WorkflowStreamAdapterResult(
            adapter=self.name,
            intent=context.intent,
            intent_confidence=context.intent_confidence,
            intent_reason=context.intent_reason,
            intent_source=context.intent_source,
            retrieval_channels=context.retrieval_channels or [],
            retrieval_stage_counts=context.retrieval_stage_counts or {},
            retrieval_stage_metrics=context.retrieval_stage_metrics or {},
            rewritten_queries=context.rewritten_queries or [],
            pipeline_stages=context.pipeline_stages or self._default_pipeline_stages(context),
            sources=context.sources or [],
            deltas=self._safe_stream_answer(
                question=question,
                sources=context.sources or [],
                extra_context=context.extra_context,
                mcp_calls=context.mcp_calls or [],
                memory_messages=memory_messages,
                assistant_message_override=context.assistant_message_override,
                intent=context.intent,
                deep_thinking=deep_thinking,
            ),
            route_mode=context.route_mode,
            route_confidence=context.route_confidence,
            route_top_k=context.route_top_k,
            route_candidates=context.route_candidates or [],
            mcp_calls=context.mcp_calls or [],
        )

    def _prepare_context(
        self,
        question: str,
        *,
        memory_messages: list[dict[str, str]],
        smart_search: bool = False,
    ) -> PreparedWorkflowContext:
        if date_answer := self._resolve_local_date_answer(question):
            return PreparedWorkflowContext(
                intent="date_query",
                intent_confidence=1.0,
                intent_reason="local date query",
                intent_source="local-rule",
                rewritten_queries=[question.strip()],
                pipeline_stages=["local", "generation"],
                route_mode="local",
                route_confidence=1.0,
                route_top_k=None,
                route_candidates=[],
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context="",
                mcp_calls=[],
                assistant_message_override=date_answer,
            )

        if assistant_answer := self._resolve_local_assistant_answer(question):
            return PreparedWorkflowContext(
                intent="system_assistant",
                intent_confidence=1.0,
                intent_reason="assistant capability query",
                intent_source="local-rule",
                rewritten_queries=[question.strip()],
                pipeline_stages=["local", "generation"],
                route_mode="local",
                route_confidence=1.0,
                route_top_k=None,
                route_candidates=[],
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context="",
                mcp_calls=[],
                assistant_message_override=assistant_answer,
            )

        with self.trace_service.span(
            name="query-rewrite-and-split",
            node_type="REWRITE",
            input_summary=question[:120],
        ) as span:
            rewritten_queries = self._rewrite_queries(
                question=question,
                memory_messages=memory_messages,
            )
            span.finish_success(output_summary=f"queries={len(rewritten_queries)}")

        intent_question = self._primary_query(question=question, rewritten_queries=rewritten_queries)
        with self.trace_service.span(
            name="intent-resolve",
            node_type="INTENT",
            input_summary=intent_question[:120],
        ) as span:
            intent_decision = self._classify_intent(
                question=intent_question,
                memory_messages=memory_messages,
            )
            span.finish_success(
                output_summary=f"intent={intent_decision.intent}; confidence={intent_decision.confidence:.2f}"
            )

        if intent_decision.intent == "clarification":
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "rewrite", "intent", "generation"],
                route_mode="clarification",
                route_confidence=0.0,
                route_top_k=None,
                route_candidates=[],
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context="",
                mcp_calls=[],
                assistant_message_override=(
                    intent_decision.clarification_question
                    or "鍙互鍐嶅叿浣撹鏄庝竴涓嬩綘鎸囩殑鏄摢涓€閮ㄥ垎鍚楋紵"
                ),
            )

        if intent_decision.intent == "chitchat":
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "rewrite", "intent", "generation"],
                route_mode="chitchat",
                route_confidence=0.0,
                route_top_k=None,
                route_candidates=[],
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context="",
                mcp_calls=[],
            )

        with self.trace_service.span(
            name="mcp.execute",
            node_type="MCP",
            input_summary=" | ".join(rewritten_queries)[:120],
        ) as span:
            mcp_result = self._execute_mcp_queries(
                original_question=f"联网搜索 {question}" if smart_search else question,
                rewritten_queries=rewritten_queries,
                memory_messages=memory_messages,
            )
            span.finish_success(output_summary=f"calls={len(mcp_result.calls)}")
        mcp_calls = [
            ChatMcpCallItem(
                tool_id=call.tool_id,
                arguments=call.arguments,
                content=call.content,
                is_error=call.is_error,
                sources=call.sources,
            )
            for call in mcp_result.calls
        ]
        if mcp_calls and (smart_search or self._has_explicit_web_intent(question)):
            return PreparedWorkflowContext(
                intent="tool_call",
                intent_confidence=max(intent_decision.confidence, mcp_result.route.confidence),
                intent_reason=mcp_result.route.reason or intent_decision.reason,
                intent_source="explicit-web",
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "rewrite", "intent", "mcp", "generation"],
                route_mode="mcp_only",
                route_confidence=mcp_result.route.confidence,
                route_top_k=None,
                route_candidates=[],
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context=mcp_result.context,
                mcp_calls=mcp_calls,
            )

        route_queries = rewritten_queries or [question]
        with self.trace_service.span(
            name="knowledge.route",
            node_type="ROUTE",
            input_summary=" | ".join(route_queries)[:120],
        ) as span:
            knowledge_route = self._resolve_routes(route_queries)
            route_candidates = [
                {
                    "knowledge_base_id": candidate.knowledge_base_id,
                    "mcp_tool_id": candidate.mcp_tool_id,
                    "name": candidate.name,
                    "path": candidate.path,
                    "score": candidate.score,
                    "top_k": candidate.top_k,
                    "min_score": candidate.min_score,
                    "has_param_prompt_template": bool(candidate.param_prompt_template.strip()),
                    "matched_node_path": candidate.matched_node_path,
                    "target_node_path": candidate.target_node_path,
                    "matched_terms": candidate.matched_terms,
                    "target_score": candidate.target_score,
                }
                for candidate in knowledge_route.candidates
            ]
            self.trace_service.update_node_metadata(
                span.id,
                {
                    "route_mode": knowledge_route.mode,
                    "route_confidence": knowledge_route.confidence,
                    "route_reason": knowledge_route.reason,
                    "knowledge_base_ids": knowledge_route.knowledge_base_ids,
                    "mcp_tool_ids": knowledge_route.mcp_tool_ids,
                    "candidates": route_candidates,
                    "route_top_k": self._resolve_route_top_k(knowledge_route),
                },
            )
            span.finish_success(
                output_summary=(
                    f"mode={knowledge_route.mode}; "
                    f"knowledge_bases={len(knowledge_route.knowledge_base_ids)}"
                )
            )

        if knowledge_route.mode in {"mcp", "mixed"} and knowledge_route.mcp_tool_ids:
            with self.trace_service.span(
                name="mcp.execute.intent_route",
                node_type="MCP",
                input_summary=" | ".join(route_queries)[:120],
                metadata={"mcp_tool_ids": knowledge_route.mcp_tool_ids},
            ) as span:
                mcp_result = self._execute_mcp_queries(
                    original_question=question,
                    rewritten_queries=rewritten_queries,
                    memory_messages=memory_messages,
                    forced_tool_ids=knowledge_route.mcp_tool_ids,
                    forced_tool_param_prompts=self._resolve_mcp_param_prompt_templates(knowledge_route),
                )
                span.finish_success(output_summary=f"calls={len(mcp_result.calls)}")
            mcp_calls = [
                ChatMcpCallItem(
                    tool_id=call.tool_id,
                    arguments=call.arguments,
                    content=call.content,
                    is_error=call.is_error,
                    sources=call.sources,
                )
                for call in mcp_result.calls
            ]

        if knowledge_route.mode == "knowledge_base":
            guidance_decision = self.guidance_service.detect(intent_question, knowledge_route)
            if guidance_decision.is_prompt:
                return PreparedWorkflowContext(
                    intent="clarification",
                    intent_confidence=knowledge_route.confidence,
                    intent_reason=knowledge_route.reason,
                    intent_source="route-guidance",
                    rewritten_queries=rewritten_queries,
                    pipeline_stages=["memory", "rewrite", "intent", "route", "generation"],
                    route_mode="clarification",
                    route_confidence=knowledge_route.confidence,
                    route_top_k=self._resolve_route_top_k(knowledge_route),
                    route_candidates=route_candidates,
                    retrieval_channels=[],
                    retrieval_stage_counts={},
                    retrieval_stage_metrics={},
                    sources=[],
                    extra_context="",
                    mcp_calls=mcp_calls,
                    assistant_message_override=guidance_decision.prompt,
                )
            retrieval_result = self.retrieval_engine.retrieve(
                intent_question,
                queries=rewritten_queries,
                knowledge_base_ids=knowledge_route.knowledge_base_ids,
                top_k_override=self._resolve_route_top_k(knowledge_route),
                top_k_by_knowledge_base=self._resolve_route_top_k_by_knowledge_base(knowledge_route),
                min_score_by_knowledge_base=self._resolve_route_min_score_by_knowledge_base(knowledge_route),
            )
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "rewrite", "intent", "route", "retrieval", "mcp", "generation"],
                route_mode="mixed" if mcp_calls else "knowledge_base",
                route_confidence=knowledge_route.confidence,
                route_top_k=self._resolve_route_top_k(knowledge_route),
                route_candidates=route_candidates,
                retrieval_channels=retrieval_result.channels,
                retrieval_stage_counts=retrieval_result.stage_counts,
                retrieval_stage_metrics=retrieval_result.stage_metrics,
                sources=retrieval_result.sources,
                extra_context=mcp_result.context,
                mcp_calls=mcp_calls,
            )

        if knowledge_route.mode == "mixed":
            retrieval_result = self.retrieval_engine.retrieve(
                intent_question,
                queries=rewritten_queries,
                knowledge_base_ids=knowledge_route.knowledge_base_ids,
                top_k_override=self._resolve_route_top_k(knowledge_route),
                top_k_by_knowledge_base=self._resolve_route_top_k_by_knowledge_base(knowledge_route),
                min_score_by_knowledge_base=self._resolve_route_min_score_by_knowledge_base(knowledge_route),
            )
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "rewrite", "intent", "route", "retrieval", "mcp", "generation"],
                route_mode="mixed",
                route_confidence=knowledge_route.confidence,
                route_top_k=self._resolve_route_top_k(knowledge_route),
                route_candidates=route_candidates,
                retrieval_channels=retrieval_result.channels,
                retrieval_stage_counts=retrieval_result.stage_counts,
                retrieval_stage_metrics=retrieval_result.stage_metrics,
                sources=retrieval_result.sources,
                extra_context=mcp_result.context,
                mcp_calls=mcp_calls,
            )

        if knowledge_route.mode == "mcp":
            return PreparedWorkflowContext(
                intent="tool_call",
                intent_confidence=knowledge_route.confidence,
                intent_reason=knowledge_route.reason,
                intent_source="route-mcp",
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "rewrite", "intent", "route", "mcp", "generation"],
                route_mode="mcp_only",
                route_confidence=knowledge_route.confidence,
                route_top_k=None,
                route_candidates=route_candidates,
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context=mcp_result.context,
                mcp_calls=mcp_calls,
            )

        if intent_decision.intent == "tool_call":
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "rewrite", "intent", "route", "mcp", "generation"],
                route_mode="mcp_only",
                route_confidence=0.0,
                route_top_k=None,
                route_candidates=[],
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context=mcp_result.context,
                mcp_calls=mcp_calls,
            )

        if mcp_calls:
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "rewrite", "intent", "route", "mcp", "generation"],
                route_mode="mcp_only",
                route_confidence=0.0,
                route_top_k=None,
                route_candidates=[],
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context=mcp_result.context,
                mcp_calls=mcp_calls,
            )

        retrieval_result = self.retrieval_engine.retrieve(intent_question, queries=rewritten_queries)
        return PreparedWorkflowContext(
            intent=intent_decision.intent,
            intent_confidence=intent_decision.confidence,
            intent_reason=intent_decision.reason,
            intent_source=intent_decision.source,
            rewritten_queries=rewritten_queries,
            pipeline_stages=["memory", "rewrite", "intent", "route", "retrieval", "generation"],
            route_mode="global",
            route_confidence=0.0,
            route_top_k=None,
            route_candidates=[],
            retrieval_channels=retrieval_result.channels,
            retrieval_stage_counts=retrieval_result.stage_counts,
            retrieval_stage_metrics=retrieval_result.stage_metrics,
            sources=retrieval_result.sources,
            extra_context="",
            mcp_calls=[],
        )

    def _generate_answer(
        self,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str,
        mcp_calls: list[ChatMcpCallItem],
        memory_messages: list[dict[str, str]],
        assistant_message_override: str,
        intent: str,
        deep_thinking: bool = False,
    ) -> str:
        with self.trace_service.span(
            name="generation.answer",
            node_type="GENERATION",
            input_summary=f"intent={intent}; sources={len(sources)}",
        ) as span:
            if assistant_message := self._resolve_override_answer(
                question=question,
                memory_messages=memory_messages,
                sources=sources,
                assistant_message_override=assistant_message_override,
                intent=intent,
            ):
                span.finish_success(output_summary="override")
                return assistant_message
            try:
                raw_answer = self.llm_service.generate_answer(
                    question=question,
                    sources=sources,
                    extra_context=extra_context,
                    memory_messages=memory_messages,
                    deep_thinking=deep_thinking,
                )
            except Exception:
                raw_answer = self._build_fallback_answer(
                    question=question,
                    sources=sources,
                    mcp_calls=mcp_calls,
                )
            final_answer = self.answer_postprocessor.finalize(raw_answer, sources)
            span.finish_success(output_summary=f"chars={len(final_answer)}")
            return final_answer

    @staticmethod
    def _default_pipeline_stages(context: PreparedWorkflowContext) -> list[str]:
        stages = ["memory", "intent"]
        if context.mcp_calls:
            stages.append("mcp")
        if context.rewritten_queries:
            stages.append("rewrite")
        if context.route_mode not in {"chitchat", "clarification"}:
            stages.append("route")
        if context.sources:
            stages.append("retrieval")
        stages.append("generation")
        return stages

    def _safe_stream_answer(
        self,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str,
        mcp_calls: list[ChatMcpCallItem],
        memory_messages: list[dict[str, str]],
        assistant_message_override: str,
        intent: str,
        deep_thinking: bool = False,
    ) -> Iterable[str]:
        span = self.trace_service.begin_stream_span(
            name="generation.answer",
            node_type="GENERATION",
            input_summary=f"intent={intent}; sources={len(sources)}; stream=true",
        )
        try:
            override = self._resolve_override_answer(
                question=question,
                memory_messages=memory_messages,
                sources=sources,
                assistant_message_override=assistant_message_override,
                intent=intent,
            )
            if override:
                span.detach()
                return TracedAnswerDeltaIterator(
                    span=span,
                    source=iter([override]),
                    fallback_factory=lambda: override,
                    success_prefix="override",
                )

            stream = self.llm_service.stream_answer(
                question=question,
                sources=sources,
                extra_context=extra_context,
                memory_messages=memory_messages,
                deep_thinking=deep_thinking,
            )
            span.detach()
        except BaseException as exc:
            span.finish_error(exc)
            raise

        return TracedAnswerDeltaIterator(
            span=span,
            source=stream,
            fallback_factory=lambda: self._build_fallback_answer(
                question=question,
                sources=sources,
                mcp_calls=mcp_calls,
            ),
        )

    def _resolve_override_answer(
        self,
        *,
        question: str,
        memory_messages: list[dict[str, str]],
        sources: list[ChatSourceItem],
        assistant_message_override: str,
        intent: str,
    ) -> str:
        if assistant_message_override.strip():
            return assistant_message_override.strip()
        if answer := self._build_assessment_count_answer(question=question, sources=sources):
            return answer
        if intent != "chitchat":
            return ""
        try:
            return self.llm_service.generate_general_answer(
                question=question,
                memory_messages=memory_messages,
            )
        except Exception:
            return "你好，我在。你可以直接告诉我想查询、分析或处理的问题。"

    @staticmethod
    @staticmethod
    def _build_assessment_count_answer(*, question: str, sources: list[ChatSourceItem]) -> str:
        normalized_question = re.sub(r"\s+", "", question)
        asks_count = (
            ("道" in normalized_question and any(token in normalized_question for token in ("多少", "几", "有几", "有多少", "共", "总共")))
            or (
                any(token in normalized_question for token in ("多少", "有几", "有多少", "共几", "总共"))
                and any(token in normalized_question for token in ("题", "小题", "复习题", "试题", "练习题"))
            )
        )
        if not asks_count:
            return ""

        for index, source in enumerate(sources, start=1):
            content = source.content.strip()
            if "题目统计线索" not in content:
                continue
            total_match = re.search(r"合计：\s*(\d+)\s*小题", content)
            if not total_match:
                continue
            detail_lines = []
            for label, count in re.findall(r"-\s*([^：\n]+)：\s*(\d+)\s*小题", content):
                detail_lines.append(f"{label}{count}小题")
            details = "，".join(detail_lines)
            if details:
                return f"根据参考资料统计，复习题共 {total_match.group(1)} 道小题，其中{details}。[{index}]"
            return f"根据参考资料统计，复习题共 {total_match.group(1)} 道小题。[{index}]"

        return ""
    def _rewrite_queries(
        self,
        *,
        question: str,
        memory_messages: list[dict[str, str]],
    ) -> list[str]:
        try:
            queries = self.query_rewrite_service.rewrite(
                history_messages=memory_messages,
                query=question,
            )
        except Exception:
            queries = [question]
        return [item.strip() for item in queries if item.strip()] or [question]

    @staticmethod
    def _primary_query(*, question: str, rewritten_queries: list[str]) -> str:
        return next((item for item in rewritten_queries if item.strip()), question).strip() or question

    def _execute_mcp_queries(
        self,
        *,
        rewritten_queries: list[str],
        memory_messages: list[dict[str, str]],
        original_question: str = "",
        forced_tool_ids: list[str] | None = None,
        forced_tool_param_prompts: dict[str, str] | None = None,
    ):
        from modules.mcp.models import McpExecutionResult, McpRouteDecision

        calls = []
        selected_tool_ids: list[str] = []
        reasons: list[str] = []
        confidence = 0.0
        query_candidates = self._mcp_query_candidates(
            original_question=original_question,
            rewritten_queries=rewritten_queries,
        )
        for query in query_candidates:
            result = self.mcp_service.execute_question(
                query,
                memory_messages=memory_messages,
                forced_tool_ids=forced_tool_ids,
                forced_tool_param_prompts=forced_tool_param_prompts,
            )
            if result.route.mode == "mcp":
                confidence = max(confidence, result.route.confidence)
                reasons.append(result.route.reason)
                for tool_id in result.route.tool_ids:
                    if tool_id not in selected_tool_ids:
                        selected_tool_ids.append(tool_id)
            for call in result.calls:
                key = (call.tool_id, tuple(sorted((str(k), str(v)) for k, v in call.arguments.items())))
                if any(
                    key == (existing.tool_id, tuple(sorted((str(k), str(v)) for k, v in existing.arguments.items())))
                    for existing in calls
                ):
                    continue
                calls.append(call)

        route = McpRouteDecision(
            mode="mcp" if calls else "none",
            tool_ids=selected_tool_ids,
            confidence=confidence,
            reason="; ".join(reason for reason in reasons if reason) or "no matched mcp tool",
        )
        return McpExecutionResult(route=route, calls=calls)

    @staticmethod
    def _mcp_query_candidates(*, original_question: str, rewritten_queries: list[str]) -> list[str]:
        candidates: list[str] = []
        for query in [original_question, *rewritten_queries]:
            normalized = query.strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates or [original_question]

    def _classify_intent(
        self,
        *,
        question: str,
        memory_messages: list[dict[str, str]],
    ) -> IntentDecision:
        try:
            decision = self.intent_classifier.classify(
                question=question,
                memory_messages=memory_messages,
            )
        except Exception:
            decision = IntentDecision(
                intent="knowledge_retrieval",
                confidence=0.0,
                reason="intent classifier unavailable",
                source="fallback",
            )

        if isinstance(decision, IntentDecision):
            return self._guard_clarification_intent(
                question=question,
                memory_messages=memory_messages,
                decision=decision,
            )

        normalized_decision = IntentDecision(
            intent=str(decision.get("intent", "knowledge_retrieval")),
            confidence=float(decision.get("confidence", 0.0)),
            reason=str(decision.get("reason", "")),
            source=str(decision.get("source", "fallback")),
            clarification_question=str(decision.get("clarification_question", "")),
        )
        return self._guard_clarification_intent(
            question=question,
            memory_messages=memory_messages,
            decision=normalized_decision,
        )

    @staticmethod
    def _guard_clarification_intent(
        *,
        question: str,
        memory_messages: list[dict[str, str]],
        decision: IntentDecision,
    ) -> IntentDecision:
        if decision.intent != "clarification":
            return decision
        if decision.source == "rule":
            return decision
        if RetriFlowIntentClassifier._looks_like_missing_context(
            question=question,
            memory_messages=memory_messages,
        ):
            return decision

        return IntentDecision(
            intent="knowledge_retrieval",
            confidence=decision.confidence,
            reason=f"overrode non-referential clarification: {decision.reason}",
            source=decision.source,
            clarification_question="",
        )

    def _build_fallback_answer(
        self,
        question: str,
        sources: list[ChatSourceItem],
        mcp_calls: list[ChatMcpCallItem],
    ) -> str:
        if not mcp_calls and not sources:
            return RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER

        segments: list[str] = []

        if mcp_calls:
            tool_summary = "；".join(call.content.strip() for call in mcp_calls if call.content.strip())
            if tool_summary:
                segments.append(tool_summary)

        if sources:
            source = sources[0]
            segments.append(f"参考资料《{source.document_title}》提到：{source.content}")

        fallback = " ".join(segments).strip()
        return fallback or RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER

    @staticmethod
    def _resolve_local_date_answer(question: str) -> str:
        normalized = re.sub(r"\s+", "", question.strip().lower())
        if not normalized:
            return ""
        if LangGraphWorkflowAdapter._has_explicit_web_intent(normalized):
            return ""
        if not re.search(r"(今天|今日|现在).{0,4}(几号|日期|星期|周几)|今天是几号|今天日期", normalized):
            return ""
        now = datetime.now().astimezone()
        weekday = "一二三四五六日"[now.weekday()]
        return f"今天是 {now.year} 年 {now.month} 月 {now.day} 日，星期{weekday}。"

    @staticmethod
    def _resolve_local_assistant_answer(question: str) -> str:
        normalized = re.sub(r"\s+", "", question.strip().lower())
        if not normalized:
            return ""
        if not re.search(r"你是谁|助手.*(做什么|是谁|能力|功能)|你能做什么|能做什么|有什么功能|介绍一下你|retriflow.*(是什么|能做什么)", normalized):
            return ""
        return (
            "我是 RetriFlow 智能知识助手，主要负责把你的问题路由到合适的处理链路："
            "可以做知识库问答、文档内容检索与来源引用、上下文续问理解、问题重写/拆分、"
            "深度思考回答，以及在开启智能搜索时调用联网搜索或天气 MCP 获取实时信息。"
            "如果你问的是已入库资料，我会优先依据知识库回答；如果是实时信息，可以打开输入框下方的“智能搜索”。"
        )

    @staticmethod
    def _has_explicit_web_intent(question: str) -> bool:
        normalized = re.sub(r"\s+", "", question.strip().lower())
        return any(
            token in normalized
            for token in (
                "联网",
                "搜索",
                "网页",
                "浏览器",
                "用mcp",
                "走mcp",
                "网上查",
                "上网查",
                "上网搜索",
                "联网搜索",
                "查网页",
                "百度",
                "最新",
                "实时",
                "today",
                "search",
                "web",
            )
        )

    def _resolve_route(self, question: str) -> KnowledgeRouteDecision:
        decision = self.route_service.route_question(question)
        return self._normalize_route_decision(decision)

    def _resolve_routes(self, questions: list[str]) -> KnowledgeRouteDecision:
        route_questions = [question for question in questions if question.strip()]
        if not route_questions:
            route_questions = [""]

        decisions = [self._resolve_route(question) for question in route_questions]
        selected_ids: list[str] = []
        selected_candidates: list[KnowledgeRouteCandidate] = []
        selected_mcp_tool_ids: list[str] = []
        reasons: list[str] = []
        best_confidence = 0.0
        for index, decision in enumerate(decisions):
            best_confidence = max(best_confidence, decision.confidence)
            if decision.reason:
                reasons.append(f"q{index + 1}: {decision.reason}")
            for tool_id in decision.mcp_tool_ids:
                if tool_id not in selected_mcp_tool_ids:
                    selected_mcp_tool_ids.append(tool_id)
            for candidate in decision.candidates:
                if not candidate.knowledge_base_id and not candidate.mcp_tool_id:
                    continue
                if candidate.knowledge_base_id and candidate.knowledge_base_id in {item.knowledge_base_id for item in selected_candidates if item.knowledge_base_id}:
                    continue
                if candidate.mcp_tool_id and candidate.mcp_tool_id in {item.mcp_tool_id for item in selected_candidates if item.mcp_tool_id}:
                    continue
                selected_candidates.append(candidate)
                if len(selected_candidates) >= 3:
                    break
            if decision.mode not in {"knowledge_base", "mixed"}:
                continue
            for knowledge_base_id in decision.knowledge_base_ids:
                if knowledge_base_id in selected_ids:
                    continue
                selected_ids.append(knowledge_base_id)
                if len(selected_ids) >= 3:
                    break
            if len(selected_ids) >= 3:
                break

        if selected_ids or selected_mcp_tool_ids:
            return KnowledgeRouteDecision(
                mode="mixed" if selected_ids and selected_mcp_tool_ids else "mcp" if selected_mcp_tool_ids else "knowledge_base",
                knowledge_base_ids=selected_ids,
                confidence=min(best_confidence, 0.99),
                reason=" | ".join(reasons),
                candidates=selected_candidates,
                mcp_tool_ids=selected_mcp_tool_ids,
            )

        first_decision = decisions[0]
        return KnowledgeRouteDecision(
            mode="global",
            knowledge_base_ids=[],
            confidence=best_confidence,
            reason=" | ".join(reasons) or first_decision.reason,
            candidates=[],
            mcp_tool_ids=[],
        )

    @staticmethod
    def _resolve_route_top_k(decision: KnowledgeRouteDecision) -> int | None:
        top_k_values = [
            int(candidate.top_k)
            for candidate in decision.candidates
            if candidate.top_k is not None and int(candidate.top_k) > 0
        ]
        if not top_k_values:
            return None
        return max(top_k_values)

    @staticmethod
    def _resolve_route_top_k_by_knowledge_base(decision: KnowledgeRouteDecision) -> dict[str, int]:
        return {
            candidate.knowledge_base_id: int(candidate.top_k)
            for candidate in decision.candidates
            if candidate.top_k is not None and int(candidate.top_k) > 0
        }

    @staticmethod
    def _resolve_route_min_score_by_knowledge_base(decision: KnowledgeRouteDecision) -> dict[str, float]:
        return {
            candidate.knowledge_base_id: float(candidate.min_score)
            for candidate in decision.candidates
            if candidate.min_score is not None and float(candidate.min_score) > 0
        }

    @staticmethod
    def _resolve_mcp_param_prompt_templates(decision: KnowledgeRouteDecision) -> dict[str, str]:
        return {
            candidate.mcp_tool_id: candidate.param_prompt_template
            for candidate in decision.candidates
            if candidate.mcp_tool_id and candidate.param_prompt_template.strip()
        }

    @staticmethod
    def _normalize_route_decision(decision) -> KnowledgeRouteDecision:
        if isinstance(decision, KnowledgeRouteDecision):
            return decision
        return KnowledgeRouteDecision(
            mode=str(decision.get("mode", "global")),
            knowledge_base_ids=[str(item) for item in decision.get("knowledge_base_ids", [])],
            confidence=float(decision.get("confidence", 0.0)),
            reason=str(decision.get("reason", "")),
            candidates=[],
            mcp_tool_ids=[str(item) for item in decision.get("mcp_tool_ids", [])],
        )


def resolve_workflow_adapter() -> WorkflowAdapter:
    return LangGraphWorkflowAdapter()
