from __future__ import annotations

from fastapi import HTTPException, status

from core.state import get_connection
from schemas.chat import MessageFeedbackRequest, MessageFeedbackResponse


class RetriFlowMessageFeedbackService:
    def submit_feedback(
        self,
        *,
        message_id: int,
        user_id: str,
        request: MessageFeedbackRequest,
    ) -> MessageFeedbackResponse:
        if request.vote not in {1, -1}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="vote must be 1 or -1")

        with get_connection() as connection:
            message = connection.execute(
                """
                select cm.id, cm.session_id, cm.role, s.owner_id
                from conversation_messages cm
                join sessions s on s.id = cm.session_id
                where cm.id = ?
                """,
                (message_id,),
            ).fetchone()
            if message is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
            if str(message["owner_id"] or "") not in {"", user_id}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Message belongs to another user")
            if str(message["role"]).lower() != "assistant":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only assistant messages can be rated")

            existing = connection.execute(
                """
                select id
                from message_feedback
                where message_id = ? and user_id = ?
                """,
                (message_id, user_id),
            ).fetchone()
            if existing is None:
                row = connection.execute(
                    """
                    insert into message_feedback (message_id, session_id, user_id, vote, reason, comment)
                    values (?, ?, ?, ?, ?, ?)
                    returning message_id, session_id, vote, reason, comment, updated_at
                    """,
                    (
                        message_id,
                        str(message["session_id"]),
                        user_id,
                        request.vote,
                        request.reason.strip(),
                        request.comment.strip(),
                    ),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    update message_feedback
                    set vote = ?,
                        reason = ?,
                        comment = ?,
                        updated_at = current_timestamp
                    where id = ?
                    returning message_id, session_id, vote, reason, comment, updated_at
                    """,
                    (
                        request.vote,
                        request.reason.strip(),
                        request.comment.strip(),
                        existing["id"],
                    ),
                ).fetchone()
            connection.commit()

        return MessageFeedbackResponse(
            message_id=int(row["message_id"]),
            session_id=str(row["session_id"]),
            vote=int(row["vote"]),
            reason=str(row["reason"] or ""),
            comment=str(row["comment"] or ""),
            updated_at=str(row["updated_at"] or ""),
        )
