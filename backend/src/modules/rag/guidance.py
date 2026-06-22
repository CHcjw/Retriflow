from __future__ import annotations

from dataclasses import dataclass

from modules.knowledge.routing import KnowledgeRouteDecision


@dataclass(frozen=True)
class GuidanceDecision:
    prompt: str = ""

    @property
    def is_prompt(self) -> bool:
        return bool(self.prompt.strip())


class RetriFlowIntentGuidanceService:
    AMBIGUITY_SCORE_RATIO = 0.8
    AMBIGUITY_MARGIN = 0.15
    MAX_OPTIONS = 3

    def detect(self, question: str, route_decision: KnowledgeRouteDecision) -> GuidanceDecision:
        candidates = route_decision.candidates[: self.MAX_OPTIONS]
        if len(candidates) < 2:
            return GuidanceDecision()

        top_score = candidates[0].score
        second_score = candidates[1].score
        if top_score <= 0:
            return GuidanceDecision()
        if second_score / top_score < self.AMBIGUITY_SCORE_RATIO - self.AMBIGUITY_MARGIN:
            return GuidanceDecision()
        if self._question_mentions_candidate(question, candidates):
            return GuidanceDecision()

        option_lines = []
        for index, candidate in enumerate(candidates, start=1):
            label = candidate.path or candidate.name or candidate.knowledge_base_id
            option_lines.append(f"{index}. {label}")
        return GuidanceDecision(
            prompt=(
                "我找到了多个可能相关的知识范围，需要你再明确一下想问哪一类：\n"
                + "\n".join(option_lines)
                + "\n请补充一个范围或关键词后我再继续检索。"
            )
        )

    @staticmethod
    def _question_mentions_candidate(question: str, candidates) -> bool:
        normalized_question = question.lower()
        for candidate in candidates:
            names = [candidate.name, candidate.path, candidate.knowledge_base_id]
            if any(name and str(name).lower() in normalized_question for name in names):
                return True
        return False
