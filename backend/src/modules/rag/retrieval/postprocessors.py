from __future__ import annotations

from typing import Callable, Protocol

from modules.rag.retrieval.channels import RetrievedChunkRecord, SearchChannelResult, SearchContext


class SearchResultPostProcessor(Protocol):
    name: str
    order: int

    def is_enabled(self, context: SearchContext) -> bool:
        ...

    def process(
        self,
        records: list[RetrievedChunkRecord],
        channel_results: list[SearchChannelResult],
        context: SearchContext,
    ) -> list[RetrievedChunkRecord]:
        ...


def deduplicate_and_rank(records: list[RetrievedChunkRecord], top_k: int = 3) -> list[RetrievedChunkRecord]:
    merged: dict[int, RetrievedChunkRecord] = {}
    for record in records:
        existing = merged.get(record.chunk_id)
        if existing is None:
            merged[record.chunk_id] = record
            continue

        existing.score += record.score

    ranked = sorted(merged.values(), key=lambda item: (-item.score, item.chunk_id))
    return ranked[:top_k]


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunkRecord]],
    top_k: int = 50,
    k: int = 60,
) -> list[RetrievedChunkRecord]:
    fused_scores: dict[int, float] = {}
    canonical_records: dict[int, RetrievedChunkRecord] = {}

    for ranked_list in ranked_lists:
        for rank, record in enumerate(ranked_list, start=1):
            fused_scores[record.chunk_id] = fused_scores.get(record.chunk_id, 0.0) + (1.0 / (k + rank))
            canonical_records.setdefault(record.chunk_id, record)

    fused_records = [
        RetrievedChunkRecord(
            chunk_id=record.chunk_id,
            knowledge_base_id=record.knowledge_base_id,
            document_id=record.document_id,
            document_title=record.document_title,
            content=record.content,
            score=fused_scores[record.chunk_id],
            channel="hybrid_rrf",
            source_updated_at=record.source_updated_at,
        )
        for chunk_id, record in canonical_records.items()
        if chunk_id in fused_scores
    ]
    fused_records.sort(key=lambda item: (-item.score, item.chunk_id))
    return fused_records[:top_k]


class RrfFusionPostProcessor:
    name = "hybrid_rrf"
    order = 10

    def __init__(self, *, top_k: int) -> None:
        self.top_k = top_k

    def is_enabled(self, context: SearchContext) -> bool:
        _ = context
        return True

    def process(
        self,
        records: list[RetrievedChunkRecord],
        channel_results: list[SearchChannelResult],
        context: SearchContext,
    ) -> list[RetrievedChunkRecord]:
        _ = records
        _ = context
        return reciprocal_rank_fusion(
            ranked_lists=[result.records for result in channel_results],
            top_k=self.top_k,
        )


class RerankPostProcessor:
    name = "rerank"
    order = 20

    def __init__(self, *, service_factory: Callable[[], object], limit: int) -> None:
        self.service_factory = service_factory
        self.limit = limit

    def is_enabled(self, context: SearchContext) -> bool:
        _ = context
        return True

    def process(
        self,
        records: list[RetrievedChunkRecord],
        channel_results: list[SearchChannelResult],
        context: SearchContext,
    ) -> list[RetrievedChunkRecord]:
        _ = channel_results
        return self.service_factory().rerank(
            question=context.original_question,
            records=records,
            limit=self.limit,
        )


class FinalLimitPostProcessor:
    name = "final"
    order = 30

    def __init__(self, *, limit: int) -> None:
        self.limit = limit

    def is_enabled(self, context: SearchContext) -> bool:
        _ = context
        return True

    def process(
        self,
        records: list[RetrievedChunkRecord],
        channel_results: list[SearchChannelResult],
        context: SearchContext,
    ) -> list[RetrievedChunkRecord]:
        _ = channel_results
        _ = context
        return records[: self.limit]
