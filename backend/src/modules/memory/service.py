from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from core.config import get_settings
from core.state import get_connection
from infra.llm import RetriFlowLLMService


@dataclass
class MemoryHistoryMessage:
    id: int
    role: str
    content: str
    created_at: str


@dataclass
class MemorySummary:
    content: str
    last_message_id: int
    updated_at: str
    expires_at: str


@dataclass
class ShortTermMemorySnapshot:
    summary: MemorySummary | None
    recent_messages: list[MemoryHistoryMessage]


@dataclass
class LayeredMemorySnapshot:
    short_term: ShortTermMemorySnapshot
    mid_term: list[str]
    long_term: list[str]


@dataclass
class MidTermMemoryItem:
    memory_type: str
    content: str


@dataclass
class LongTermMemoryItem:
    memory_type: str
    content: str


class RetriFlowConversationMemorySummaryGenerator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = RetriFlowLLMService()

    def generate(
        self,
        *,
        existing_summary: str,
        messages: list[MemoryHistoryMessage],
    ) -> str:
        if not messages:
            return existing_summary

        normalized_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.content.strip()
        ]
        if not normalized_messages:
            return existing_summary

        try:
            return self.llm_service.summarize_conversation(
                existing_summary=existing_summary,
                conversation_messages=normalized_messages,
                max_chars=self.settings.memory_summary_max_chars,
            )
        except Exception:
            return self._fallback_summary(existing_summary, normalized_messages)

    def _fallback_summary(
        self,
        existing_summary: str,
        messages: list[dict[str, str]],
    ) -> str:
        user_topics = [
            item["content"].strip()
            for item in messages
            if item["role"] == "user" and item["content"].strip()
        ]
        latest_topics = "；".join(user_topics[-4:])
        if existing_summary.strip() and latest_topics:
            summary = f"{existing_summary.strip()}；后续讨论：{latest_topics}"
        elif existing_summary.strip():
            summary = existing_summary.strip()
        elif latest_topics:
            summary = f"近期对话涉及：{latest_topics}"
        else:
            summary = "近期对话围绕已讨论主题继续推进。"
        return summary[: self.settings.memory_summary_max_chars].strip("； ")


