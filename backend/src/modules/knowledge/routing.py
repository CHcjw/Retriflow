from dataclasses import dataclass
import json
from typing import Any

from core.config import get_settings
from core.state import get_connection
from infra.llm import RetriFlowLLMService
from modules.knowledge.intent_cache import IntentTreeCacheManager
from modules.rag.retrieval.channels import tokenize_text


@dataclass
class KnowledgeRouteCandidate:
    knowledge_base_id: str
    name: str
    path: str
    score: float


@dataclass
class KnowledgeRouteDecision:
    mode: str
    knowledge_base_ids: list[str]
    confidence: float
    reason: str
    candidates: list[KnowledgeRouteCandidate] = None

    def __post_init__(self) -> None:
        if self.candidates is None:
            self.candidates = []



class RetriFlowKnowledgeRouteService:
    MAX_INTENT_COUNT = 3
    DOMAIN_SYNONYMS: dict[str, list[str]] = {
        "insurance": ["保险", "理赔", "核保", "保单", "赔付", "underwriting", "claim", "policy", "premium"],
        "retriflow": ["retriflow", "langgraph", "langchain", "rag", "migration"],
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = RetriFlowLLMService()
        self.intent_tree_cache = IntentTreeCacheManager()

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

        intent_decision = self._route_with_intent_tree(question)
        if intent_decision is not None:
            return intent_decision

        return self._fallback_route(question=question, knowledge_bases=knowledge_bases)

    def _route_with_intent_tree(self, question: str) -> KnowledgeRouteDecision | None:
        intent_nodes = self._load_enabled_intent_nodes()
        if not intent_nodes:
            return None

        query_terms = set(tokenize_text(question))
        expanded_terms = set(query_terms)
        expanded_terms.update(self._expand_domain_terms(query_terms))
        if not expanded_terms:
            return None

        scored: list[tuple[float, dict[str, Any], set[str]]] = []
        for node in intent_nodes:
            node_terms = set(tokenize_text(node["match_text"]))
            overlap = expanded_terms.intersection(node_terms)
            score = len(overlap) / max(min(len(expanded_terms), 6), 1)
            if self._has_domain_alignment(expanded_terms, node_terms):
                score += 0.45
            scored.append((score, node, overlap))

        if not scored:
            return None

        scored.sort(key=lambda item: (-item[0], int(item[1].get("sort_order") or 0), str(item[1]["id"])))
        selected: list[tuple[float, dict[str, Any], set[str], dict[str, Any]]] = []
        seen_knowledge_bases: set[str] = set()
        for score, node, overlap in scored:
            if score < self.settings.route_confidence_threshold:
                continue
            target_node = self._resolve_kb_target_node(node)
            if target_node is None:
                continue
            knowledge_base_id = str(target_node["knowledge_base_id"])
            if knowledge_base_id in seen_knowledge_bases:
                continue
            selected.append((score, node, overlap, target_node))
            seen_knowledge_bases.add(knowledge_base_id)
            if len(selected) >= self.MAX_INTENT_COUNT:
                break

        if not selected:
            return None

        best_score = selected[0][0]
        knowledge_base_ids = [str(target["knowledge_base_id"]) for _, _, _, target in selected]
        candidates = [
            KnowledgeRouteCandidate(
                knowledge_base_id=str(target["knowledge_base_id"]),
                name=str(target.get("name") or node.get("name") or target["knowledge_base_id"]),
                path=str(target.get("path") or target.get("name") or target["knowledge_base_id"]),
                score=float(score),
            )
            for score, node, _, target in selected
        ]
        candidate_summaries = [
            f"{target['path']}({score:.2f})"
            for score, _, _, target in selected
        ]
        matched_terms = sorted({term for _, _, overlap, _ in selected for term in overlap})[:6]

        return KnowledgeRouteDecision(
            mode="knowledge_base",
            knowledge_base_ids=knowledge_base_ids,
            confidence=min(best_score, 0.99),
            reason=(
                f"intent path candidates: {'; '.join(candidate_summaries)} | matched terms: "
                f"{', '.join(matched_terms) or selected[0][1]['name']}"
            ),
            candidates=candidates,
        )

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

    def _load_enabled_intent_nodes(self) -> list[dict[str, Any]]:
        cached_tree = self.intent_tree_cache.get_intent_tree_from_cache()
        if cached_tree is not None:
            return self._flatten_intent_tree(cached_tree)

        rows = self._load_intent_node_rows_from_db()
        roots = self._build_intent_tree(rows)
        self.intent_tree_cache.save_intent_tree_to_cache(roots)
        return self._flatten_intent_tree(roots)

    @staticmethod
    def _load_intent_node_rows_from_db() -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select
                    id,
                    name,
                    code,
                    level,
                    node_type,
                    parent_id,
                    knowledge_base_id,
                    collection_name,
                    description,
                    sample_questions_json,
                    rule_snippet,
                    prompt_template,
                    top_k,
                    sort_order
                from admin_intent_nodes
                where enabled = 1
                  and node_type = 'KB'
                order by parent_id, sort_order, created_at, name
                """
            ).fetchall()

        columns = [
            "id",
            "name",
            "code",
            "level",
            "node_type",
            "parent_id",
            "knowledge_base_id",
            "collection_name",
            "description",
            "sample_questions_json",
            "rule_snippet",
            "prompt_template",
            "top_k",
            "sort_order",
        ]
        return [{key: row[key] for key in columns} for row in rows]

    @staticmethod
    def _build_intent_tree(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nodes_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            sample_questions = RetriFlowKnowledgeRouteService._parse_json_field(
                row["sample_questions_json"],
                default=[],
            )
            node = {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "code": str(row["code"] or ""),
                "level": str(row["level"] or ""),
                "parent_id": str(row["parent_id"] or "ROOT"),
                "knowledge_base_id": str(row["knowledge_base_id"] or ""),
                "collection_name": str(row["collection_name"] or ""),
                "description": str(row["description"] or ""),
                "sample_questions": sample_questions,
                "rule_snippet": str(row["rule_snippet"] or ""),
                "prompt_template": str(row["prompt_template"] or ""),
                "top_k": row.get("top_k"),
                "sort_order": int(row["sort_order"] or 0),
                "children": [],
            }
            nodes_by_id[node["id"]] = node

        roots: list[dict[str, Any]] = []
        for node in sorted(nodes_by_id.values(), key=lambda item: (item["sort_order"], item["name"])):
            parent = nodes_by_id.get(str(node["parent_id"]))
            if parent is None:
                roots.append(node)
            else:
                parent["children"].append(node)
        return roots

    @staticmethod
    def _flatten_intent_tree(roots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        flattened: list[dict[str, Any]] = []

        def visit(node: dict[str, Any], ancestors: list[dict[str, Any]]) -> None:
            path_parts = [str(item.get("name") or "").strip() for item in [*ancestors, node]]
            ancestor_text = " ".join(
                " ".join(
                    str(part or "")
                    for part in [
                        item.get("name"),
                        item.get("code"),
                        item.get("description"),
                        item.get("rule_snippet"),
                        item.get("prompt_template"),
                        " ".join(str(question) for question in item.get("sample_questions") or []),
                    ]
                )
                for item in [*ancestors, node]
            )
            item = {**node}
            item["path"] = " / ".join(part for part in path_parts if part) or str(node.get("name") or "")
            item["match_text"] = ancestor_text
            flattened.append(item)
            for child in sorted(node.get("children") or [], key=lambda child: (child.get("sort_order") or 0, child.get("name") or "")):
                visit(child, [*ancestors, node])

        for root in sorted(roots, key=lambda item: (item.get("sort_order") or 0, item.get("name") or "")):
            visit(root, [])
        return flattened

    @staticmethod
    def _resolve_kb_target_node(node: dict[str, Any]) -> dict[str, Any] | None:
        if str(node.get("knowledge_base_id") or "").strip():
            return node

        descendants: list[dict[str, Any]] = []

        def collect(current: dict[str, Any], parent_path: str) -> None:
            for child in current.get("children") or []:
                child_path = " / ".join(part for part in [parent_path, str(child.get("name") or "")] if part)
                child = {**child, "path": child_path}
                if str(child.get("knowledge_base_id") or "").strip():
                    descendants.append(child)
                collect(child, child_path)

        collect(node, str(node.get("path") or node.get("name") or ""))
        if not descendants:
            return None
        descendants.sort(key=lambda item: (int(item.get("sort_order") or 0), str(item.get("name") or "")))
        return descendants[0]

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

