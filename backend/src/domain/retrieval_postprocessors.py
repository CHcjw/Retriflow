from domain.retrieval_channels import RetrievedChunkRecord


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
