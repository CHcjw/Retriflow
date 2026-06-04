from core.state import get_connection
from schemas.session import (
    ConversationMessageItem,
    ConversationMessageListResponse,
    SessionCreateRequest,
    SessionItem,
    SessionListResponse,
)


class RetriFlowSessionService:
    def list_sessions(self) -> SessionListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                "select id, title, message_count from sessions order by id"
            ).fetchall()
        return SessionListResponse(
            items=[
                SessionItem(
                    id=row["id"],
                    title=row["title"],
                    message_count=row["message_count"],
                )
                for row in rows
            ]
        )

    def create_session(self, request: SessionCreateRequest) -> SessionItem:
        with get_connection() as connection:
            next_index = connection.execute("select count(*) from sessions").fetchone()[0] + 1
            session_id = f"session-{next_index}"
            connection.execute(
                """
                insert into sessions (id, title, message_count)
                values (?, ?, ?)
                """,
                (session_id, request.title, 0),
            )
            connection.commit()

        return SessionItem(id=session_id, title=request.title, message_count=0)

    def list_messages(self, session_id: str) -> ConversationMessageListResponse:
        with get_connection() as connection:
            rows = connection.execute(
                """
                select id, session_id, role, content, created_at
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
                )
                for row in rows
            ]
        )

    @staticmethod
    def _serialize_timestamp(value) -> str:
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
