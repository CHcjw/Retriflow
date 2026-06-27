import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_PATH))


class RetriFlowConversationMemoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / f"retriflow-{uuid.uuid4().hex}.db"
        os.environ["RETRIFLOW_DATABASE_BACKEND"] = "sqlite"
        os.environ["RETRIFLOW_DB_PATH"] = str(self.db_path)
        os.environ["RETRIFLOW_DATABASE_DSN"] = ""
        os.environ["RETRIFLOW_PGVECTOR_DSN"] = ""
        os.environ["RETRIFLOW_VECTOR_STORE_TYPE"] = "memory"
        os.environ["RETRIFLOW_LLM_PROVIDER"] = "disabled"
        os.environ["RETRIFLOW_SEED_DEMO_CONTENT"] = "true"
        os.environ["RETRIFLOW_MEMORY_HISTORY_KEEP_TURNS"] = "2"
        os.environ["RETRIFLOW_MEMORY_SUMMARY_ENABLED"] = "true"
        os.environ["RETRIFLOW_MEMORY_SUMMARY_START_TURNS"] = "3"
        os.environ["RETRIFLOW_MEMORY_SUMMARY_MAX_CHARS"] = "120"
        os.environ["RETRIFLOW_MEMORY_SHORT_TTL_DAYS"] = "30"
        os.environ["RETRIFLOW_MEMORY_MID_ENABLED"] = "true"
        os.environ["RETRIFLOW_MEMORY_MID_MAX_ITEMS"] = "4"
        os.environ["RETRIFLOW_MEMORY_MID_TTL_DAYS"] = "14"
        os.environ["RETRIFLOW_MEMORY_MID_PROMPT_MAX_ITEMS"] = "3"
        os.environ["RETRIFLOW_MEMORY_LONG_ENABLED"] = "true"
        os.environ["RETRIFLOW_MEMORY_LONG_MAX_ITEMS"] = "3"
        os.environ["RETRIFLOW_MEMORY_LONG_TTL_DAYS"] = "180"
        os.environ["RETRIFLOW_MEMORY_LONG_PROMPT_MAX_ITEMS"] = "2"

        from core.config import get_settings
        from core.state import initialize_database

        get_settings.cache_clear()
        initialize_database()

    def tearDown(self) -> None:
        for key in (
            "RETRIFLOW_DATABASE_BACKEND",
            "RETRIFLOW_DB_PATH",
            "RETRIFLOW_DATABASE_DSN",
            "RETRIFLOW_PGVECTOR_DSN",
            "RETRIFLOW_VECTOR_STORE_TYPE",
            "RETRIFLOW_LLM_PROVIDER",
            "RETRIFLOW_SEED_DEMO_CONTENT",
            "RETRIFLOW_MEMORY_HISTORY_KEEP_TURNS",
            "RETRIFLOW_MEMORY_SUMMARY_ENABLED",
            "RETRIFLOW_MEMORY_SUMMARY_START_TURNS",
            "RETRIFLOW_MEMORY_SUMMARY_MAX_CHARS",
            "RETRIFLOW_MEMORY_SHORT_TTL_DAYS",
            "RETRIFLOW_MEMORY_MID_ENABLED",
            "RETRIFLOW_MEMORY_MID_MAX_ITEMS",
            "RETRIFLOW_MEMORY_MID_TTL_DAYS",
            "RETRIFLOW_MEMORY_MID_PROMPT_MAX_ITEMS",
            "RETRIFLOW_MEMORY_LONG_ENABLED",
            "RETRIFLOW_MEMORY_LONG_MAX_ITEMS",
            "RETRIFLOW_MEMORY_LONG_TTL_DAYS",
            "RETRIFLOW_MEMORY_LONG_PROMPT_MAX_ITEMS",
            "RETRIFLOW_DISTRIBUTED_LOCK_BACKEND",
        ):
            os.environ.pop(key, None)

        from core.config import get_settings

        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def _insert_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        created_at: str = "2026-06-09 10:00:00",
    ) -> int:
        from core.state import get_connection

        with get_connection() as connection:
            cursor = connection.execute(
                """
                insert into conversation_messages (session_id, role, content, created_at)
                values (?, ?, ?, ?)
                """,
                (session_id, role, content, created_at),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def test_load_short_term_memory_returns_summary_and_recent_turns(self) -> None:
        from core.state import get_connection
        from modules.memory import RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        with get_connection() as connection:
            connection.execute(
                """
                insert into conversation_memory_summaries (session_id, content, last_message_id, updated_at)
                values (?, ?, ?, ?)
                """,
                (
                    session_id,
                    "用户之前主要在讨论迁移方案和部署限制。",
                    2,
                    "2026-06-09 09:00:00",
                ),
            )
            connection.commit()

        self._insert_message(session_id, "user", "第一轮用户问题")
        self._insert_message(session_id, "assistant", "第一轮助手回答")
        self._insert_message(session_id, "user", "第二轮用户问题")
        self._insert_message(session_id, "assistant", "第二轮助手回答")
        self._insert_message(session_id, "user", "第三轮用户问题")
        self._insert_message(session_id, "assistant", "第三轮助手回答")

        memory = RetriFlowConversationMemoryService().load_short_term_memory(session_id)

        self.assertIsNotNone(memory.summary)
        self.assertIn("迁移方案", memory.summary.content)
        self.assertEqual(len(memory.recent_messages), 4)
        self.assertEqual(memory.recent_messages[0].content, "第二轮用户问题")
        self.assertEqual(memory.recent_messages[-1].content, "第三轮助手回答")

    def test_load_short_term_memory_filters_expired_messages(self) -> None:
        from modules.memory import RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        self._insert_message(
            session_id,
            "user",
            "已经过期的历史消息",
            created_at="2026-01-01 08:00:00",
        )
        self._insert_message(
            session_id,
            "assistant",
            "最近的助手消息",
            created_at="2026-06-09 08:00:00",
        )

        memory = RetriFlowConversationMemoryService().load_short_term_memory(
            session_id,
            now="2026-06-09T12:00:00",
        )

        self.assertEqual(len(memory.recent_messages), 1)
        self.assertEqual(memory.recent_messages[0].content, "最近的助手消息")

    def test_update_short_term_memory_creates_summary_after_threshold(self) -> None:
        from core.state import get_connection
        from modules.memory import RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        for index in range(1, 5):
            self._insert_message(session_id, "user", f"用户问题{index}")
            self._insert_message(session_id, "assistant", f"助手回答{index}")

        with patch(
            "modules.memory.service.RetriFlowConversationMemorySummaryGenerator.generate",
            return_value="用户咨询了前期迁移问题、部署限制和当前待确认事项。",
        ) as generate:
            RetriFlowConversationMemoryService().update_short_term_memory(session_id)

        with get_connection() as connection:
            rows = connection.execute(
                """
                select content, last_message_id
                from conversation_memory_summaries
                where session_id = ?
                order by id desc
                """,
                (session_id,),
            ).fetchall()

        self.assertTrue(rows)
        self.assertIn("迁移问题", rows[0]["content"])
        self.assertGreater(int(rows[0]["last_message_id"]), 0)
        generate.assert_called_once()

    def test_update_short_term_memory_skips_when_lock_is_busy(self) -> None:
        from contextlib import contextmanager

        from core.state import get_connection
        from modules.memory import RetriFlowConversationMemoryService

        session_id = "session-lock-busy"
        for index in range(1, 5):
            self._insert_message(session_id, "user", f"user question {index}")
            self._insert_message(session_id, "assistant", f"assistant answer {index}")

        @contextmanager
        def busy_lock(*args, **kwargs):
            yield False

        with patch("modules.memory.service.get_distributed_lock_service") as lock_factory:
            lock_factory.return_value.acquire.side_effect = busy_lock
            with patch(
                "modules.memory.service.RetriFlowConversationMemorySummaryGenerator.generate",
                return_value="summary",
            ) as generate:
                RetriFlowConversationMemoryService().update_short_term_memory(session_id)

        with get_connection() as connection:
            count = connection.execute(
                "select count(*) from conversation_memory_summaries where session_id = ?",
                (session_id,),
            ).fetchone()[0]

        self.assertEqual(count, 0)
        generate.assert_not_called()

    def test_update_mid_term_memory_persists_structured_items(self) -> None:
        from core.state import get_connection
        from modules.memory import MidTermMemoryItem, RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        self._insert_message(session_id, "user", "我需要继续完善 RetriFlow 的中期记忆。")
        self._insert_message(session_id, "assistant", "我会先把目标、约束和待确认事项提炼出来。")

        with patch(
            "modules.memory.service.RetriFlowConversationMidMemoryExtractor.extract",
            return_value=[
                MidTermMemoryItem(memory_type="goal", content="继续完善 RetriFlow 的中期记忆"),
                MidTermMemoryItem(memory_type="constraint", content="保持现有模型选择不变"),
                MidTermMemoryItem(memory_type="open_item", content="确认长期记忆如何持久化"),
            ],
        ) as extract:
            RetriFlowConversationMemoryService().update_mid_term_memory(session_id)

        with get_connection() as connection:
            rows = connection.execute(
                """
                select memory_type, content, status
                from conversation_mid_memories
                where session_id = ?
                order by id
                """,
                (session_id,),
            ).fetchall()

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["memory_type"], "goal")
        self.assertEqual(rows[0]["status"], "active")
        self.assertIn("中期记忆", rows[0]["content"])
        self.assertEqual(rows[2]["memory_type"], "open_item")
        extract.assert_called_once()

    def test_update_mid_term_memory_sets_expires_at(self) -> None:
        from core.state import get_connection
        from modules.memory import MidTermMemoryItem, RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        self._insert_message(session_id, "user", "请继续完善会话任务记忆")
        self._insert_message(session_id, "assistant", "我会补充 TTL 和状态治理")

        with patch(
            "modules.memory.service.RetriFlowConversationMidMemoryExtractor.extract",
            return_value=[MidTermMemoryItem(memory_type="goal", content="完善中期记忆 TTL")],
        ):
            RetriFlowConversationMemoryService().update_mid_term_memory(
                session_id,
                now="2026-06-09T10:00:00",
            )

        with get_connection() as connection:
            row = connection.execute(
                """
                select expires_at
                from conversation_mid_memories
                where session_id = ?
                order by id desc
                limit 1
                """,
                (session_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["expires_at"], "2026-06-23 10:00:00")

    def test_load_prompt_messages_includes_mid_term_memory_block(self) -> None:
        from core.state import get_connection
        from modules.memory import RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        with get_connection() as connection:
            connection.execute(
                """
                insert into conversation_mid_memories (
                    session_id,
                    memory_type,
                    content,
                    status,
                    updated_at
                )
                values (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    "goal",
                    "完成 RetriFlow 会话记忆设计",
                    "active",
                    "2026-06-09 10:00:00",
                ),
            )
            connection.execute(
                """
                insert into conversation_mid_memories (
                    session_id,
                    memory_type,
                    content,
                    status,
                    updated_at
                )
                values (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    "constraint",
                    "保持现有模型配置不变",
                    "active",
                    "2026-06-09 10:01:00",
                ),
            )
            connection.commit()

        prompt_messages = RetriFlowConversationMemoryService().load_prompt_messages(session_id)

        mid_term_block = next(
            message for message in prompt_messages if message["role"] == "system" and "中期记忆" in message["content"]
        )
        self.assertIn("完成 RetriFlow 会话记忆设计", mid_term_block["content"])
        self.assertIn("保持现有模型配置不变", mid_term_block["content"])

    def test_load_mid_term_memory_ignores_expired_items(self) -> None:
        from core.state import get_connection
        from modules.memory import RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        with get_connection() as connection:
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
                    "goal",
                    "已过期的中期记忆",
                    "active",
                    "2026-06-01 10:00:00",
                    "2026-06-05 10:00:00",
                ),
            )
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
                    "goal",
                    "仍然有效的中期记忆",
                    "active",
                    "2026-06-09 10:00:00",
                    "2026-06-20 10:00:00",
                ),
            )
            connection.commit()

        items = RetriFlowConversationMemoryService().load_mid_term_memory(
            session_id,
            now="2026-06-09T12:00:00",
        )

        self.assertEqual(items, ["仍然有效的中期记忆"])

    def test_update_long_term_memory_persists_structured_items(self) -> None:
        from core.state import get_connection
        from modules.memory import LongTermMemoryItem, RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        self._insert_message(session_id, "user", "我的偏好是回答尽量简洁，并保持当前模型配置不变。")
        self._insert_message(session_id, "assistant", "我会记住这个长期偏好和约束。")

        with patch(
            "modules.memory.service.RetriFlowConversationLongMemoryExtractor.extract",
            return_value=[
                LongTermMemoryItem(memory_type="preference", content="回答尽量简洁"),
                LongTermMemoryItem(memory_type="constraint", content="保持当前模型配置不变"),
            ],
        ) as extract:
            RetriFlowConversationMemoryService().update_long_term_memory(session_id)

        with get_connection() as connection:
            rows = connection.execute(
                """
                select owner_type, owner_id, memory_type, content, status
                from conversation_long_memories
                where owner_type = ? and owner_id = ?
                order by id
                """,
                ("session", session_id),
            ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["owner_type"], "session")
        self.assertEqual(rows[0]["owner_id"], session_id)
        self.assertEqual(rows[0]["memory_type"], "preference")
        self.assertEqual(rows[0]["status"], "active")
        self.assertIn("简洁", rows[0]["content"])
        self.assertEqual(rows[1]["memory_type"], "constraint")
        extract.assert_called_once()

    def test_update_long_term_memory_sets_expires_at(self) -> None:
        from core.state import get_connection
        from modules.memory import LongTermMemoryItem, RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        self._insert_message(session_id, "user", "我的长期偏好是尽量表格化输出")
        self._insert_message(session_id, "assistant", "我会记录这个长期偏好")

        with patch(
            "modules.memory.service.RetriFlowConversationLongMemoryExtractor.extract",
            return_value=[LongTermMemoryItem(memory_type="preference", content="偏好表格化输出")],
        ):
            RetriFlowConversationMemoryService().update_long_term_memory(
                session_id,
                now="2026-06-09T10:00:00",
            )

        with get_connection() as connection:
            row = connection.execute(
                """
                select expires_at
                from conversation_long_memories
                where owner_type = ? and owner_id = ?
                order by id desc
                limit 1
                """,
                ("session", session_id),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["expires_at"], "2026-12-06 10:00:00")

    def test_load_prompt_messages_includes_long_term_memory_block(self) -> None:
        from core.state import get_connection
        from modules.memory import RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        with get_connection() as connection:
            connection.execute(
                """
                insert into conversation_long_memories (
                    owner_type,
                    owner_id,
                    memory_type,
                    content,
                    status,
                    updated_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    "session",
                    session_id,
                    "preference",
                    "回答尽量简洁",
                    "active",
                    "2026-06-09 10:02:00",
                ),
            )
            connection.commit()

        prompt_messages = RetriFlowConversationMemoryService().load_prompt_messages(session_id)

        long_term_block = next(
            message for message in prompt_messages if message["role"] == "system" and "回答尽量简洁" in message["content"]
        )
        self.assertIn("回答尽量简洁", long_term_block["content"])

    def test_load_prompt_messages_prioritizes_relevant_long_term_memories_for_query(self) -> None:
        from core.state import get_connection
        from modules.memory import RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        with get_connection() as connection:
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
                    "session",
                    session_id,
                    "preference",
                    "回答时优先使用表格化输出",
                    "active",
                    "2026-06-09 10:02:00",
                    "2026-12-31 10:02:00",
                ),
            )
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
                    "session",
                    session_id,
                    "preference",
                    "回答时尽量简洁",
                    "active",
                    "2026-06-09 10:01:00",
                    "2026-12-31 10:01:00",
                ),
            )
            connection.commit()

        prompt_messages = RetriFlowConversationMemoryService().load_prompt_messages(
            session_id,
            query="请用表格总结这个方案",
        )

        long_term_block = next(
            message for message in prompt_messages if message["role"] == "system" and "长期记忆" in message["content"]
        )
        lines = [line for line in long_term_block["content"].splitlines() if line.startswith("- ")]
        self.assertEqual(len(lines), 2)
        self.assertIn("表格化输出", lines[0])

    def test_update_long_term_memory_prefers_session_owner_id(self) -> None:
        from core.state import get_connection
        from modules.memory import LongTermMemoryItem, RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        with get_connection() as connection:
            connection.execute(
                """
                update sessions
                set owner_id = ?
                where id = ?
                """,
                ("user-42", session_id),
            )
            connection.commit()

        self._insert_message(session_id, "user", "我的偏好是回答尽量简洁")
        self._insert_message(session_id, "assistant", "我会记住你的偏好")

        with patch(
            "modules.memory.service.RetriFlowConversationLongMemoryExtractor.extract",
            return_value=[LongTermMemoryItem(memory_type="preference", content="回答尽量简洁")],
        ):
            RetriFlowConversationMemoryService().update_long_term_memory(session_id)

        with get_connection() as connection:
            row = connection.execute(
                """
                select owner_type, owner_id, content
                from conversation_long_memories
                order by id desc
                limit 1
                """
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["owner_type"], "user")
        self.assertEqual(row["owner_id"], "user-42")
        self.assertEqual(row["content"], "回答尽量简洁")

    def test_update_long_term_memory_deactivates_conflicting_same_type_memory(self) -> None:
        from core.state import get_connection
        from modules.memory import LongTermMemoryItem, RetriFlowConversationMemoryService

        session_id = "session-demo-1"
        with get_connection() as connection:
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
                    "session",
                    session_id,
                    "preference",
                    "回答尽量简洁",
                    "active",
                    "2026-06-09 09:00:00",
                    "2026-12-31 09:00:00",
                ),
            )
            connection.commit()

        self._insert_message(session_id, "user", "以后回答时优先表格化输出")
        self._insert_message(session_id, "assistant", "我会更新这个长期偏好")

        with patch(
            "modules.memory.service.RetriFlowConversationLongMemoryExtractor.extract",
            return_value=[LongTermMemoryItem(memory_type="preference", content="优先表格化输出")],
        ):
            RetriFlowConversationMemoryService().update_long_term_memory(session_id)

        with get_connection() as connection:
            rows = connection.execute(
                """
                select content, status
                from conversation_long_memories
                where owner_type = ? and owner_id = ? and memory_type = ?
                order by id
                """,
                ("session", session_id, "preference"),
            ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["content"], "回答尽量简洁")
        self.assertEqual(rows[0]["status"], "inactive")
        self.assertEqual(rows[1]["content"], "优先表格化输出")
        self.assertEqual(rows[1]["status"], "active")


if __name__ == "__main__":
    unittest.main()
