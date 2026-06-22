from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, PrivateAttr

from core.config import get_settings
from infra.vector_store import resolve_vector_store
from modules.rag.rerank import RetriFlowRerankService
from modules.rag.retrieval.channels import BM25SearchChannel, RetrievalChannel, SearchChannelResult, SearchContext, VectorSearchChannel
from modules.rag.retrieval.postprocessors import (
    FinalLimitPostProcessor,
    RerankPostProcessor,
    RrfFusionPostProcessor,
    SearchResultPostProcessor,
    deduplicate_and_rank,
)
from modules.rag.trace import RetriFlowTraceService
from schemas.chat import ChatSourceItem


@dataclass
class RetrievalResult:
    channels: list[str]
    sources: list[ChatSourceItem]
    stage_counts: dict[str, int]
    stage_metrics: dict[str, dict[str, object]]


class RetriFlowHybridRetriever(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _channels: list[RetrievalChannel] = PrivateAttr()
    _knowledge_base_ids: list[str] | None = PrivateAttr(default=None)
    _bm25_top_k: int = PrivateAttr(default=80)
    _vector_top_k: int = PrivateAttr(default=80)
    _fusion_top_k: int = PrivateAttr(default=50)
    _rerank_top_k: int = PrivateAttr(default=10)
    _final_top_k: int = PrivateAttr(default=5)
    _postprocessors: list[SearchResultPostProcessor] = PrivateAttr()
    _trace_service: RetriFlowTraceService = PrivateAttr()
    _last_stage_metrics: dict[str, dict[str, object]] = PrivateAttr(default_factory=dict)

    def __init__(
        self,
        knowledge_base_ids: list[str] | None = None,
        channels: list[RetrievalChannel] | None = None,
        postprocessors: list[SearchResultPostProcessor] | None = None,
    ) -> None:
        super().__init__()
        settings = get_settings()
        self._channels = channels or [
            BM25SearchChannel(),
            VectorSearchChannel(vector_store_factory=resolve_vector_store),
        ]
        self._knowledge_base_ids = knowledge_base_ids
        self._vector_top_k = settings.retrieval_vector_top_k
        self._fusion_top_k = settings.retrieval_rrf_top_k
        self._rerank_top_k = settings.retrieval_rerank_top_k
        self._final_top_k = settings.retrieval_final_top_k
        self._bm25_top_k = settings.retrieval_bm25_top_k
        self._postprocessors = postprocessors or [
            RrfFusionPostProcessor(top_k=self._fusion_top_k),
            RerankPostProcessor(service_factory=lambda: RetriFlowRerankService(), limit=self._rerank_top_k),
            FinalLimitPostProcessor(limit=self._final_top_k),
        ]
        self._trace_service = RetriFlowTraceService()

    @property
    def channel_names(self) -> list[str]:
        channel_names = [channel.name for channel in self._channels]
        return [*channel_names, "hybrid_rrf", "rerank"]

    def _get_relevant_documents(self, query: str) -> list[Document]:
        ranked, _stage_counts = self.retrieve_ranked_records(query)
        return [
            Document(
                page_content=item.content,
                metadata={
                    "chunk_id": item.chunk_id,
                    "knowledge_base_id": item.knowledge_base_id,
                    "document_id": item.document_id,
                    "document_title": item.document_title,
                    "score": item.score,
                    "channel": item.channel,
                    "source_updated_at": item.source_updated_at,
                },
            )
            for item in ranked
        ]

    def retrieve_ranked_records(
        self,
        query: str,
        queries: list[str] | None = None,
    ) -> tuple[list, dict[str, int]]:
        with self._trace_service.span(
            name="multi-channel-retrieval",
            node_type="RETRIEVE_CHANNEL",
            input_summary=query[:120],
            metadata={"knowledge_base_ids": self._knowledge_base_ids or []},
        ) as span:
            base_context = SearchContext(
                original_question=query,
                rewritten_question=(queries or [""])[0] if queries else "",
                queries=queries,
                knowledge_base_ids=self._knowledge_base_ids,
            )
            channel_results = []
            stage_counts: dict[str, int] = {}
            stage_metrics: dict[str, dict[str, object]] = {}
            for channel in self._channels:
                if not channel.is_enabled(base_context):
                    continue
                channel_context = SearchContext(
                    original_question=query,
                    rewritten_question=base_context.rewritten_question,
                    queries=base_context.effective_queries,
                    knowledge_base_ids=self._knowledge_base_ids,
                    top_k=self._top_k_for_channel(channel.name),
                    metadata=base_context.metadata,
                )
                try:
                    channel_result = channel.search(channel_context)
                except Exception as exc:
                    channel_result = SearchChannelResult(
                        channel_name=channel.name,
                        records=[],
                        latency_ms=0,
                        metadata={
                            "query_count": len(channel_context.effective_queries),
                            "error": str(exc),
                        },
                    )
                records = deduplicate_and_rank(channel_result.records, top_k=channel_context.top_k)
                channel_result.records = records
                channel_results.append(channel_result)
                stage_counts[channel_result.channel_name] = len(records)
                stage_metrics[channel_result.channel_name] = {
                    "records": len(records),
                    "latency_ms": channel_result.latency_ms,
                    "query_count": (channel_result.metadata or {}).get("query_count", len(channel_context.effective_queries)),
                    "top_k": channel_context.top_k,
                }
                if (channel_result.metadata or {}).get("error"):
                    stage_metrics[channel_result.channel_name]["error"] = str(channel_result.metadata["error"])

            records = [record for result in channel_results for record in result.records]
            for postprocessor in sorted(
                (item for item in self._postprocessors if item.is_enabled(base_context)),
                key=lambda item: item.order,
            ):
                before_count = len(records)
                try:
                    records = postprocessor.process(records, channel_results, base_context)
                except Exception as exc:
                    stage_counts[postprocessor.name] = len(records)
                    stage_metrics[postprocessor.name] = {
                        "input_records": before_count,
                        "records": len(records),
                        "error": str(exc),
                    }
                    continue
                stage_counts[postprocessor.name] = len(records)
                stage_metrics[postprocessor.name] = {
                    "input_records": before_count,
                    "records": len(records),
                }

            stage_counts.setdefault("final", len(records))
            stage_metrics.setdefault("final", {"records": len(records)})
            self._last_stage_metrics = stage_metrics
            span.finish_success(
                output_summary=(
                    f"channels={','.join(stage_counts.keys())}; "
                    f"records={len(records)}"
                )
            )
            return records, stage_counts

    def _top_k_for_channel(self, channel_name: str) -> int:
        if channel_name == "bm25":
            return self._bm25_top_k
        if channel_name == "semantic":
            return self._vector_top_k
        return max(self._bm25_top_k, self._vector_top_k)


class RetriFlowRetrievalEngine:
    def __init__(self) -> None:
        self._default_retriever = RetriFlowHybridRetriever()
        self.trace_service = RetriFlowTraceService()

    def retrieve(
        self,
        question: str,
        queries: list[str] | None = None,
        knowledge_base_ids: list[str] | None = None,
    ) -> RetrievalResult:
        with self.trace_service.span(
            name="retrieval-engine",
            node_type="RETRIEVE",
            input_summary=question[:120],
            metadata={"knowledge_base_ids": knowledge_base_ids or []},
        ) as span:
            retriever = self._default_retriever
            if knowledge_base_ids:
                retriever = RetriFlowHybridRetriever(knowledge_base_ids=knowledge_base_ids)

            channel_names = retriever.channel_names
            ranked, stage_counts = retriever.retrieve_ranked_records(question, queries=queries)
            sources = [
                ChatSourceItem(
                    chunk_id=int(item.chunk_id),
                    knowledge_base_id=str(item.knowledge_base_id),
                    document_id=int(item.document_id),
                    document_title=str(item.document_title),
                    content=item.content,
                    score=float(item.score),
                    source_link=(
                        f"/api/v1/knowledge-bases/{item.knowledge_base_id}"
                        f"/documents/{item.document_id}/chunks"
                    ),
                    source_updated_at=str(item.source_updated_at),
                )
                for item in ranked
            ]
            span.finish_success(output_summary=f"sources={len(sources)}")
            return RetrievalResult(
                channels=channel_names,
                sources=sources,
                stage_counts=stage_counts,
                stage_metrics=retriever._last_stage_metrics,
            )
