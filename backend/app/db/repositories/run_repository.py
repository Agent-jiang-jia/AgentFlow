"""Agent run persistence queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.run import Run


class RunRepository:
    """Read and write run records within a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: Run) -> None:
        """Stage a new run record."""
        self._session.add(run)

    def get_for_thread(self, *, run_id: str, thread_id: str) -> Run | None:
        """Return a run only when it belongs to the expected thread."""
        statement = select(Run).where(Run.id == run_id, Run.thread_id == thread_id)
        return self._session.scalar(statement)

    def list_active(self) -> list[Run]:
        """Return runs left non-terminal by an interrupted process."""
        statement = select(Run).where(Run.status.in_(("pending", "running")))
        return list(self._session.scalars(statement))
