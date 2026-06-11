from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from domain.answer_postprocessor import RetriFlowAnswerPostprocessor
from domain.intent_classifier import IntentDecision, RetriFlowIntentClassifier
from domain.knowledge_route import KnowledgeRouteDecision, RetriFlowKnowledgeRouteService
from domain.llm import RetriFlowLLMService
from domain.memory import RetriFlowConversationMemoryService
from domain.mcp.service import RetriFlowMcpService
from domain.query_rewrite import RetriFlowQueryRewriteService
from domain.retrieval import RetriFlowRetrievalEngine
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
    rewritten_queries: list[str]
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
    rewritten_queries: list[str]
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
    route_mode: str = "global"
    retrieval_channels: list[str] | None = None
    retrieval_stage_counts: dict[str, int] | None = None
    sources: list[ChatSourceItem] | None = None
    extra_context: str = ""
    mcp_calls: list[ChatMcpCallItem] | None = None
    assistant_message_override: str = ""


class WorkflowAdapter:
    name = "langgraph"

    def run(self, question: str, *, session_id: str = "") -> WorkflowAdapterResult:
        raise NotImplementedError

    def stream(self, question: str, *, session_id: str = "") -> WorkflowStreamAdapterResult:
        raise NotImplementedError


class LangGraphWorkflowAdapter(WorkflowAdapter):
    name = "langgraph"

    def __init__(self) -> None:
        self.retrieval_engine = RetriFlowRetrievalEngine()
        self.intent_classifier = RetriFlowIntentClassifier()
        self.route_service = RetriFlowKnowledgeRouteService()
        self.mcp_service = RetriFlowMcpService()
        self.memory_service = RetriFlowConversationMemoryService()
        self.query_rewrite_service = RetriFlowQueryRewriteService()
        self.llm_service = RetriFlowLLMService()
        self.answer_postprocessor = RetriFlowAnswerPostprocessor()

    def run(self, question: str, *, session_id: str = "") -> WorkflowAdapterResult:
        memory_messages = self.memory_service.load_prompt_messages(
            session_id=session_id,
            query=question,
        )
        context = self._prepare_context(question, memory_messages=memory_messages)
        assistant_message = self._generate_answer(
            question=question,
            sources=context.sources or [],
            extra_context=context.extra_context,
            mcp_calls=context.mcp_calls or [],
            memory_messages=memory_messages,
            assistant_message_override=context.assistant_message_override,
            intent=context.intent,
        )
        return WorkflowAdapterResult(
            adapter=self.name,
            intent=context.intent,
            intent_confidence=context.intent_confidence,
            intent_reason=context.intent_reason,
            intent_source=context.intent_source,
            retrieval_channels=context.retrieval_channels or [],
            retrieval_stage_counts=context.retrieval_stage_counts or {},
            rewritten_queries=context.rewritten_queries or [],
            sources=context.sources or [],
            assistant_message=assistant_message,
            route_mode=context.route_mode,
            mcp_calls=context.mcp_calls or [],
        )

    def stream(self, question: str, *, session_id: str = "") -> WorkflowStreamAdapterResult:
        memory_messages = self.memory_service.load_prompt_messages(
            session_id=session_id,
            query=question,
        )
        context = self._prepare_context(question, memory_messages=memory_messages)
        return WorkflowStreamAdapterResult(
            adapter=self.name,
            intent=context.intent,
            intent_confidence=context.intent_confidence,
            intent_reason=context.intent_reason,
            intent_source=context.intent_source,
            retrieval_channels=context.retrieval_channels or [],
            retrieval_stage_counts=context.retrieval_stage_counts or {},
            rewritten_queries=context.rewritten_queries or [],
            sources=context.sources or [],
            deltas=self._safe_stream_answer(
                question=question,
                sources=context.sources or [],
                extra_context=context.extra_context,
                mcp_calls=context.mcp_calls or [],
                memory_messages=memory_messages,
                assistant_message_override=context.assistant_message_override,
                intent=context.intent,
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
        intent_decision = self._classify_intent(
            question=question,
            memory_messages=memory_messages,
        )

        if intent_decision.intent == "clarification":
            return PreparedWorkflowContext(
                intent=intent_decision.intent,
                intent_confidence=intent_decision.confidence,
                intent_reason=intent_decision.reason,
                intent_source=intent_decision.source,
                rewritten_queries=[],
                route_mode="clarification",
                retrieval_channels=[],
                retrieval_stage_counts={},
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
                route_mode="chitchat",
                retrieval_channels=[],
                retrieval_stage_counts={},
                sources=[],
                extra_context="",
                mcp_calls=[],
            )

        mcp_result = self.mcp_service.execute_question(question)
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
            rewritten_queries = self._rewrite_queries(
                question=question,
                memory_messages=memory_messages,
            )

        route_query = rewritten_queries[0] if rewritten_queries else question
        knowledge_route = self._resolve_route(route_query)

        if knowledge_route.mode == "knowledge_base":
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
                route_mode="mixed" if mcp_calls else "knowledge_base",
                retrieval_channels=retrieval_result.channels,
                retrieval_stage_counts=retrieval_result.stage_counts,
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
                route_mode="mcp_only",
                retrieval_channels=[],
                retrieval_stage_counts={},
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
                route_mode="mcp_only",
                retrieval_channels=[],
                retrieval_stage_counts={},
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
            route_mode="global",
            retrieval_channels=retrieval_result.channels,
            retrieval_stage_counts=retrieval_result.stage_counts,
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
    ) -> str:
        if assistant_message := self._resolve_override_answer(
            question=question,
            memory_messages=memory_messages,
            sources=sources,
            assistant_message_override=assistant_message_override,
            intent=intent,
        ):
            return assistant_message
        try:
            raw_answer = self.llm_service.generate_answer(
                question=question,
                sources=sources,
                extra_context=extra_context,
                memory_messages=memory_messages,
            )
        except Exception:
            raw_answer = self._build_fallback_answer(
                question=question,
                sources=sources,
                mcp_calls=mcp_calls,
            )
        return self.answer_postprocessor.finalize(raw_answer, sources)

    def _safe_stream_answer(
        self,
        question: str,
        sources: list[ChatSourceItem],
        extra_context: str,
        mcp_calls: list[ChatMcpCallItem],
        memory_messages: list[dict[str, str]],
        assistant_message_override: str,
        intent: str,
    ) -> Iterable[str]:
        override = self._resolve_override_answer(
            question=question,
            memory_messages=memory_messages,
            sources=sources,
            assistant_message_override=assistant_message_override,
            intent=intent,
        )
        if override:
            return iter([override])

        stream = self.llm_service.stream_answer(
            question=question,
            sources=sources,
            extra_context=extra_context,
            memory_messages=memory_messages,
        )

        def iterator() -> Iterable[str]:
            yielded_any = False
            try:
                for delta in stream:
                    yielded_any = True
                    yield delta
            except Exception:
                yield self._build_fallback_answer(
                    question=question,
                    sources=sources,
                    mcp_calls=mcp_calls,
                )
                return

            if not yielded_any:
                yield self._build_fallback_answer(
                    question=question,
                    sources=sources,
                    mcp_calls=mcp_calls,
                )

        return iterator()

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
        if isinstance(decision, KnowledgeRouteDecision):
            return decision
        return KnowledgeRouteDecision(
            mode=str(decision.get("mode", "global")),
            knowledge_base_ids=[str(item) for item in decision.get("knowledge_base_ids", [])],
            confidence=float(decision.get("confidence", 0.0)),
            reason=str(decision.get("reason", "")),
        )


def resolve_workflow_adapter() -> WorkflowAdapter:
    return LangGraphWorkflowAdapter()
