from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from domain.workflow_adapter import resolve_workflow_adapter
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

    def run(self, question: str, *, session_id: str = "") -> WorkflowResult:
        adapter_result = self.adapter.run(question, session_id=session_id)
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
                rewritten_queries=adapter_result.rewritten_queries,
                sources=adapter_result.sources,
                route_mode=adapter_result.route_mode,
                mcp_calls=adapter_result.mcp_calls,
            ),
            mcp_calls=adapter_result.mcp_calls,
        )

    def stream(self, question: str, *, session_id: str = "") -> WorkflowStreamResult:
        adapter_result = self.adapter.stream(question, session_id=session_id)
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
                rewritten_queries=adapter_result.rewritten_queries,
                sources=adapter_result.sources,
                route_mode=adapter_result.route_mode,
                mcp_calls=adapter_result.mcp_calls,
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
        rewritten_queries: list[str],
        sources: list[ChatSourceItem],
        route_mode: str,
        mcp_calls: list[ChatMcpCallItem],
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
            rewritten_queries=rewritten_queries,
            rewrite_query_count=len(rewritten_queries),
            route_mode=route_mode,
            mcp_tool_count=len(mcp_calls),
        )
