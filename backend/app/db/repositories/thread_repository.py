"""Thread persistence queries."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.run import Run
from app.db.models.thread import Thread


class ThreadRepository:
    """Read and write thread records within a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, thread: Thread) -> None:
        """Stage a new thread record."""
        self._session.add(thread)

    def get(self, thread_id: str) -> Thread | None:
        """Return one thread by its opaque identifier."""
        return self._session.get(Thread, thread_id)

    def list_page(self, *, offset: int, limit: int) -> list[Thread]:
        """Return threads ordered by most recent activity."""
        statement = (
            select(Thread)
            .order_by(Thread.updated_at.desc(), Thread.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def count(self) -> int:
        """Return the total number of threads."""
        return int(self._session.scalar(select(func.count()).select_from(Thread)) or 0)

    def list_ids(self) -> set[str]:
        """Return all logical thread identifiers for storage reconciliation."""
        return set(self._session.scalars(select(Thread.id)))

    def has_active_run(self, thread_id: str) -> bool:
        """Return whether a pending or running execution exists."""
        statement = select(
            select(Run.id)
            .where(Run.thread_id == thread_id, Run.status.in_(("pending", "running")))
            .exists()
        )
        return bool(self._session.scalar(statement))

    def touch(self, thread: Thread, timestamp: datetime) -> None:
        """Move a thread to the supplied activity timestamp."""
        thread.updated_at = timestamp

    def delete(self, thread: Thread) -> None:
        """Stage a thread and all database cascades for deletion."""
        self._session.delete(thread)
