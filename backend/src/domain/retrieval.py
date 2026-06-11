from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, PrivateAttr

from core.config import get_settings
from schemas.chat import ChatSourceItem

from domain.reranker import RetriFlowRerankService
from domain.retrieval_channels import BM25SearchChannel, RetrievalChannel
from domain.retrieval_postprocessors import deduplicate_and_rank, reciprocal_rank_fusion
from domain.vector_store import resolve_vector_store


@dataclass
class RetrievalResult:
    channels: list[str]
    sources: list[ChatSourceItem]
    stage_counts: dict[str, int]


class RetriFlowHybridRetriever(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _channels: list[RetrievalChannel] = PrivateAttr()
    _knowledge_base_ids: list[str] | None = PrivateAttr(default=None)
    _bm25_top_k: int = PrivateAttr(default=80)
    _vector_top_k: int = PrivateAttr(default=80)
    _fusion_top_k: int = PrivateAttr(default=50)
    _rerank_top_k: int = PrivateAttr(default=10)
    _final_top_k: int = PrivateAttr(default=5)

    def __init__(self, knowledge_base_ids: list[str] | None = None) -> None:
        super().__init__()
        settings = get_settings()
        self._channels = [BM25SearchChannel()]
        self._knowledge_base_ids = knowledge_base_ids
        self._vector_top_k = settings.retrieval_vector_top_k
        self._fusion_top_k = settings.retrieval_rrf_top_k
        self._rerank_top_k = settings.retrieval_rerank_top_k
        self._final_top_k = settings.retrieval_final_top_k
        self._bm25_top_k = settings.retrieval_bm25_top_k

    @property
    def channel_names(self) -> list[str]:
        return ["bm25", "semantic", "hybrid_rrf", "rerank"]

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
        effective_queries = [item.strip() for item in (queries or [query]) if item.strip()]
        if not effective_queries:
            effective_queries = [query]

        bm25_records = []
        semantic_records = []
        for effective_query in effective_queries:
            for channel in self._channels:
                bm25_records.extend(
                    channel.retrieve(
                        effective_query,
                        knowledge_base_ids=self._knowledge_base_ids,
                        top_k=self._bm25_top_k,
                    )
                )
            semantic_records.extend(self._similarity_search(query=effective_query))

        bm25_records = deduplicate_and_rank(bm25_records, top_k=self._bm25_top_k)
        semantic_records = deduplicate_and_rank(semantic_records, top_k=self._vector_top_k)
        fused_records = reciprocal_rank_fusion([bm25_records, semantic_records], top_k=self._fusion_top_k)
        reranked_records = RetriFlowRerankService().rerank(
            question=query,
            records=fused_records,
            limit=self._rerank_top_k,
        )
        ranked = reranked_records[: self._final_top_k]
        return ranked, {
            "bm25": len(bm25_records),
            "semantic": len(semantic_records),
            "hybrid_rrf": len(fused_records),
            "rerank": len(reranked_records),
            "final": len(ranked),
        }

    def _similarity_search(self, query: str):
        vector_store = resolve_vector_store()
        if self._knowledge_base_ids:
            try:
                return vector_store.similarity_search(
                    query,
                    k=self._vector_top_k,
                    knowledge_base_ids=self._knowledge_base_ids,
                )
            except TypeError:
                return vector_store.similarity_search(query, k=self._vector_top_k)
        return vector_store.similarity_search(query, k=self._vector_top_k)


class RetriFlowRetrievalEngine:
    def __init__(self) -> None:
        self._default_retriever = RetriFlowHybridRetriever()

    def retrieve(
        self,
        question: str,
        queries: list[str] | None = None,
        knowledge_base_ids: list[str] | None = None,
    ) -> RetrievalResult:
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
        return RetrievalResult(channels=channel_names, sources=sources, stage_counts=stage_counts)