class RetriFlowConversationMidMemoryExtractor:
    ALLOWED_TYPES = {"goal", "constraint", "resolved_item", "open_item"}

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = RetriFlowLLMService()

    def extract(
        self,
        *,
        session_id: str,
        messages: list[MemoryHistoryMessage],
        existing_items: list[str] | None = None,
    ) -> list[MidTermMemoryItem]:
        normalized_messages = [
            {"role": message.role, "content": message.content.strip()}
            for message in messages
            if message.content.strip()
        ]
        if not session_id.strip() or not normalized_messages:
            return []

        try:
            payload = self.llm_service.extract_json_object(
                system_prompt=self._build_system_prompt(),
                user_prompt=self._build_user_prompt(
                    existing_items=existing_items or [],
                    messages=normalized_messages,
                    max_items=self.settings.memory_mid_max_items,
                ),
            )
            items = self._normalize_items(payload.get("items", []))
            if items:
                return items[: self.settings.memory_mid_max_items]
        except Exception:
            pass

        return self._fallback_extract(normalized_messages)[: self.settings.memory_mid_max_items]

    def _normalize_items(self, raw_items: Any) -> list[MidTermMemoryItem]:
        if not isinstance(raw_items, list):
            return []

        normalized: list[MidTermMemoryItem] = []
        seen: set[tuple[str, str]] = set()
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            memory_type = str(item.get("memory_type", "")).strip()
            content = str(item.get("content", "")).strip()
            if memory_type not in self.ALLOWED_TYPES or not content:
                continue
            key = (memory_type, content)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(MidTermMemoryItem(memory_type=memory_type, content=content))
        return normalized

    def _fallback_extract(self, messages: list[dict[str, str]]) -> list[MidTermMemoryItem]:
        extracted: list[MidTermMemoryItem] = []
        seen: set[tuple[str, str]] = set()

        for message in messages:
            if message["role"] != "user":
                continue
            content = message["content"].strip()
            if not content:
                continue

            lower = content.lower()
            candidates: list[MidTermMemoryItem] = []

            if any(keyword in content for keyword in ("需要", "想要", "目标", "希望", "继续")):
                candidates.append(MidTermMemoryItem(memory_type="goal", content=content))
            if any(keyword in content for keyword in ("保持", "不要", "不能", "必须", "限制", "约束")):
                candidates.append(MidTermMemoryItem(memory_type="constraint", content=content))
            if any(keyword in content for keyword in ("待确认", "后续", "下一步", "还要", "还需要", "后面")):
                candidates.append(MidTermMemoryItem(memory_type="open_item", content=content))
            if "已完成" in content or "已经完成" in content or "done" in lower:
                candidates.append(MidTermMemoryItem(memory_type="resolved_item", content=content))

            for candidate in candidates:
                key = (candidate.memory_type, candidate.content)
                if key in seen:
                    continue
                seen.add(key)
                extracted.append(candidate)

        return extracted

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "你是 RetriFlow 的中期记忆提取器。"
            "请从对话中提取对后续多轮协作真正有价值的信息。"
            "只允许输出以下 memory_type：goal、constraint、resolved_item、open_item。"
            "不要复述闲聊，不要提取一次性细节，不要生成不存在的信息。"
            '必须返回 JSON，格式为 {"items":[{"memory_type":"goal","content":"..."}]}。'
        )

    @staticmethod
    def _build_user_prompt(
        *,
        existing_items: list[str],
        messages: list[dict[str, str]],
        max_items: int,
    ) -> str:
        lines = [
            "【已有中期记忆】",
            *([f"- {item}" for item in existing_items] or ["无"]),
            "",
            "【最近对话】",
        ]
        for message in messages:
            role = "用户" if message["role"] == "user" else "助手"
            lines.append(f"{role}：{message['content']}")
        lines.extend(
            [
                "",
                "【要求】",
                "提取后续多轮协作需要保留的目标、约束、已解决事项、待确认事项。",
                "避免和已有中期记忆重复。",
                f"最多返回 {max_items} 条。",
            ]
        )
        return "\n".join(lines)


