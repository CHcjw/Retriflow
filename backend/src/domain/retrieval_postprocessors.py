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
