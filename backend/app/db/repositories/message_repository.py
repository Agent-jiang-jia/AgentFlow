"""Ordered message persistence queries."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.message import Message


class MessageRepository:
    """Read and write messages within a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, message: Message) -> None:
        """Stage a message record."""
        self._session.add(message)

    def next_sequence_number(self, thread_id: str) -> int:
        """Return the next strictly increasing sequence for a thread."""
        current = self._session.scalar(
            select(func.max(Message.sequence_number)).where(Message.thread_id == thread_id)
        )
        return int(current or 0) + 1

    def list_page(self, *, thread_id: str, offset: int, limit: int) -> list[Message]:
        """Return one page in authoritative conversation order."""
        statement = (
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.sequence_number.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def count(self, thread_id: str) -> int:
        """Return a thread's message count."""
        statement = select(func.count()).select_from(Message).where(Message.thread_id == thread_id)
        return int(self._session.scalar(statement) or 0)

    def list_conversation(self, thread_id: str) -> list[Message]:
        """Return all plain conversation messages for model context."""
        statement = (
            select(Message)
            .where(
                Message.thread_id == thread_id,
                Message.role.in_(("system", "user", "assistant")),
                Message.message_type == "text",
            )
            .order_by(Message.sequence_number.asc())
        )
        return list(self._session.scalars(statement))

    def first_user_message(self, thread_id: str) -> Message | None:
        """Return the first user message used for simple title generation."""
        statement = (
            select(Message)
            .where(
                Message.thread_id == thread_id,
                Message.role == "user",
                Message.message_type == "text",
            )
            .order_by(Message.sequence_number.asc())
            .limit(1)
        )
        return self._session.scalar(statement)
