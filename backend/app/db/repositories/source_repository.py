"""Web-source persistence and run-scoped queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.source import Source


class SourceRepository:
    """Read and write sources within a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_run_url(self, *, run_id: str, url: str) -> Source | None:
        """Return a source with the run-level unique identity."""
        return self._session.scalar(
            select(Source).where(Source.run_id == run_id, Source.url == url)
        )

    def add(self, source: Source) -> None:
        """Stage one source record."""
        self._session.add(source)

    def list_for_run(self, *, run_id: str, thread_id: str) -> list[Source]:
        """Return sources only for the expected run and thread."""
        statement = (
            select(Source)
            .where(Source.run_id == run_id, Source.thread_id == thread_id)
            .order_by(Source.created_at.asc(), Source.id.asc())
        )
        return list(self._session.scalars(statement))
