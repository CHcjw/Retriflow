from collections.abc import Iterable
from dataclasses import dataclass

from schemas.chat import ChatSourceItem, ChatWorkflowMetadata

from domain.workflow_adapter import resolve_workflow_adapter


@dataclass
class WorkflowResult:
    assistant_message: str
    sources: list[ChatSourceItem]
    workflow: ChatWorkflowMetadata


@dataclass
class WorkflowStreamResult:
    sources: list[ChatSourceItem]
    workflow: ChatWorkflowMetadata
    deltas: Iterable[str]


class RetriFlowChatWorkflow:
    def __init__(self) -> None:
        self.adapter = resolve_workflow_adapter()

    def run(self, question: str) -> WorkflowResult:
        adapter_result = self.adapter.run(question)
        return WorkflowResult(
            assistant_message=adapter_result.assistant_message,
            sources=adapter_result.sources,
            workflow=self._build_metadata(
                adapter=adapter_result.adapter,
                channels=adapter_result.retrieval_channels,
                sources=adapter_result.sources,
            ),
        )

    def stream(self, question: str) -> WorkflowStreamResult:
        adapter_result = self.adapter.stream(question)
        return WorkflowStreamResult(
            sources=adapter_result.sources,
            workflow=self._build_metadata(
                adapter=adapter_result.adapter,
                channels=adapter_result.retrieval_channels,
                sources=adapter_result.sources,
            ),
            deltas=adapter_result.deltas,
        )

    @staticmethod
    def _build_metadata(
        adapter: str,
        channels: list[str],
        sources: list[ChatSourceItem],
    ) -> ChatWorkflowMetadata:
        return ChatWorkflowMetadata(
            name="retriflow_langgraph_ready",
            adapter=adapter,
            retrieval_channels=channels,
            retrieval_count=len(sources),
        )
