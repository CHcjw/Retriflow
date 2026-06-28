from core.state import get_connection
from schemas.session import (
    ConversationMessageItem,
    ConversationMessageListResponse,
    SessionCreateRequest,
    SessionItem,
    SessionListResponse,
)


class RetriFlowSessionService:
    def list_sessions(self, user_id: str) -> SessionListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, title, message_count, owner_id
                from sessions
                where owner_id = ? or owner_id = ''
                """,
                (user_id,),
            ).fetchall()
        rows = sorted(rows, key=lambda row: self._session_sort_key(str(row["id"])), reverse=True)
        return SessionListResponse(
            items=[
                SessionItem(
                    id=row["id"],
                    title=row["title"],
                    message_count=row["message_count"],
                    owner_id=str(row.get("owner_id", "") or ""),
                )
                for row in rows
            ]
        )

    def create_session(self, request: SessionCreateRequest, user_id: str) -> SessionItem:
        with get_connection() as connection:
            existing_ids = connection.execute("select id from sessions").fetchall()
            next_index = self._next_numeric_suffix([str(row["id"]) for row in existing_ids], prefix="session-")
            session_id = f"session-{next_index}"
            connection.execute(
                """
                insert into sessions (id, title, message_count, owner_id)
                values (?, ?, ?, ?)
                """,
                (session_id, request.title, 0, user_id),
            )
            connection.commit()

        return SessionItem(
            id=session_id,
            title=request.title,
            message_count=0,
            owner_id=user_id,
        )

    def list_messages(self, session_id: str, user_id: str) -> ConversationMessageListResponse:
        self.ensure_session_access(session_id, user_id, claim_unowned=False)
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, session_id, role, content, created_at, duration_ms
                from conversation_messages
                where session_id = ?
                order by id
                """,
                (session_id,),
            ).fetchall()

        return ConversationMessageListResponse(
            items=[
                ConversationMessageItem(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    created_at=self._serialize_timestamp(row["created_at"]),
                    duration_ms=int(row.get("duration_ms", 0) or 0),
                )
                for row in rows
            ]
        )

    def delete_session(self, session_id: str, user_id: str) -> None:
        self.ensure_session_access(session_id, user_id, claim_unowned=False, allow_unowned=True)
        with get_connection() as connection:
            connection.execute("delete from conversation_messages where session_id = ?", (session_id,))
            connection.execute("delete from conversation_memory_summaries where session_id = ?", (session_id,))
            connection.execute("delete from conversation_mid_memories where session_id = ?", (session_id,))
            connection.execute(
                """
                delete from conversation_long_memories
                where owner_type = ? and owner_id = ?
                """,
                ("session", session_id),
            )
            connection.execute("delete from sessions where id = ?", (session_id,))
            connection.commit()

    def update_session_title(self, session_id: str, title: str, user_id: str) -> SessionItem:
        self.ensure_session_access(session_id, user_id, claim_unowned=False)
        with get_connection() as connection:
            connection.execute(
                """
                update sessions
                set title = ?
                where id = ?
                """,
                (title, session_id),
            )
            connection.commit()
            row = connection.execute(
                """
                select id, title, message_count, owner_id
                from sessions
                where id = ?
                """,
                (session_id,),
            ).fetchone()
        return SessionItem(
            id=row["id"],
            title=row["title"],
            message_count=row["message_count"],
            owner_id=str(row.get("owner_id", "") or ""),
        )

    def ensure_session_access(
        self,
        session_id: str,
        user_id: str,
        *,
        claim_unowned: bool,
        allow_unowned: bool = False,
    ) -> None:
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
            if row is None:
                raise ValueError("session not found")

            owner_id = str(row.get("owner_id", "") or "").strip()
            if owner_id and owner_id != user_id:
                raise PermissionError("forbidden session")
            if not owner_id and allow_unowned:
                return
            if not owner_id and claim_unowned:
                connection.execute(
                    """
                    update sessions
                    set owner_id = ?
                    where id = ?
                    """,
                    (user_id, session_id),
                )
                connection.commit()

    @staticmethod
    def _serialize_timestamp(value) -> str:
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _next_numeric_suffix(existing_ids: list[str], *, prefix: str) -> int:
        max_suffix = 0
        for item in existing_ids:
            if not item.startswith(prefix):
                continue
            suffix = item[len(prefix):]
            if suffix.isdigit():
                max_suffix = max(max_suffix, int(suffix))
        return max_suffix + 1

    @staticmethod
    def _session_sort_key(session_id: str) -> tuple[int, int, str]:
        prefix = "session-"
        if session_id.startswith(prefix):
            suffix = session_id[len(prefix):]
            if suffix.isdigit():
                return (1, int(suffix), session_id)
        return (0, 0, session_id)