class RetriFlowConversationLongMemoryExtractor:
    ALLOWED_TYPES = {"preference", "constraint", "profile", "stable_fact"}

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = RetriFlowLLMService()

    def extract(
        self,
        *,
        session_id: str,
        messages: list[MemoryHistoryMessage],
        existing_items: list[str] | None = None,
    ) -> list[LongTermMemoryItem]:
        normalized_messages = [
            {"role": message.role, "content": message.content.strip()}
            for message in messages
            if message.content.strip()
        ]
        if not session_id.strip() or not normalized_messages:
            return []

        try:
            payload = self.llm_service.extract_json_object(
                system_prompt=self._build_system_prompt(),
                user_prompt=self._build_user_prompt(
                    existing_items=existing_items or [],
                    messages=normalized_messages,
                    max_items=self.settings.memory_long_max_items,
                ),
            )
            items = self._normalize_items(payload.get("items", []))
            if items:
                return items[: self.settings.memory_long_max_items]
        except Exception:
            pass

        return self._fallback_extract(normalized_messages)[: self.settings.memory_long_max_items]

    def _normalize_items(self, raw_items: Any) -> list[LongTermMemoryItem]:
        if not isinstance(raw_items, list):
            return []

        normalized: list[LongTermMemoryItem] = []
        seen: set[tuple[str, str]] = set()
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            memory_type = str(item.get("memory_type", "")).strip()
            content = str(item.get("content", "")).strip()
            if memory_type not in self.ALLOWED_TYPES or not content:
                continue
            key = (memory_type, content)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(LongTermMemoryItem(memory_type=memory_type, content=content))
        return normalized

    def _fallback_extract(self, messages: list[dict[str, str]]) -> list[LongTermMemoryItem]:
        extracted: list[LongTermMemoryItem] = []
        seen: set[tuple[str, str]] = set()

        for message in messages:
            if message["role"] != "user":
                continue
            content = message["content"].strip()
            if not content:
                continue

            candidates: list[LongTermMemoryItem] = []
            if any(keyword in content for keyword in ("偏好", "喜欢", "尽量", "习惯")):
                candidates.append(LongTermMemoryItem(memory_type="preference", content=content))
            if any(keyword in content for keyword in ("保持", "不要", "不能", "必须", "约束", "限制")):
                candidates.append(LongTermMemoryItem(memory_type="constraint", content=content))
            if any(keyword in content for keyword in ("我是", "我们是", "我的角色", "团队")):
                candidates.append(LongTermMemoryItem(memory_type="profile", content=content))
            if any(keyword in content for keyword in ("一直", "长期", "固定", "默认")):
                candidates.append(LongTermMemoryItem(memory_type="stable_fact", content=content))

            for candidate in candidates:
                key = (candidate.memory_type, candidate.content)
                if key in seen:
                    continue
                seen.add(key)
                extracted.append(candidate)

        return extracted

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "你是 RetriFlow 的长期记忆提取器。"
            "请从对话中提取适合长期保留的稳定信息。"
            "只允许输出以下 memory_type：preference、constraint、profile、stable_fact。"
            "不要提取一次性任务细节，不要编造信息。"
            '必须返回 JSON，格式为 {"items":[{"memory_type":"preference","content":"..."}]}。'
        )

    @staticmethod
    def _build_user_prompt(
        *,
        existing_items: list[str],
        messages: list[dict[str, str]],
        max_items: int,
    ) -> str:
        lines = [
            "【已有长期记忆】",
            *([f"- {item}" for item in existing_items] or ["无"]),
            "",
            "【最近对话】",
        ]
        for message in messages:
            role = "用户" if message["role"] == "user" else "助手"
            lines.append(f"{role}：{message['content']}")
        lines.extend(
            [
                "",
                "【要求】",
                "只提取长期稳定有效的偏好、约束、身份画像或稳定事实。",
                "避免和已有长期记忆重复。",
                f"最多返回 {max_items} 条。",
            ]
        )
        return "\n".join(lines)


