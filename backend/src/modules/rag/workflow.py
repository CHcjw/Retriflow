from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from modules.rag.trace import RetriFlowTraceService
from modules.rag.workflow_adapter import resolve_workflow_adapter
from schemas.chat import ChatMcpCallItem, ChatSourceItem, ChatWorkflowMetadata


@dataclass
class WorkflowResult:
    assistant_message: str
    sources: list[ChatSourceItem]
    workflow: ChatWorkflowMetadata
    mcp_calls: list[ChatMcpCallItem]


@dataclass
class WorkflowStreamResult:
    sources: list[ChatSourceItem]
    workflow: ChatWorkflowMetadata
    deltas: Iterable[str]
    mcp_calls: list[ChatMcpCallItem]


class RetriFlowChatWorkflow:
    def __init__(self) -> None:
        self.adapter = resolve_workflow_adapter()
        self.trace_service = RetriFlowTraceService()

    def run(self, question: str, *, session_id: str = "", deep_thinking: bool = False) -> WorkflowResult:
        with self.trace_service.start_root(
            session_id=session_id,
            task_id="chat",
            name="chat.run",
        ) as trace_root:
            adapter_result = self.adapter.run(question, session_id=session_id, deep_thinking=deep_thinking)
            trace_root.finish_success(
                output_summary=(
                    f"intent={adapter_result.intent}; "
                    f"route={adapter_result.route_mode}; "
                    f"sources={len(adapter_result.sources)}"
                )
            )
        return WorkflowResult(
            assistant_message=adapter_result.assistant_message,
            sources=adapter_result.sources,
            workflow=self._build_metadata(
                adapter=adapter_result.adapter,
                intent=adapter_result.intent,
                intent_confidence=adapter_result.intent_confidence,
                intent_reason=adapter_result.intent_reason,
                intent_source=adapter_result.intent_source,
                channels=adapter_result.retrieval_channels,
                stage_counts=adapter_result.retrieval_stage_counts,
                stage_metrics=adapter_result.retrieval_stage_metrics,
                rewritten_queries=adapter_result.rewritten_queries,
                pipeline_stages=adapter_result.pipeline_stages,
                sources=adapter_result.sources,
                route_mode=adapter_result.route_mode,
                mcp_calls=adapter_result.mcp_calls,
                deep_thinking=deep_thinking,
            ),
            mcp_calls=adapter_result.mcp_calls,
        )

    def stream(self, question: str, *, session_id: str = "", deep_thinking: bool = False) -> WorkflowStreamResult:
        if self.trace_service.has_active_trace():
            adapter_result = self.adapter.stream(question, session_id=session_id, deep_thinking=deep_thinking)
            return WorkflowStreamResult(
                sources=adapter_result.sources,
                workflow=self._build_metadata(
                    adapter=adapter_result.adapter,
                    intent=adapter_result.intent,
                    intent_confidence=adapter_result.intent_confidence,
                    intent_reason=adapter_result.intent_reason,
                    intent_source=adapter_result.intent_source,
                    channels=adapter_result.retrieval_channels,
                    stage_counts=adapter_result.retrieval_stage_counts,
                    stage_metrics=adapter_result.retrieval_stage_metrics,
                    rewritten_queries=adapter_result.rewritten_queries,
                    pipeline_stages=adapter_result.pipeline_stages,
                    sources=adapter_result.sources,
                    route_mode=adapter_result.route_mode,
                    mcp_calls=adapter_result.mcp_calls,
                    deep_thinking=deep_thinking,
                ),
                deltas=adapter_result.deltas,
                mcp_calls=adapter_result.mcp_calls,
            )

        with self.trace_service.start_root(
            session_id=session_id,
            task_id="chat_stream",
            name="chat.stream",
        ) as trace_root:
            adapter_result = self.adapter.stream(question, session_id=session_id, deep_thinking=deep_thinking)
            trace_root.finish_success(
                output_summary=(
                    f"intent={adapter_result.intent}; "
                    f"route={adapter_result.route_mode}; "
                    f"sources={len(adapter_result.sources)}"
                )
            )
        return WorkflowStreamResult(
            sources=adapter_result.sources,
            workflow=self._build_metadata(
                adapter=adapter_result.adapter,
                intent=adapter_result.intent,
                intent_confidence=adapter_result.intent_confidence,
                intent_reason=adapter_result.intent_reason,
                intent_source=adapter_result.intent_source,
                channels=adapter_result.retrieval_channels,
                stage_counts=adapter_result.retrieval_stage_counts,
                stage_metrics=adapter_result.retrieval_stage_metrics,
                rewritten_queries=adapter_result.rewritten_queries,
                pipeline_stages=adapter_result.pipeline_stages,
                sources=adapter_result.sources,
                route_mode=adapter_result.route_mode,
                mcp_calls=adapter_result.mcp_calls,
                deep_thinking=deep_thinking,
            ),
            deltas=adapter_result.deltas,
            mcp_calls=adapter_result.mcp_calls,
        )

    @staticmethod
    def _build_metadata(
        adapter: str,
        intent: str,
        intent_confidence: float,
        intent_reason: str,
        intent_source: str,
        channels: list[str],
        stage_counts: dict[str, int],
        stage_metrics: dict[str, dict[str, object]],
        rewritten_queries: list[str],
        pipeline_stages: list[str],
        sources: list[ChatSourceItem],
        route_mode: str,
        mcp_calls: list[ChatMcpCallItem],
        deep_thinking: bool = False,
    ) -> ChatWorkflowMetadata:
        return ChatWorkflowMetadata(
            name="retriflow_langgraph_ready",
            adapter=adapter,
            intent=intent,
            intent_confidence=intent_confidence,
            intent_reason=intent_reason,
            intent_source=intent_source,
            retrieval_channels=channels,
            retrieval_count=len(sources),
            retrieval_stage_counts=stage_counts,
            retrieval_stage_metrics=stage_metrics,
            rewritten_queries=rewritten_queries,
            rewrite_query_count=len(rewritten_queries),
            pipeline_stages=pipeline_stages,
            route_mode=route_mode,
            mcp_tool_count=len(mcp_calls),
            deep_thinking=deep_thinking,
        )
