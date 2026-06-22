from __future__ import annotations

import re
from dataclasses import dataclass
from math import log
import time
from typing import Callable, Protocol

from core.state import get_connection


@dataclass
class RetrievedChunkRecord:
    chunk_id: int
    knowledge_base_id: str
    document_id: int
    document_title: str
    content: str
    score: float
    channel: str
    source_updated_at: str = ""


@dataclass
class SearchContext:
    original_question: str
    rewritten_question: str = ""
    queries: list[str] | None = None
    knowledge_base_ids: list[str] | None = None
    top_k: int = 80
    metadata: dict[str, object] | None = None

    @property
    def main_question(self) -> str:
        return self.rewritten_question or self.original_question

    @property
    def effective_queries(self) -> list[str]:
        queries = [item.strip() for item in (self.queries or [self.main_question]) if item.strip()]
        return queries or [self.original_question]


@dataclass
class SearchChannelResult:
    channel_name: str
    records: list[RetrievedChunkRecord]
    latency_ms: int = 0
    metadata: dict[str, object] | None = None


class RetrievalChannel(Protocol):
    name: str

    def is_enabled(self, context: SearchContext) -> bool:
        ...

    def search(self, context: SearchContext) -> SearchChannelResult:
        ...

    def retrieve(
        self,
        question: str,
        knowledge_base_ids: list[str] | None = None,
        top_k: int = 80,
    ) -> list[RetrievedChunkRecord]:
        ...


def tokenize_text(text: str) -> list[str]:
    normalized = text.lower()
    english_tokens = re.findall(r"[a-z0-9_]+", normalized)
    chinese_tokens: list[str] = []
    for segment in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(segment) == 1:
            chinese_tokens.append(segment)
            continue
        chinese_tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        chinese_tokens.append(segment)
    return [token for token in english_tokens + chinese_tokens if token]


def load_chunk_rows(knowledge_base_ids: list[str] | None = None):
    with get_connection() as connection:
        params: tuple[str, ...] = ()
        where_clause = ""
        if knowledge_base_ids:
            placeholders = ",".join("?" for _ in knowledge_base_ids)
            where_clause = f"where kc.knowledge_base_id in ({placeholders})"
            params = tuple(knowledge_base_ids)

        return connection.execute(
            f"""
            select
                kc.id as chunk_id,
                kc.knowledge_base_id,
                kc.document_id,
                kd.title as document_title,
                kc.content,
                kd.created_at as source_updated_at
            from knowledge_chunks kc
            join knowledge_documents kd on kd.id = kc.document_id
            {where_clause}
            order by kc.id desc
            """,
            params,
        ).fetchall()


class BM25SearchChannel:
    name = "bm25"

    def is_enabled(self, context: SearchContext) -> bool:
        _ = context
        return True

    def search(self, context: SearchContext) -> SearchChannelResult:
        started_at = time.perf_counter()
        records: list[RetrievedChunkRecord] = []
        for query in context.effective_queries:
            records.extend(
                self.retrieve(
                    query,
                    knowledge_base_ids=context.knowledge_base_ids,
                    top_k=context.top_k,
                )
            )
        return SearchChannelResult(
            channel_name=self.name,
            records=records,
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            metadata={"query_count": len(context.effective_queries)},
        )

    def retrieve(
        self,
        question: str,
        knowledge_base_ids: list[str] | None = None,
        top_k: int = 80,
    ) -> list[RetrievedChunkRecord]:
        rows = load_chunk_rows(knowledge_base_ids=knowledge_base_ids)
        if not rows:
            return []

        query_tokens = tokenize_text(question)
        if not query_tokens:
            query_tokens = [question.lower()]

        tokenized_corpus = [tokenize_text(f"{row['document_title']} {row['content']}") for row in rows]
        non_empty_lengths = [len(tokens) for tokens in tokenized_corpus if tokens]
        average_doc_length = sum(non_empty_lengths) / max(len(non_empty_lengths), 1)
        total_documents = len(tokenized_corpus)
        document_frequencies: dict[str, int] = {}

        for tokens in tokenized_corpus:
            for token in set(tokens):
                document_frequencies[token] = document_frequencies.get(token, 0) + 1

        k1 = 1.5
        b = 0.75
        scored_records: list[RetrievedChunkRecord] = []
        for row, tokens in zip(rows, tokenized_corpus, strict=False):
            if not tokens:
                continue

            doc_length = len(tokens)
            score = 0.0
            for token in query_tokens:
                term_frequency = tokens.count(token)
                if term_frequency == 0:
                    continue
                df = document_frequencies.get(token, 0)
                idf = log(1 + ((total_documents - df + 0.5) / (df + 0.5)))
                denominator = term_frequency + k1 * (1 - b + b * (doc_length / max(average_doc_length, 1)))
                score += idf * ((term_frequency * (k1 + 1)) / max(denominator, 1e-9))

            if score <= 0:
                continue

            scored_records.append(
                RetrievedChunkRecord(
                    chunk_id=row["chunk_id"],
                    knowledge_base_id=row["knowledge_base_id"],
                    document_id=row["document_id"],
                    document_title=row["document_title"],
                    content=row["content"],
                    score=score,
                    channel=self.name,
                    source_updated_at=str(row["source_updated_at"] or ""),
                )
            )

        scored_records.sort(key=lambda item: (-item.score, item.chunk_id))
        return scored_records[:top_k]


