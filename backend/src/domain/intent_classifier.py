from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.config import get_settings
from domain.llm import RetriFlowLLMService


@dataclass
class IntentDecision:
    intent: str
    confidence: float
    reason: str
    source: str
    clarification_question: str = ""


class RetriFlowIntentClassifier:
    TOOL_KEYWORDS = (
        "天气",
        "气温",
        "销售",
        "销量",
        "业绩",
        "工单",
        "机票",
        "火车票",
        "weather",
        "sales",
        "ticket",
    )
    KNOWLEDGE_HINTS = (
        "知识库",
        "文档",
        "说明",
        "流程",
        "迁移",
        "部署",
        "方案",
        "原理",
        "对比",
        "总结",
        "retriflow",
        "ragent",
        "langchain",
        "langgraph",
        "rag",
    )
    CHITCHAT_KEYWORDS = (
        "你好",
        "您好",
        "嗨",
        "hello",
        "hi",
        "谢谢",
        "感谢",
        "你是谁",
        "介绍一下你自己",
        "聊聊",
    )
    AMBIGUOUS_REFERENCES = (
        "这个",
        "那个",
        "它",
        "上面那个",
        "刚才那个",
        "这个东西",
    )
    VALID_INTENTS = {
        "knowledge_retrieval",
        "tool_call",
        "chitchat",
        "clarification",
    }
    SYSTEM_PROMPT = (
        "你是 RetriFlow 的意图识别器。"
        "请根据对话历史和用户最新问题，将意图分类为以下四种之一："
        "knowledge_retrieval、tool_call、chitchat、clarification。"
        "knowledge_retrieval 表示应该查询知识库；"
        "tool_call 表示应该调用工具或外部 API；"
        "chitchat 表示闲聊或无需检索的直接对话；"
        "clarification 表示问题信息不足，需要先反问用户。"
        "必须返回 JSON，格式为 "
        "{\"intent\":\"knowledge_retrieval\",\"confidence\":0.9,"
        "\"reason\":\"...\",\"clarification_question\":\"...\"}。"
        "如果不是 clarification，clarification_question 返回空字符串。"
    )

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = RetriFlowLLMService()

    def classify(
        self,
        *,
        question: str,
        memory_messages: list[dict[str, str]],
    ) -> IntentDecision:
        normalized_question = question.strip()
        if not normalized_question:
            return self._fallback_decision(reason="empty question")

        rule_decision = self._classify_with_rules(
            question=normalized_question,
            memory_messages=memory_messages,
        )
        if rule_decision is not None:
            return rule_decision

        llm_decision = self._classify_with_llm(
            question=normalized_question,
            memory_messages=memory_messages,
        )
        if llm_decision is not None:
            return llm_decision

        return self._fallback_decision(reason="intent classifier unavailable")

    def _classify_with_rules(
        self,
        *,
        question: str,
        memory_messages: list[dict[str, str]],
    ) -> IntentDecision | None:
        lowered = question.lower()

        if any(keyword.lower() in lowered for keyword in self.CHITCHAT_KEYWORDS):
            return IntentDecision(
                intent="chitchat",
                confidence=0.88,
                reason="matched chitchat keywords",
                source="rule",
            )

        if self._looks_like_missing_context(question=question, memory_messages=memory_messages):
            return IntentDecision(
                intent="clarification",
                confidence=0.9,
                reason="question depends on missing referent",
                source="rule",
                clarification_question="你说的“这个”具体指哪个产品、订单或文档？",
            )

        if self._is_strong_tool_request(question):
            return IntentDecision(
                intent="tool_call",
                confidence=0.92,
                reason="matched strong tool keywords",
                source="rule",
            )

        return None

    def _classify_with_llm(
        self,
        *,
        question: str,
        memory_messages: list[dict[str, str]],
    ) -> IntentDecision | None:
        provider = self.llm_service._resolve_provider(capability="intent")
        if provider is None or provider.name == "disabled":
            return None

        try:
            payload = self.llm_service.extract_json_object(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=self._build_user_prompt(
                    question=question,
                    memory_messages=memory_messages,
                ),
                capability="intent",
            )
        except Exception:
            return None

        return self._normalize_llm_payload(payload)

    def _normalize_llm_payload(self, payload: dict[str, Any]) -> IntentDecision | None:
        intent = str(payload.get("intent", "")).strip()
        if intent not in self.VALID_INTENTS:
            return None

        confidence = float(payload.get("confidence", 0.0))
        if confidence < self.settings.intent_confidence_threshold:
            return None

        reason = str(payload.get("reason", "")).strip() or "classified by llm"
        clarification_question = str(payload.get("clarification_question", "")).strip()
        if intent == "clarification" and not clarification_question:
            clarification_question = "可以再具体说明一下你指的是哪一部分吗？"

        return IntentDecision(
            intent=intent,
            confidence=confidence,
            reason=reason,
            source="llm",
            clarification_question=clarification_question,
        )

    def _is_strong_tool_request(self, question: str) -> bool:
        lowered = question.lower()
        has_tool_keyword = any(keyword.lower() in lowered for keyword in self.TOOL_KEYWORDS)
        if not has_tool_keyword:
            return False

        has_knowledge_hint = any(keyword.lower() in lowered for keyword in self.KNOWLEDGE_HINTS)
        if has_knowledge_hint:
            return False

        conjunctions = ("并", "和", "一起", "同时", "顺便", "再", "总结", "说明", "对比")
        if any(token in question for token in conjunctions):
            return False

        return True

    @staticmethod
    def _looks_like_missing_context(
        *,
        question: str,
        memory_messages: list[dict[str, str]],
    ) -> bool:
        stripped = question.strip()
        if len(stripped) > 18:
            return False
        if not any(reference in stripped for reference in RetriFlowIntentClassifier.AMBIGUOUS_REFERENCES):
            return False

        recent_user_messages = [
            str(message.get("content", "")).strip()
            for message in memory_messages[-4:]
            if str(message.get("role", "")).strip() == "user"
        ]
        if not recent_user_messages:
            return True

        latest_context = " ".join(recent_user_messages[-2:]).strip()
        return not latest_context or latest_context == stripped

    @staticmethod
    def _build_user_prompt(
        *,
        question: str,
        memory_messages: list[dict[str, str]],
    ) -> str:
        history_lines: list[str] = []
        for message in memory_messages[-8:]:
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"system", "user", "assistant"} or not content:
                continue
            history_lines.append(f"{role}: {content}")

        history_text = "\n".join(history_lines) or "无"
        return f"对话历史：\n{history_text}\n\n用户最新问题：{question}"

    @staticmethod
    def _fallback_decision(reason: str) -> IntentDecision:
        return IntentDecision(
            intent="knowledge_retrieval",
            confidence=0.0,
            reason=reason,
            source="fallback",
        )
