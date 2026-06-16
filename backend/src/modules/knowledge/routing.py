from dataclasses import dataclass
import json
from typing import Any

from core.config import get_settings
from core.state import get_connection
from infra.llm import RetriFlowLLMService
from modules.rag.retrieval.channels import tokenize_text


@dataclass
class KnowledgeRouteDecision:
    mode: str
    knowledge_base_ids: list[str]
    confidence: float
    reason: str


class RetriFlowKnowledgeRouteService:
    DOMAIN_SYNONYMS: dict[str, list[str]] = {
        "insurance": ["保险", "理赔", "核保", "保单", "赔付", "underwriting", "claim", "policy", "premium"],
        "retriflow": ["retriflow", "langgraph", "langchain", "rag", "migration"],
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = RetriFlowLLMService()

    def route_question(self, question: str) -> KnowledgeRouteDecision:
        knowledge_bases = self._load_knowledge_base_profiles()
        if not knowledge_bases:
            return KnowledgeRouteDecision(
                mode="global",
                knowledge_base_ids=[],
                confidence=0.0,
                reason="no knowledge bases available",
            )

        if self.settings.route_use_llm:
            llm_decision = self._try_llm_route(question=question, knowledge_bases=knowledge_bases)
            if llm_decision is not None:
                return llm_decision

        return self._fallback_route(question=question, knowledge_bases=knowledge_bases)

    def _try_llm_route(
        self,
        question: str,
        knowledge_bases: list[dict[str, Any]],
    ) -> KnowledgeRouteDecision | None:
        try:
            payload = self.llm_service.route_knowledge_bases(
                question=question,
                knowledge_base_profiles=knowledge_bases,
            )
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None

        mode = str(payload.get("mode", "global"))
        knowledge_base_ids = [str(item) for item in payload.get("knowledge_base_ids", [])]
        confidence = float(payload.get("confidence", 0.0))
        reason = str(payload.get("reason", "llm route"))

        if mode == "knowledge_base" and knowledge_base_ids and confidence >= self.settings.route_confidence_threshold:
            return KnowledgeRouteDecision(
                mode="knowledge_base",
                knowledge_base_ids=knowledge_base_ids,
                confidence=confidence,
                reason=reason,
            )

        return KnowledgeRouteDecision(
            mode="global",
            knowledge_base_ids=[],
            confidence=confidence,
            reason=reason or "llm confidence below threshold",
        )

    def _fallback_route(
        self,
        question: str,
        knowledge_bases: list[dict[str, Any]],
    ) -> KnowledgeRouteDecision:
        query_terms = set(tokenize_text(question))
        expanded_terms = set(query_terms)
        expanded_terms.update(self._expand_domain_terms(query_terms))
        if not expanded_terms:
            return KnowledgeRouteDecision(
                mode="global",
                knowledge_base_ids=[],
                confidence=0.0,
                reason="question did not contain routeable terms",
            )

        scored = []
        for knowledge_base in knowledge_bases:
            profile_terms = set(tokenize_text(knowledge_base["profile_text"]))
            keywords = set(knowledge_base.get("keywords", []))
            overlap = expanded_terms.intersection(profile_terms.union(keywords))
            overlap_score = len(overlap) / max(min(len(expanded_terms), 6), 1)
            keyword_score = len(expanded_terms.intersection(keywords)) / max(min(len(keywords), 4), 1)
            score = max(overlap_score, keyword_score)
            if self._has_domain_alignment(expanded_terms, profile_terms.union(keywords)):
                score += 0.45
            if knowledge_base["name"].lower() in question.lower():
                score += 0.35
            scored.append((score, knowledge_base, overlap))

        scored.sort(key=lambda item: (-item[0], item[1]["id"]))
        best_score, best_match, overlap = scored[0]
        if best_score < self.settings.route_confidence_threshold:
            return KnowledgeRouteDecision(
                mode="global",
                knowledge_base_ids=[],
                confidence=max(best_score, 0.0),
                reason="confidence below threshold",
            )

        return KnowledgeRouteDecision(
            mode="knowledge_base",
            knowledge_base_ids=[str(best_match["id"])],
            confidence=min(best_score, 0.99),
            reason=f"matched profile terms: {', '.join(sorted(overlap)[:6]) or best_match['name']}",
        )

    def _expand_domain_terms(self, query_terms: set[str]) -> set[str]:
        expanded: set[str] = set()
        lowered_terms = {term.lower() for term in query_terms}
        for canonical, synonyms in self.DOMAIN_SYNONYMS.items():
            synonym_set = {canonical, *synonyms}
            if lowered_terms.intersection({item.lower() for item in synonym_set}):
                expanded.update(synonym_set)
        return expanded

    def _has_domain_alignment(self, expanded_terms: set[str], profile_terms: set[str]) -> bool:
        lowered_expanded = {term.lower() for term in expanded_terms}
        lowered_profile = {term.lower() for term in profile_terms}
        for canonical, synonyms in self.DOMAIN_SYNONYMS.items():
            alias_set = {canonical.lower(), *(item.lower() for item in synonyms)}
            if lowered_expanded.intersection(alias_set) and lowered_profile.intersection(alias_set):
                return True
        return False

    @staticmethod
    def _load_knowledge_base_profiles() -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select
                    k.id,
                    k.name,
                    p.profile_text,
                    p.sample_questions_json,
                    p.keywords_json
                from knowledge_bases k
                left join knowledge_base_route_profiles p on p.knowledge_base_id = k.id
                order by k.id
                """
            ).fetchall()

        profiles: list[dict[str, Any]] = []
        for row in rows:
            sample_questions = RetriFlowKnowledgeRouteService._parse_json_field(
                row["sample_questions_json"],
                default=[],
            )
            keywords = RetriFlowKnowledgeRouteService._parse_json_field(
                row["keywords_json"],
                default=[],
            )
            profiles.append(
                {
                    "id": str(row["id"]),
                    "name": str(row["name"]),
                    "profile_text": str(row["profile_text"] or row["name"]),
                    "sample_questions": sample_questions,
                    "keywords": keywords,
                }
            )
        return profiles

    @staticmethod
    def _parse_json_field(value: Any, *, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return default
            return json.loads(text)
        return default

