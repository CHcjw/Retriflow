from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, PrivateAttr

from core.state import get_connection
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
    _search_top_k_override: int | None = PrivateAttr(default=None)
    _top_k_by_knowledge_base: dict[str, int] = PrivateAttr(default_factory=dict)
    _min_score_by_knowledge_base: dict[str, float] = PrivateAttr(default_factory=dict)
    _postprocessors: list[SearchResultPostProcessor] = PrivateAttr()
    _trace_service: RetriFlowTraceService = PrivateAttr()
    _last_stage_metrics: dict[str, dict[str, object]] = PrivateAttr(default_factory=dict)

    def __init__(
        self,
        knowledge_base_ids: list[str] | None = None,
        channels: list[RetrievalChannel] | None = None,
        postprocessors: list[SearchResultPostProcessor] | None = None,
        search_top_k_override: int | None = None,
        top_k_by_knowledge_base: dict[str, int] | None = None,
        min_score_by_knowledge_base: dict[str, float] | None = None,
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
        self._search_top_k_override = search_top_k_override if search_top_k_override and search_top_k_override > 0 else None
        self._top_k_by_knowledge_base = {
            str(knowledge_base_id): int(top_k)
            for knowledge_base_id, top_k in (top_k_by_knowledge_base or {}).items()
            if int(top_k) > 0
        }
        self._min_score_by_knowledge_base = {
            str(knowledge_base_id): float(min_score)
            for knowledge_base_id, min_score in (min_score_by_knowledge_base or {}).items()
            if float(min_score) > 0
        }
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
                records = self._apply_per_knowledge_base_min_score(records)
                records = self._apply_per_knowledge_base_limit(records)
                channel_result.records = records
                channel_results.append(channel_result)
                stage_counts[channel_result.channel_name] = len(records)
                stage_metrics[channel_result.channel_name] = {
                    "records": len(records),
                    "latency_ms": channel_result.latency_ms,
                    "query_count": (channel_result.metadata or {}).get("query_count", len(channel_context.effective_queries)),
                    "top_k": channel_context.top_k,
                    "cache_hits": (channel_result.metadata or {}).get("cache_hits", 0),
                }
                if (channel_result.metadata or {}).get("cross_request_cache_hits"):
                    stage_metrics[channel_result.channel_name]["cross_request_cache_hits"] = (
                        channel_result.metadata or {}
                    ).get("cross_request_cache_hits", 0)
                    stage_metrics[channel_result.channel_name]["cache_scope"] = "cross_request"
                if self._top_k_by_knowledge_base:
                    stage_metrics[channel_result.channel_name]["top_k_by_knowledge_base"] = dict(
                        self._top_k_by_knowledge_base
                    )
                if self._min_score_by_knowledge_base:
                    stage_metrics[channel_result.channel_name]["min_score_by_knowledge_base"] = dict(
                        self._min_score_by_knowledge_base
                    )
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
        if self._search_top_k_override is not None:
            return self._search_top_k_override
        if channel_name == "bm25":
            return self._bm25_top_k
        if channel_name == "semantic":
            return self._vector_top_k
        return max(self._bm25_top_k, self._vector_top_k)

    def _apply_per_knowledge_base_limit(self, records: list) -> list:
        if not self._top_k_by_knowledge_base:
            return records
        counts: dict[str, int] = {}
        limited = []
        for record in records:
            knowledge_base_id = str(record.knowledge_base_id)
            limit = self._top_k_by_knowledge_base.get(knowledge_base_id)
            if limit is None:
                limited.append(record)
                continue
            if counts.get(knowledge_base_id, 0) >= limit:
                continue
            counts[knowledge_base_id] = counts.get(knowledge_base_id, 0) + 1
            limited.append(record)
        return limited

    def _apply_per_knowledge_base_min_score(self, records: list) -> list:
        if not self._min_score_by_knowledge_base:
            return records
        filtered = []
        for record in records:
            min_score = self._min_score_by_knowledge_base.get(str(record.knowledge_base_id))
            if min_score is not None and float(record.score) < min_score:
                continue
            filtered.append(record)
        return filtered


class RetriFlowRetrievalEngine:
    def __init__(self, retriever_factory: Callable[..., RetriFlowHybridRetriever] = RetriFlowHybridRetriever) -> None:
        self._retriever_factory = retriever_factory
        self._default_retriever = self._retriever_factory()
        self.trace_service = RetriFlowTraceService()

    def retrieve(
        self,
        question: str,
        queries: list[str] | None = None,
        knowledge_base_ids: list[str] | None = None,
        top_k_override: int | None = None,
        top_k_by_knowledge_base: dict[str, int] | None = None,
        min_score_by_knowledge_base: dict[str, float] | None = None,
    ) -> RetrievalResult:
        with self.trace_service.span(
            name="retrieval-engine",
            node_type="RETRIEVE",
            input_summary=question[:120],
            metadata={
                "knowledge_base_ids": knowledge_base_ids or [],
                "top_k_override": top_k_override,
                "top_k_by_knowledge_base": top_k_by_knowledge_base or {},
                "min_score_by_knowledge_base": min_score_by_knowledge_base or {},
            },
        ) as span:
            retriever = self._default_retriever
            if knowledge_base_ids or top_k_override or top_k_by_knowledge_base or min_score_by_knowledge_base:
                retriever = self._retriever_factory(
                    knowledge_base_ids=knowledge_base_ids,
                    search_top_k_override=top_k_override,
                    top_k_by_knowledge_base=top_k_by_knowledge_base,
                    min_score_by_knowledge_base=min_score_by_knowledge_base,
                )

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
            sources = self._prepend_assessment_count_context(
                question=question,
                sources=sources,
                knowledge_base_ids=knowledge_base_ids,
            )
            self.trace_service.update_node_metadata(
                span.id,
                self._build_retrieval_observability_metadata(
                    channel_names=channel_names,
                    stage_counts=stage_counts,
                    stage_metrics=retriever._last_stage_metrics,
                    sources=sources,
                ),
            )
            span.finish_success(output_summary=f"sources={len(sources)}")
            return RetrievalResult(
                channels=channel_names,
                sources=sources,
                stage_counts=stage_counts,
                stage_metrics=retriever._last_stage_metrics,
            )

    @staticmethod
    def _build_retrieval_observability_metadata(
        *,
        channel_names: list[str],
        stage_counts: dict[str, int],
        stage_metrics: dict[str, dict[str, object]],
        sources: list[ChatSourceItem],
    ) -> dict[str, object]:
        return {
            "channels": channel_names,
            "stage_counts": stage_counts,
            "stage_metrics": stage_metrics,
            "source_count": len(sources),
            "source_preview": [
                {
                    "chunk_id": source.chunk_id,
                    "knowledge_base_id": source.knowledge_base_id,
                    "document_id": source.document_id,
                    "document_title": source.document_title,
                    "score": source.score,
                    "source_updated_at": source.source_updated_at,
                }
                for source in sources[:5]
            ],
        }

    @classmethod
    def _prepend_assessment_count_context(
        cls,
        *,
        question: str,
        sources: list[ChatSourceItem],
        knowledge_base_ids: list[str] | None,
    ) -> list[ChatSourceItem]:
        if not cls._looks_like_assessment_count_question(question):
            return sources

        document_ids = []
        for source in sources:
            if source.document_id not in document_ids:
                document_ids.append(source.document_id)

        documents = cls._load_documents_for_count_context(
            document_ids=document_ids,
            knowledge_base_ids=knowledge_base_ids,
            question=question,
        )
        if document_ids:
            fallback_documents = cls._load_documents_for_count_context(
                document_ids=[],
                knowledge_base_ids=knowledge_base_ids,
                question=question,
            )
            seen_ids = {int(document["id"]) for document in documents}
            documents = [
                *documents,
                *(document for document in fallback_documents if int(document["id"]) not in seen_ids),
            ]
        for document in documents:
            context = cls._build_assessment_count_context(str(document["content"] or ""))
            if not context:
                continue
            synthetic_source = ChatSourceItem(
                chunk_id=0 - int(document["id"]),
                knowledge_base_id=str(document["knowledge_base_id"]),
                document_id=int(document["id"]),
                document_title=str(document["title"]),
                content=context,
                score=1.0,
                source_link=(
                    f"/api/v1/knowledge-bases/{document['knowledge_base_id']}"
                    f"/documents/{document['id']}/preview"
                ),
                source_updated_at=str(document.get("created_at") or ""),
            )
            return [synthetic_source, *sources]

        return sources

    @staticmethod
    def _looks_like_assessment_count_question(question: str) -> bool:
        normalized = re.sub(r"\s+", "", question)
        if "道" in normalized and any(token in normalized for token in ("多少", "几", "有几", "有多少", "共", "总共")):
            return True
        if any(token in normalized for token in ("多少道", "几道", "有多少道", "有几道", "共几道", "总共多少道")):
            return True
        if not any(token in normalized for token in ("多少", "有几", "有多少", "共几", "总共")):
            return False
        return any(token in normalized for token in ("题", "小题", "复习题", "试题", "练习题"))

    @staticmethod
    def _load_documents_for_count_context(
        *,
        document_ids: list[int],
        knowledge_base_ids: list[str] | None,
        question: str,
    ) -> list:
        with get_connection() as connection:
            if document_ids:
                placeholders = ",".join("?" for _ in document_ids)
                return connection.execute(
                    f"""
                    select id, knowledge_base_id, title, content, created_at
                    from knowledge_documents
                    where id in ({placeholders})
                    order by id
                    """,
                    tuple(document_ids),
                ).fetchall()

            params: list[str] = []
            where_clauses: list[str] = []
            if knowledge_base_ids:
                placeholders = ",".join("?" for _ in knowledge_base_ids)
                where_clauses.append(f"knowledge_base_id in ({placeholders})")
                params.extend(knowledge_base_ids)

            query_tokens = [token for token in ("复习", "软件工程", "题", "试题", "练习") if token in question]
            if query_tokens:
                token_clauses = []
                for token in query_tokens:
                    token_clauses.append("(title like ? or content like ?)")
                    params.extend([f"%{token}%", f"%{token}%"])
                where_clauses.append("(" + " or ".join(token_clauses) + ")")

            where_sql = f"where {' and '.join(where_clauses)}" if where_clauses else ""
            return connection.execute(
                f"""
                select id, knowledge_base_id, title, content, created_at
                from knowledge_documents
                {where_sql}
                order by id desc
                limit 5
                """,
                tuple(params),
            ).fetchall()

    @staticmethod
    def _build_assessment_count_context(content: str) -> str:
        rows: list[tuple[str, int, str]] = []
        normalized_content = re.sub(r"(?<!^)([一二三四五六七八九十]+、)", r"\n\1", content)
        for raw_line in normalized_content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            label_match = re.match(r"^[一二三四五六七八九十]+、\s*([^（(]+)", line)
            if not label_match:
                continue
            label = label_match.group(1).strip()
            detail_match = re.search(r"本题共\s*(\d+)\s*小题", line)
            if detail_match:
                rows.append((label, int(detail_match.group(1)), line))
                continue
            sub_question_numbers = {int(item) for item in re.findall(r"第\s*(\d+)\s*小题", line)}
            if sub_question_numbers:
                rows.append((label, len(sub_question_numbers), line))

        if not rows:
            return ""

        total = sum(count for _, count, _ in rows)
        lines = ["题目统计线索："]
        for label, count, original in rows:
            lines.append(f"- {label}：{count}小题。依据：{original}")
        lines.append(f"合计：{total}小题。")
        return "\n".join(lines)
