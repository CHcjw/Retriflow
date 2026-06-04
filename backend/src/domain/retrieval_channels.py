import re
from dataclasses import dataclass
from typing import Protocol

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


class RetrievalChannel(Protocol):
    name: str

    def retrieve(self, question: str) -> list[RetrievedChunkRecord]:
        ...


def tokenize_text(text: str) -> list[str]:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
    return [token for token in normalized.split() if token]


def load_chunk_rows():
    with get_connection() as connection:
        return connection.execute(
            """
            select
                kc.id as chunk_id,
                kc.knowledge_base_id,
                kc.document_id,
                kd.title as document_title,
                kc.content
            from knowledge_chunks kc
            join knowledge_documents kd on kd.id = kc.document_id
            order by kc.id desc
            """
        ).fetchall()


class KeywordSearchChannel:
    name = "keyword"

    def retrieve(self, question: str) -> list[RetrievedChunkRecord]:
        keywords = tokenize_text(question)
        if not keywords:
            keywords = [question.lower()]

        results: list[RetrievedChunkRecord] = []
        for row in load_chunk_rows():
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
                    )
                )
        return results


class DocumentTitleSearchChannel:
    name = "document"

    def retrieve(self, question: str) -> list[RetrievedChunkRecord]:
        tokens = tokenize_text(question)
        if not tokens:
            tokens = [question.lower()]

        results: list[RetrievedChunkRecord] = []
        for row in load_chunk_rows():
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
                    )
                )
        return results


class SemanticSearchChannel:
    name = "semantic"

    def retrieve(self, question: str) -> list[RetrievedChunkRecord]:
        question_terms = set(tokenize_text(question))
        if not question_terms:
            question_terms = {question.lower()}

        results: list[RetrievedChunkRecord] = []
        for row in load_chunk_rows():
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
                )
            )
        return results
