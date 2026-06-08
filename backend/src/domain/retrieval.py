from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, PrivateAttr

from schemas.chat import ChatSourceItem

from domain.reranker import RetriFlowRerankService
from domain.retrieval_channels import BM25SearchChannel, RetrievalChannel
from domain.retrieval_postprocessors import reciprocal_rank_fusion
from domain.vector_store import resolve_vector_store


@dataclass
class RetrievalResult:
    channels: list[str]
    sources: list[ChatSourceItem]


class RetriFlowHybridRetriever(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _channels: list[RetrievalChannel] = PrivateAttr()
    _knowledge_base_ids: list[str] | None = PrivateAttr(default=None)
    _vector_top_k: int = PrivateAttr(default=80)
    _fusion_top_k: int = PrivateAttr(default=50)
    _rerank_top_k: int = PrivateAttr(default=10)
    _final_top_k: int = PrivateAttr(default=5)

    def __init__(self, knowledge_base_ids: list[str] | None = None) -> None:
        super().__init__()
        self._channels = [BM25SearchChannel()]
        self._knowledge_base_ids = knowledge_base_ids

    @property
    def channel_names(self) -> list[str]:
        return ["bm25", "semantic", "hybrid_rrf", "rerank"]

    def _get_relevant_documents(self, query: str) -> list[Document]:
        records = []
        for channel in self._channels:
            records.append(
                channel.retrieve(
                    query,
                    knowledge_base_ids=self._knowledge_base_ids,
                    top_k=self._vector_top_k,
                )
            )

        semantic_records = self._similarity_search(query=query)
        records.append(semantic_records)

        fused_records = reciprocal_rank_fusion(records, top_k=self._fusion_top_k)
        reranked_records = RetriFlowRerankService().rerank(
            question=query,
            records=fused_records,
            limit=self._rerank_top_k,
        )
        ranked = reranked_records[: self._final_top_k]
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
                },
            )
            for item in ranked
        ]

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
        knowledge_base_ids: list[str] | None = None,
    ) -> RetrievalResult:
        retriever = self._default_retriever
        if knowledge_base_ids:
            retriever = RetriFlowHybridRetriever(knowledge_base_ids=knowledge_base_ids)

        channel_names = retriever.channel_names
        ranked = retriever.invoke(question)
        sources = [
            ChatSourceItem(
                chunk_id=int(item.metadata["chunk_id"]),
                knowledge_base_id=str(item.metadata["knowledge_base_id"]),
                document_id=int(item.metadata["document_id"]),
                document_title=str(item.metadata["document_title"]),
                content=item.page_content,
                score=float(item.metadata["score"]),
                source_link=(
                    f"/api/v1/knowledge-bases/{item.metadata['knowledge_base_id']}"
                    f"/documents/{item.metadata['document_id']}/chunks"
                ),
                source_updated_at=str(item.metadata.get("source_updated_at", "")),
            )
            for item in ranked
        ]
        return RetrievalResult(channels=channel_names, sources=sources)