class VectorSearchChannel:
    name = "semantic"

    def __init__(self, vector_store_factory: Callable[[], object]) -> None:
        self.vector_store_factory = vector_store_factory

    def is_enabled(self, context: SearchContext) -> bool:
        _ = context
        return True

    def search(self, context: SearchContext) -> SearchChannelResult:
        started_at = time.perf_counter()
        records: list[RetrievedChunkRecord] = []
        for query in context.effective_queries:
            records.extend(
                self.retrieve(
                    query,
                    knowledge_base_ids=context.knowledge_base_ids,
                    top_k=context.top_k,
                )
            )
        return SearchChannelResult(
            channel_name=self.name,
            records=records,
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            metadata={"query_count": len(context.effective_queries)},
        )

    def retrieve(
        self,
        question: str,
        knowledge_base_ids: list[str] | None = None,
        top_k: int = 80,
    ) -> list[RetrievedChunkRecord]:
        vector_store = self.vector_store_factory()
        if knowledge_base_ids:
            try:
                return vector_store.similarity_search(
                    question,
                    k=top_k,
                    knowledge_base_ids=knowledge_base_ids,
                )
            except TypeError:
                return vector_store.similarity_search(question, k=top_k)
        return vector_store.similarity_search(question, k=top_k)


class KeywordSearchChannel:
    name = "keyword"

    def retrieve(
        self,
        question: str,
        knowledge_base_ids: list[str] | None = None,
        top_k: int = 80,
    ) -> list[RetrievedChunkRecord]:
        keywords = tokenize_text(question)
        if not keywords:
            keywords = [question.lower()]

        results: list[RetrievedChunkRecord] = []
        for row in load_chunk_rows(knowledge_base_ids=knowledge_base_ids):
            content = row["content"].lower()
            score = 0.0
            for keyword in keywords:
                if keyword:
                    score += content.count(keyword)
            if score > 0:
                results.append(
                    RetrievedChunkRecord(
                        chunk_id=row["chunk_id"],
                        knowledge_base_id=row["knowledge_base_id"],
                        document_id=row["document_id"],
                        document_title=row["document_title"],
                        content=row["content"],
                        score=score,
                        channel=self.name,
                        source_updated_at=str(row["source_updated_at"] or ""),
                    )
                )
        results.sort(key=lambda item: (-item.score, item.chunk_id))
        return results[:top_k]


class DocumentTitleSearchChannel:
    name = "document"

    def retrieve(
        self,
        question: str,
        knowledge_base_ids: list[str] | None = None,
        top_k: int = 80,
    ) -> list[RetrievedChunkRecord]:
        tokens = tokenize_text(question)
        if not tokens:
            tokens = [question.lower()]

        results: list[RetrievedChunkRecord] = []
        for row in load_chunk_rows(knowledge_base_ids=knowledge_base_ids):
            title = row["document_title"].lower()
            score = 0.0
            for token in tokens:
                if token and token in title:
                    score += 1.5
            if score > 0:
                results.append(
                    RetrievedChunkRecord(
                        chunk_id=row["chunk_id"],
                        knowledge_base_id=row["knowledge_base_id"],
                        document_id=row["document_id"],
                        document_title=row["document_title"],
                        content=row["content"],
                        score=score,
                        channel=self.name,
                        source_updated_at=str(row["source_updated_at"] or ""),
                    )
                )
        results.sort(key=lambda item: (-item.score, item.chunk_id))
        return results[:top_k]


class SemanticSearchChannel:
    name = "semantic"

    def retrieve(
        self,
        question: str,
        knowledge_base_ids: list[str] | None = None,
        top_k: int = 80,
    ) -> list[RetrievedChunkRecord]:
        question_terms = set(tokenize_text(question))
        if not question_terms:
            question_terms = {question.lower()}

        results: list[RetrievedChunkRecord] = []
        for row in load_chunk_rows(knowledge_base_ids=knowledge_base_ids):
            combined_terms = set(tokenize_text(f"{row['document_title']} {row['content']}"))
            overlap = question_terms.intersection(combined_terms)
            if not overlap:
                continue

            score = len(overlap) / max(len(question_terms), 1)
            if any(term in row["document_title"].lower() for term in overlap):
                score += 0.35

            results.append(
                RetrievedChunkRecord(
                    chunk_id=row["chunk_id"],
                    knowledge_base_id=row["knowledge_base_id"],
                    document_id=row["document_id"],
                    document_title=row["document_title"],
                    content=row["content"],
                    score=score,
                    channel=self.name,
                    source_updated_at=str(row["source_updated_at"] or ""),
                )
            )
        results.sort(key=lambda item: (-item.score, item.chunk_id))
        return results[:top_k]
