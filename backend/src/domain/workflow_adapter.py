import importlib.util
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, TypedDict

from core.config import get_settings
from domain.llm import RetriFlowLLMService
from domain.retrieval import RetriFlowRetrievalEngine
from schemas.chat import ChatSourceItem


@dataclass
class WorkflowAdapterResult:
    adapter: str
    retrieval_channels: list[str]
    sources: list[ChatSourceItem]
    assistant_message: str


@dataclass
class WorkflowStreamAdapterResult:
    adapter: str
    retrieval_channels: list[str]
    sources: list[ChatSourceItem]
    deltas: Iterable[str]


class WorkflowAdapter:
    name = "fallback"

    def run(self, question: str) -> WorkflowAdapterResult:
        raise NotImplementedError

    def stream(self, question: str) -> WorkflowStreamAdapterResult:
        result = self.run(question)
        return WorkflowStreamAdapterResult(
            adapter=result.adapter,
            retrieval_channels=result.retrieval_channels,
            sources=result.sources,
            deltas=[result.assistant_message],
        )


class FallbackWorkflowAdapter(WorkflowAdapter):
    name = "fallback"

    def __init__(self) -> None:
        self.retrieval_engine = RetriFlowRetrievalEngine()

    def run(self, question: str) -> WorkflowAdapterResult:
        retrieval_result = self.retrieval_engine.retrieve(question)
        assistant_message = self._build_answer(question=question, sources=retrieval_result.sources)
        return WorkflowAdapterResult(
            adapter=self.name,
            retrieval_channels=retrieval_result.channels,
            sources=retrieval_result.sources,
            assistant_message=assistant_message,
        )

    def stream(self, question: str) -> WorkflowStreamAdapterResult:
        retrieval_result = self.retrieval_engine.retrieve(question)
        assistant_message = self._build_answer(question=question, sources=retrieval_result.sources)
        return WorkflowStreamAdapterResult(
            adapter=self.name,
            retrieval_channels=retrieval_result.channels,
            sources=retrieval_result.sources,
            deltas=[assistant_message],
        )

    @staticmethod
    def _build_answer(question: str, sources: list[ChatSourceItem]) -> str:
        if sources:
            source = sources[0]
            return (
                f"RetriFlow received your question: {question}. "
                f"Based on document '{source.document_title}', the retrieved context says: {source.content}"
            )

        return (
            f"RetriFlow received your question: {question}. "
            "No matching knowledge chunk was found yet. Next we will replace this with a LangGraph answer pipeline."
        )


class LangGraphState(TypedDict):
    question: str
    sources: list[ChatSourceItem]
    retrieval_channels: list[str]
    retrieval_count: int
    assistant_message: str


class LangGraphWorkflowAdapter(WorkflowAdapter):
    name = "langgraph"

    def __init__(self) -> None:
        from langgraph.graph import END, START, StateGraph

        self.settings = get_settings()
        self.retrieval_engine = RetriFlowRetrievalEngine()
        self.llm_service = RetriFlowLLMService()
        self._traceable = self._resolve_traceable()

        workflow = StateGraph(LangGraphState)
        workflow.add_node(
            "retrieve",
            self._traceable(name="retriflow_retrieve", run_type="retriever")(self._retrieve_node),
        )
        workflow.add_node(
            "generate",
            self._traceable(name="retriflow_generate", run_type="chain")(self._generate_node),
        )
        workflow.add_edge(START, "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        self.graph = workflow.compile()

    def run(self, question: str) -> WorkflowAdapterResult:
        state = self.graph.invoke(
            {
                "question": question,
                "sources": [],
                "retrieval_channels": [],
                "retrieval_count": 0,
                "assistant_message": "",
            }
        )
        return WorkflowAdapterResult(
            adapter=self.name,
            retrieval_channels=list(state["retrieval_channels"]),
            sources=list(state["sources"]),
            assistant_message=str(state["assistant_message"]),
        )

    def stream(self, question: str) -> WorkflowStreamAdapterResult:
        retrieval_result = self.retrieval_engine.retrieve(question)
        sources = retrieval_result.sources

        try:
            deltas = self.llm_service.stream_answer(question=question, sources=sources)
        except Exception as exc:
            deltas = [self._build_fallback_answer(question=question, sources=sources, error=exc)]

        return WorkflowStreamAdapterResult(
            adapter=self.name,
            retrieval_channels=retrieval_result.channels,
            sources=sources,
            deltas=deltas,
        )

    def _retrieve_node(self, state: LangGraphState) -> dict[str, Any]:
        question = str(state["question"])
        retrieval_result = self.retrieval_engine.retrieve(question)
        return {
            "question": question,
            "sources": retrieval_result.sources,
            "retrieval_channels": retrieval_result.channels,
            "retrieval_count": len(retrieval_result.sources),
        }

    def _generate_node(self, state: LangGraphState) -> dict[str, Any]:
        question = str(state["question"])
        sources = list(state["sources"])

        try:
            assistant_message = self.llm_service.generate_answer(question=question, sources=sources)
        except Exception as exc:
            assistant_message = self._build_fallback_answer(question=question, sources=sources, error=exc)

        return {"assistant_message": assistant_message}

    def _build_fallback_answer(self, question: str, sources: list[ChatSourceItem], error: Exception) -> str:
        error_message = str(error).strip() or error.__class__.__name__

        if sources:
            source = sources[0]
            return (
                f"RetriFlow LangGraph 在调用模型 '{self.settings.default_chat_model}' 时触发降级处理："
                f"{error_message}。你的问题是“{question}”。当前命中的首条资料是《{source.document_title}》，"
                f"相关内容为：{source.content}"
            )

        return (
            f"RetriFlow LangGraph 在调用模型 '{self.settings.default_chat_model}' 时触发降级处理："
            f"{error_message}。你的问题是“{question}”。当前还没有检索到可直接引用的知识片段。"
        )

    @staticmethod
    def _resolve_traceable():
        try:
            from langsmith import traceable
        except ImportError:

            def noop_traceable(**_kwargs):
                def decorator(fn):
                    return fn

                return decorator

            return noop_traceable

        return traceable


def resolve_workflow_adapter() -> WorkflowAdapter:
    settings = get_settings()
    adapter_mode = settings.workflow_adapter
    has_langgraph = importlib.util.find_spec("langgraph") is not None
    has_langchain = importlib.util.find_spec("langchain") is not None

    if adapter_mode == "langgraph" and has_langgraph and has_langchain:
        return LangGraphWorkflowAdapter()

    if adapter_mode == "auto" and has_langgraph and has_langchain:
        return LangGraphWorkflowAdapter()

    return FallbackWorkflowAdapter()