class RetriFlowConversationMemoryService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.summary_generator = RetriFlowConversationMemorySummaryGenerator()
        self.mid_term_extractor = RetriFlowConversationMidMemoryExtractor()
        self.long_term_extractor = RetriFlowConversationLongMemoryExtractor()

    def load_short_term_memory(
        self,
        session_id: str,
        *,
        now: str | None = None,
    ) -> ShortTermMemorySnapshot:
        current_time = self._resolve_now(now)
        self._cleanup_expired_memory(session_id=session_id, now=current_time)
        summary = self._load_latest_summary(session_id=session_id, now=current_time)
        recent_messages = self._load_recent_messages(session_id=session_id, now=current_time)
        return ShortTermMemorySnapshot(summary=summary, recent_messages=recent_messages)

    def load_mid_term_memory(
        self,
        session_id: str,
        *,
        now: str | None = None,
    ) -> list[str]:
        if not self.settings.memory_mid_enabled:
            return []
        current_time = self._resolve_now(now)
        with get_connection() as connection:
            rows = connection.execute(
                """
                select content
                from conversation_mid_memories
                where session_id = ?
                  and status = ?
                  and (expires_at is null or expires_at > ?)
                order by updated_at desc, id desc
                limit ?
                """,
                (
                    session_id,
                    "active",
                    self._format_datetime(current_time),
                    self.settings.memory_mid_max_items,
                ),
            ).fetchall()
        return [str(row["content"]).strip() for row in rows if str(row["content"]).strip()]

    def load_long_term_memory(
        self,
        session_id: str,
        *,
        now: str | None = None,
    ) -> list[str]:
        if not self.settings.memory_long_enabled:
            return []
        current_time = self._resolve_now(now)
        owner_type, owner_id = self._resolve_long_term_owner(session_id)
        with get_connection() as connection:
            rows = connection.execute(
                """
                select content
                from conversation_long_memories
                where owner_type = ?
                  and owner_id = ?
                  and status = ?
                  and (expires_at is null or expires_at > ?)
                order by updated_at desc, id desc
                limit ?
                """,
                (
                    owner_type,
                    owner_id,
                    "active",
                    self._format_datetime(current_time),
                    self.settings.memory_long_max_items,
                ),
            ).fetchall()
        return [str(row["content"]).strip() for row in rows if str(row["content"]).strip()]

    def load_layered_memory(
        self,
        session_id: str,
        *,
        now: str | None = None,
    ) -> LayeredMemorySnapshot:
        return LayeredMemorySnapshot(
            short_term=self.load_short_term_memory(session_id, now=now),
            mid_term=self.load_mid_term_memory(session_id, now=now),
            long_term=self.load_long_term_memory(session_id, now=now),
        )

    def load_prompt_messages(
        self,
        session_id: str,
        *,
        query: str = "",
        now: str | None = None,
    ) -> list[dict[str, str]]:
        if not session_id.strip():
            return []

        layered = self.load_layered_memory(session_id=session_id, now=now)
        prompt_messages: list[dict[str, str]] = []
        selected_mid_term = self._select_memory_items_for_prompt(
            layered.mid_term,
            query=query,
            limit=self.settings.memory_mid_prompt_max_items,
        )
        selected_long_term = self._select_memory_items_for_prompt(
            layered.long_term,
            query=query,
            limit=self.settings.memory_long_prompt_max_items,
        )

        if layered.short_term.summary is not None:
            prompt_messages.append(
                {
                    "role": "system",
                    "content": f"对话摘要\n{layered.short_term.summary.content}",
                }
            )

        if selected_mid_term:
            prompt_messages.append(
                {
                    "role": "system",
                    "content": "中期记忆\n" + "\n".join(f"- {item}" for item in selected_mid_term),
                }
            )

        if selected_long_term:
            prompt_messages.append(
                {
                    "role": "system",
                    "content": "长期记忆\n" + "\n".join(f"- {item}" for item in selected_long_term),
                }
            )

        for message in layered.short_term.recent_messages:
            prompt_messages.append({"role": message.role, "content": message.content})

        return prompt_messages

    def update_short_term_memory(
        self,
        session_id: str,
        *,
        now: str | None = None,
    ) -> None:
        if not self.settings.memory_summary_enabled or not session_id.strip():
            return

        current_time = self._resolve_now(now)
        self._cleanup_expired_memory(session_id=session_id, now=current_time)
        active_messages = self._load_active_messages(session_id=session_id, now=current_time)
        normalized_messages = self._normalize_messages(active_messages)
        user_turns = sum(1 for message in normalized_messages if message.role == "user")

        if user_turns < self.settings.memory_summary_start_turns:
            return

        keep_message_count = max(0, self.settings.memory_history_keep_turns * 2)
        if len(normalized_messages) <= keep_message_count:
            return

        cutoff_message = normalized_messages[-keep_message_count]
        latest_summary = self._load_latest_summary(session_id=session_id, now=current_time)
        start_after_id = latest_summary.last_message_id if latest_summary is not None else 0
        to_summarize = [
            message
            for message in normalized_messages
            if start_after_id < message.id < cutoff_message.id
        ]
        if not to_summarize:
            return

        summary = self.summary_generator.generate(
            existing_summary=latest_summary.content if latest_summary is not None else "",
            messages=to_summarize,
        ).strip()
        if not summary:
            return

        expires_at = current_time + timedelta(days=max(1, self.settings.memory_short_ttl_days))
        with get_connection() as connection:
            connection.execute(
                """
                insert into conversation_memory_summaries (
                    session_id,
                    content,
                    last_message_id,
                    updated_at,
                    expires_at
                )
                values (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    summary,
                    to_summarize[-1].id,
                    self._format_datetime(current_time),
                    self._format_datetime(expires_at),
                ),
            )
            connection.commit()

    def update_mid_term_memory(
        self,
        session_id: str,
        *,
        now: str | None = None,
    ) -> None:
        if not self.settings.memory_mid_enabled or not session_id.strip():
            return

        current_time = self._resolve_now(now)
        self._cleanup_expired_memory(session_id=session_id, now=current_time)
        active_messages = self._load_active_messages(session_id=session_id, now=current_time)
        normalized_messages = self._normalize_messages(active_messages)
        if not normalized_messages:
            return

        recent_window_size = max(6, self.settings.memory_history_keep_turns * 2 + 2)
        recent_messages = normalized_messages[-recent_window_size:]
        existing_items = self.load_mid_term_memory(
            session_id=session_id,
            now=current_time.isoformat(),
        )
        extracted_items = self.mid_term_extractor.extract(
            session_id=session_id,
            messages=recent_messages,
            existing_items=existing_items,
        )
        if not extracted_items:
            return

        self._save_mid_term_items(
            session_id=session_id,
            items=extracted_items,
            now=current_time,
        )

    def update_long_term_memory(
        self,
        session_id: str,
        *,
        now: str | None = None,
    ) -> None:
        if not self.settings.memory_long_enabled or not session_id.strip():
            return

        current_time = self._resolve_now(now)
        self._cleanup_expired_memory(session_id=session_id, now=current_time)
        active_messages = self._load_active_messages(session_id=session_id, now=current_time)
        normalized_messages = self._normalize_messages(active_messages)
        if not normalized_messages:
            return

        recent_window_size = max(8, self.settings.memory_history_keep_turns * 2 + 4)
        recent_messages = normalized_messages[-recent_window_size:]
        existing_items = self.load_long_term_memory(
            session_id=session_id,
            now=current_time.isoformat(),
        )
        extracted_items = self.long_term_extractor.extract(
            session_id=session_id,
            messages=recent_messages,
            existing_items=existing_items,
        )
        if not extracted_items:
            return

        self._save_long_term_items(
            session_id=session_id,
            items=extracted_items,
            now=current_time,
        )

    def _save_mid_term_items(
        self,
        *,
        session_id: str,
        items: list[MidTermMemoryItem],
        now: datetime,
    ) -> None:
        if not items:
            return

        current = self._format_datetime(now)
        expires_at = self._format_datetime(
            now + timedelta(days=max(1, self.settings.memory_mid_ttl_days))
        )
        with get_connection() as connection:
            rows = connection.execute(
                """
                select memory_type, content
                from conversation_mid_memories
                where session_id = ?
                  and status = ?
                """,
                (session_id, "active"),
            ).fetchall()
            existing_pairs = {
                (str(row["memory_type"]).strip(), str(row["content"]).strip())
                for row in rows
                if str(row["memory_type"]).strip() and str(row["content"]).strip()
            }

            for item in items[: self.settings.memory_mid_max_items]:
                key = (item.memory_type.strip(), item.content.strip())
                if key in existing_pairs or not key[0] or not key[1]:
                    continue
                connection.execute(
                    """
                    insert into conversation_mid_memories (
                        session_id,
                        memory_type,
                        content,
                        status,
                        updated_at,
                        expires_at
                    )
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        item.memory_type.strip(),
                        item.content.strip(),
                        "active",
                        current,
                        expires_at,
                    ),
                )
                existing_pairs.add(key)

            active_rows = connection.execute(
                """
                select id
                from conversation_mid_memories
                where session_id = ?
                  and status = ?
                order by updated_at desc, id desc
                """,
                (session_id, "active"),
            ).fetchall()
            overflow_ids = [
                int(row["id"])
                for row in active_rows[self.settings.memory_mid_max_items :]
            ]
            for memory_id in overflow_ids:
                connection.execute(
                    """
                    update conversation_mid_memories
                    set status = ?
                    where id = ?
                    """,
                    ("inactive", memory_id),
                )
            connection.commit()

    def _save_long_term_items(
        self,
        *,
        session_id: str,
        items: list[LongTermMemoryItem],
        now: datetime,
    ) -> None:
        if not items:
            return

        current = self._format_datetime(now)
        expires_at = self._format_datetime(
            now + timedelta(days=max(1, self.settings.memory_long_ttl_days))
        )
        owner_type, owner_id = self._resolve_long_term_owner(session_id)
        with get_connection() as connection:
            rows = connection.execute(
                """
                select memory_type, content
                from conversation_long_memories
                where owner_type = ?
                  and owner_id = ?
                  and status = ?
                """,
                (owner_type, owner_id, "active"),
            ).fetchall()
            existing_pairs = {
                (str(row["memory_type"]).strip(), str(row["content"]).strip())
                for row in rows
                if str(row["memory_type"]).strip() and str(row["content"]).strip()
            }
            existing_by_type: dict[str, set[str]] = {}
            for memory_type, content in existing_pairs:
                existing_by_type.setdefault(memory_type, set()).add(content)

            for item in items[: self.settings.memory_long_max_items]:
                key = (item.memory_type.strip(), item.content.strip())
                if key in existing_pairs or not key[0] or not key[1]:
                    continue
                if key[0] in existing_by_type and key[1] not in existing_by_type[key[0]]:
                    connection.execute(
                        """
                        update conversation_long_memories
                        set status = ?
                        where owner_type = ?
                          and owner_id = ?
                          and memory_type = ?
                          and status = ?
                        """,
                        ("inactive", owner_type, owner_id, key[0], "active"),
                    )
                    existing_pairs = {pair for pair in existing_pairs if pair[0] != key[0]}
                    existing_by_type[key[0]] = set()
                connection.execute(
                    """
                    insert into conversation_long_memories (
                        owner_type,
                        owner_id,
                        memory_type,
                        content,
                        status,
                        updated_at,
                        expires_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        owner_type,
                        owner_id,
                        item.memory_type.strip(),
                        item.content.strip(),
                        "active",
                        current,
                        expires_at,
                    ),
                )
                existing_pairs.add(key)
                existing_by_type.setdefault(key[0], set()).add(key[1])

            active_rows = connection.execute(
                """
                select id
                from conversation_long_memories
                where owner_type = ?
                  and owner_id = ?
                  and status = ?
                order by updated_at desc, id desc
                """,
                (owner_type, owner_id, "active"),
            ).fetchall()
            overflow_ids = [
                int(row["id"])
                for row in active_rows[self.settings.memory_long_max_items :]
            ]
            for memory_id in overflow_ids:
                connection.execute(
                    """
                    update conversation_long_memories
                    set status = ?
                    where id = ?
                    """,
                    ("inactive", memory_id),
                )
            connection.commit()

    @staticmethod
    def _resolve_long_term_owner(session_id: str) -> tuple[str, str]:
        with get_connection() as connection:
            row = connection.execute(
                """
                select owner_id
                from sessions
                where id = ?
                limit 1
                """,
                (session_id,),
            ).fetchone()

        if row is not None:
            owner_id = str(row.get("owner_id", "") or "").strip()
            if owner_id:
                return ("user", owner_id)
        return ("session", session_id)

    def _load_recent_messages(
        self,
        session_id: str,
        *,
        now: datetime,
    ) -> list[MemoryHistoryMessage]:
        active_messages = self._load_active_messages(session_id=session_id, now=now)
        normalized = self._normalize_messages(active_messages)
        keep_message_count = max(0, self.settings.memory_history_keep_turns * 2)
        if keep_message_count <= 0:
            return []
        return normalized[-keep_message_count:]

    def _load_active_messages(
        self,
        session_id: str,
        *,
        now: datetime,
    ) -> list[MemoryHistoryMessage]:
        cutoff = now - timedelta(days=max(1, self.settings.memory_short_ttl_days))
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, role, content, created_at
                from conversation_messages
                where session_id = ?
                  and role in (?, ?)
                  and created_at >= ?
                order by id
                """,
                (
                    session_id,
                    "user",
                    "assistant",
                    self._format_datetime(cutoff),
                ),
            ).fetchall()

        return [
            MemoryHistoryMessage(
                id=int(row["id"]),
                role=str(row["role"]),
                content=str(row["content"]),
                created_at=self._serialize_timestamp(row["created_at"]),
            )
            for row in rows
            if str(row["content"]).strip()
        ]

    def _load_latest_summary(
        self,
        session_id: str,
        *,
        now: datetime,
    ) -> MemorySummary | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                select content, last_message_id, updated_at, expires_at
                from conversation_memory_summaries
                where session_id = ?
                  and (expires_at is null or expires_at > ?)
                order by id desc
                limit 1
                """,
                (session_id, self._format_datetime(now)),
            ).fetchone()

        if row is None:
            return None
        return MemorySummary(
            content=str(row["content"]),
            last_message_id=int(row["last_message_id"]),
            updated_at=self._serialize_timestamp(row["updated_at"]),
            expires_at=self._serialize_timestamp(row["expires_at"]),
        )

    def _cleanup_expired_memory(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> None:
        current = self._format_datetime(now)
        owner_type, owner_id = self._resolve_long_term_owner(session_id)
        with get_connection() as connection:
            connection.execute(
                """
                delete from conversation_memory_summaries
                where session_id = ?
                  and expires_at is not null
                  and expires_at <= ?
                """,
                (session_id, current),
            )
            connection.execute(
                """
                delete from conversation_mid_memories
                where session_id = ?
                  and expires_at is not null
                  and expires_at <= ?
                """,
                (session_id, current),
            )
            connection.execute(
                """
                delete from conversation_long_memories
                where owner_type = ?
                  and owner_id = ?
                  and expires_at is not null
                  and expires_at <= ?
                """,
                (owner_type, owner_id, current),
            )
            connection.commit()

    @staticmethod
    def _select_memory_items_for_prompt(
        items: list[str],
        *,
        query: str,
        limit: int,
    ) -> list[str]:
        normalized = [item.strip() for item in items if item.strip()]
        if not normalized or limit <= 0:
            return []
        if not query.strip():
            return normalized[:limit]

        ranked = sorted(
            normalized,
            key=lambda item: (
                RetriFlowConversationMemoryService._memory_relevance_score(item, query),
                len(item),
            ),
            reverse=True,
        )
        return ranked[:limit]

    @staticmethod
    def _memory_relevance_score(item: str, query: str) -> int:
        item_lower = item.lower()
        query_tokens = [
            token.strip()
            for token in query.lower().replace("，", " ").replace("。", " ").replace(",", " ").split()
            if token.strip()
        ]
        if not query_tokens:
            return 0

        score = 0
        for token in query_tokens:
            if token in item_lower:
                score += max(1, len(token))

        for char in query:
            if char.strip() and char in item:
                score += 1
        return score

    @staticmethod
    def _normalize_messages(messages: list[MemoryHistoryMessage]) -> list[MemoryHistoryMessage]:
        if not messages:
            return []
        for index, message in enumerate(messages):
            if message.role == "user":
                return messages[index:]
        return messages

    @staticmethod
    def _resolve_now(now: str | None) -> datetime:
        if not now:
            return datetime.now()
        return datetime.fromisoformat(now)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.isoformat(sep=" ", timespec="seconds")

    @staticmethod
    def _serialize_timestamp(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

