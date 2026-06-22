from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

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

    def run(self, question: str, *, session_id: str = "", deep_thinking: bool = False) -> WorkflowAdapterResult:
        raise NotImplementedError

    def stream(self, question: str, *, session_id: str = "", deep_thinking: bool = False) -> WorkflowStreamAdapterResult:
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

    def run(self, question: str, *, session_id: str = "", deep_thinking: bool = False) -> WorkflowAdapterResult:
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
        context = self._prepare_context(question, memory_messages=memory_messages)
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
            mcp_calls=context.mcp_calls or [],
        )

    def stream(self, question: str, *, session_id: str = "", deep_thinking: bool = False) -> WorkflowStreamAdapterResult:
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
        context = self._prepare_context(question, memory_messages=memory_messages)
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
            mcp_calls=context.mcp_calls or [],
        )

    def _prepare_context(
        self,
        question: str,
        *,
        memory_messages: list[dict[str, str]],
    ) -> PreparedWorkflowContext:
        with self.trace_service.span(
            name="intent-resolve",
            node_type="INTENT",
            input_summary=question[:120],
        ) as span:
            intent_decision = self._classify_intent(
                question=question,
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
                rewritten_queries=[],
                pipeline_stages=["memory", "intent", "generation"],
                route_mode="clarification",
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context="",
                mcp_calls=[],
                assistant_message_override=(
                    intent_decision.clarification_question
                    or "可以再具体说明一下你指的是哪一部分吗？"
                ),
            )

        if intent_decision.intent == "chitchat":
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=[],
                pipeline_stages=["memory", "intent", "generation"],
                route_mode="chitchat",
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
            input_summary=question[:120],
        ) as span:
            mcp_result = self.mcp_service.execute_question(question)
            span.finish_success(output_summary=f"calls={len(mcp_result.calls)}")
        mcp_calls = [
            ChatMcpCallItem(
                tool_id=call.tool_id,
                arguments=call.arguments,
                content=call.content,
                is_error=call.is_error,
            )
            for call in mcp_result.calls
        ]

        if intent_decision.intent == "tool_call":
            rewritten_queries: list[str] = []
        else:
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

        route_queries = rewritten_queries or [question]
        with self.trace_service.span(
            name="knowledge.route",
            node_type="ROUTE",
            input_summary=" | ".join(route_queries)[:120],
        ) as span:
            knowledge_route = self._resolve_routes(route_queries)
            span.finish_success(
                output_summary=(
                    f"mode={knowledge_route.mode}; "
                    f"knowledge_bases={len(knowledge_route.knowledge_base_ids)}"
                )
        )

        if knowledge_route.mode == "knowledge_base":
            guidance_decision = self.guidance_service.detect(question, knowledge_route)
            if guidance_decision.is_prompt:
                return PreparedWorkflowContext(
                    intent="clarification",
                    intent_confidence=knowledge_route.confidence,
                    intent_reason=knowledge_route.reason,
                    intent_source="route-guidance",
                    rewritten_queries=rewritten_queries,
                    pipeline_stages=["memory", "intent", "mcp", "rewrite", "route", "generation"],
                    route_mode="clarification",
                    retrieval_channels=[],
                    retrieval_stage_counts={},
                    retrieval_stage_metrics={},
                    sources=[],
                    extra_context="",
                    mcp_calls=mcp_calls,
                    assistant_message_override=guidance_decision.prompt,
                )
            retrieval_result = self.retrieval_engine.retrieve(
                question,
                queries=rewritten_queries,
                knowledge_base_ids=knowledge_route.knowledge_base_ids,
            )
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=rewritten_queries,
                pipeline_stages=["memory", "intent", "mcp", "rewrite", "route", "retrieval", "generation"],
                route_mode="mixed" if mcp_calls else "knowledge_base",
                retrieval_channels=retrieval_result.channels,
                retrieval_stage_counts=retrieval_result.stage_counts,
                retrieval_stage_metrics=retrieval_result.stage_metrics,
                sources=retrieval_result.sources,
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
                pipeline_stages=["memory", "intent", "mcp", "generation"],
                route_mode="mcp_only",
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
                pipeline_stages=["memory", "intent", "mcp", "rewrite", "route", "generation"],
                route_mode="mcp_only",
                retrieval_channels=[],
                retrieval_stage_counts={},
                retrieval_stage_metrics={},
                sources=[],
                extra_context=mcp_result.context,
                mcp_calls=mcp_calls,
            )

        retrieval_result = self.retrieval_engine.retrieve(question, queries=rewritten_queries)
        return PreparedWorkflowContext(
            intent=intent_decision.intent,
            intent_confidence=intent_decision.confidence,
            intent_reason=intent_decision.reason,
            intent_source=intent_decision.source,
            rewritten_queries=rewritten_queries,
            pipeline_stages=["memory", "intent", "rewrite", "route", "retrieval", "generation"],
            route_mode="global",
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
        if intent != "chitchat":
            return ""
        try:
            return self.llm_service.generate_general_answer(
                question=question,
                memory_messages=memory_messages,
            )
        except Exception:
            return RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER if not sources else ""

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
            return decision

        return IntentDecision(
            intent=str(decision.get("intent", "knowledge_retrieval")),
            confidence=float(decision.get("confidence", 0.0)),
            reason=str(decision.get("reason", "")),
            source=str(decision.get("source", "fallback")),
            clarification_question=str(decision.get("clarification_question", "")),
        )

    def _build_fallback_answer(
        self,
        question: str,
        sources: list[ChatSourceItem],
        mcp_calls: list[ChatMcpCallItem],
    ) -> str:
        if not mcp_calls and not sources:
            return RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER

        segments = [f"收到你的问题：{question}。"]

        if mcp_calls:
            tool_summary = "；".join(call.content.strip() for call in mcp_calls if call.content.strip())
            if tool_summary:
                segments.append(f"工具结果显示：{tool_summary}")

        if sources:
            source = sources[0]
            segments.append(f"参考资料《{source.document_title}》提到：{source.content}")

        fallback = " ".join(segments).strip()
        return fallback or RetriFlowAnswerPostprocessor.DEFAULT_NO_ANSWER

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
        reasons: list[str] = []
        best_confidence = 0.0
        for index, decision in enumerate(decisions):
            best_confidence = max(best_confidence, decision.confidence)
            if decision.reason:
                reasons.append(f"q{index + 1}: {decision.reason}")
            if decision.mode != "knowledge_base":
                continue
            for candidate in decision.candidates:
                if candidate.knowledge_base_id in {item.knowledge_base_id for item in selected_candidates}:
                    continue
                selected_candidates.append(candidate)
                if len(selected_candidates) >= 3:
                    break
            for knowledge_base_id in decision.knowledge_base_ids:
                if knowledge_base_id in selected_ids:
                    continue
                selected_ids.append(knowledge_base_id)
                if len(selected_ids) >= 3:
                    break
            if len(selected_ids) >= 3:
                break

        if selected_ids:
            return KnowledgeRouteDecision(
                mode="knowledge_base",
                knowledge_base_ids=selected_ids,
                confidence=min(best_confidence, 0.99),
                reason=" | ".join(reasons),
                candidates=selected_candidates,
            )

        first_decision = decisions[0]
        return KnowledgeRouteDecision(
            mode="global",
            knowledge_base_ids=[],
            confidence=best_confidence,
            reason=" | ".join(reasons) or first_decision.reason,
            candidates=[],
        )

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
        )


def resolve_workflow_adapter() -> WorkflowAdapter:
    return LangGraphWorkflowAdapter()
