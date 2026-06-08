from dataclasses import dataclass

import httpx

from core.config import get_settings
from domain.llm import LLMProviderConfig, RetriFlowLLMService
from domain.retrieval_channels import RetrievedChunkRecord, tokenize_text


@dataclass
class RerankItem:
    index: int
    relevance_score: float


class RetriFlowRerankService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = RetriFlowLLMService()

    def rerank(
        self,
        question: str,
        records: list[RetrievedChunkRecord],
        limit: int = 10,
    ) -> list[RetrievedChunkRecord]:
        if not records:
            return []

        provider = self.llm_service._resolve_provider()
        if provider is None:
            return self._fallback_rerank(question=question, records=records, limit=limit)

        try:
            ranked_items = self._request_rerank(provider=provider, question=question, records=records, limit=limit)
        except Exception:
            return self._fallback_rerank(question=question, records=records, limit=limit)

        reranked: list[RetrievedChunkRecord] = []
        for item in ranked_items:
            if item.index < 0 or item.index >= len(records):
                continue
            source = records[item.index]
            reranked.append(
                RetrievedChunkRecord(
                    chunk_id=source.chunk_id,
                    knowledge_base_id=source.knowledge_base_id,
                    document_id=source.document_id,
                    document_title=source.document_title,
                    content=source.content,
                    score=item.relevance_score,
                    channel="rerank",
                )
            )

        return reranked[:limit] or self._fallback_rerank(question=question, records=records, limit=limit)

    def _request_rerank(
        self,
        provider: LLMProviderConfig,
        question: str,
        records: list[RetrievedChunkRecord],
        limit: int,
    ) -> list[RerankItem]:
        payload = {
            "model": self.settings.default_rerank_model,
            "query": question,
            "documents": [f"{record.document_title}\n{record.content}" for record in records],
            "top_n": min(limit, len(records)),
            "return_documents": False,
        }
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.settings.llm_request_timeout_seconds) as client:
            response = client.post(
                f"{provider.base_url.rstrip('/')}/rerank",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        raw_items = data.get("results") or data.get("data") or []
        ranked_items: list[RerankItem] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            raw_index = raw_item.get("index")
            raw_score = raw_item.get("relevance_score", raw_item.get("score", 0.0))
            if raw_index is None:
                continue
            ranked_items.append(RerankItem(index=int(raw_index), relevance_score=float(raw_score)))

        ranked_items.sort(key=lambda item: (-item.relevance_score, item.index))
        return ranked_items[:limit]

    @staticmethod
    def _fallback_rerank(
        question: str,
        records: list[RetrievedChunkRecord],
        limit: int,
    ) -> list[RetrievedChunkRecord]:
        query_terms = set(tokenize_text(question))

        def score_record(record: RetrievedChunkRecord) -> tuple[float, float, int]:
            record_terms = set(tokenize_text(f"{record.document_title} {record.content}"))
            overlap = len(query_terms.intersection(record_terms))
            return (float(overlap), float(record.score), -record.chunk_id)

        ranked = sorted(records, key=score_record, reverse=True)
        ranked_size = len(ranked[:limit])
        return [
            RetrievedChunkRecord(
                chunk_id=record.chunk_id,
                knowledge_base_id=record.knowledge_base_id,
                document_id=record.document_id,
                document_title=record.document_title,
                content=record.content,
                score=float(ranked_size - index),
                channel="rerank",
            )
            for index, record in enumerate(ranked[:limit])
        ]
