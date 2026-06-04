from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, PrivateAttr

from schemas.chat import ChatSourceItem

from domain.retrieval_channels import (
    DocumentTitleSearchChannel,
    KeywordSearchChannel,
    RetrievalChannel,
)
from domain.retrieval_postprocessors import deduplicate_and_rank
from domain.vector_store import resolve_vector_store


@dataclass
class RetrievalResult:
    channels: list[str]
    sources: list[ChatSourceItem]


class RetriFlowHybridRetriever(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _channels: list[RetrievalChannel] = PrivateAttr()

    def __init__(self) -> None:
        super().__init__()
        self._channels = [
            KeywordSearchChannel(),
            DocumentTitleSearchChannel(),
        ]

    @property
    def channel_names(self) -> list[str]:
        return [channel.name for channel in self._channels] + ["semantic"]

    def _get_relevant_documents(self, query: str) -> list[Document]:
        records = []
        for channel in self._channels:
            records.extend(channel.retrieve(query))
        records.extend(resolve_vector_store().similarity_search(query, k=4))

        ranked = deduplicate_and_rank(records)
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


class RetriFlowRetrievalEngine:
    def __init__(self) -> None:
        self.retriever = RetriFlowHybridRetriever()

    def retrieve(self, question: str) -> RetrievalResult:
        channel_names = self.retriever.channel_names
        ranked = self.retriever.invoke(question)
        sources = [
            ChatSourceItem(
                chunk_id=int(item.metadata["chunk_id"]),
                knowledge_base_id=str(item.metadata["knowledge_base_id"]),
                document_id=int(item.metadata["document_id"]),
                document_title=str(item.metadata["document_title"]),
                content=item.page_content,
                score=float(item.metadata["score"]),
            )
            for item in ranked
        ]
        return RetrievalResult(channels=channel_names, sources=sources)
