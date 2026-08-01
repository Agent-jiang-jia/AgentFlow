"""Persist and project web sources used by one agent run."""

from dataclasses import dataclass
from uuid import uuid4

from app.db.database import Database
from app.db.models.source import Source
from app.db.models.thread import utc_now
from app.db.repositories.run_repository import RunRepository
from app.db.repositories.source_repository import SourceRepository


@dataclass(frozen=True, slots=True)
class SourceInput:
    """Trusted normalized source supplied by a web tool."""

    title: str
    url: str
    snippet: str
    source_type: str


class SourceService:
    """Maintain run/thread source consistency and safe public projections."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def record(self, *, run_id: str, thread_id: str, sources: tuple[SourceInput, ...]) -> None:
        """Upsert sources, promoting fetched pages over search-only entries."""
        if not sources:
            return
        with self._database.session_factory() as session:
            run = RunRepository(session).get_for_thread(run_id=run_id, thread_id=thread_id)
            if run is None:
                raise RuntimeError("Source run context was lost")
            repository = SourceRepository(session)
            for item in sources:
                existing = repository.get_for_run_url(run_id=run_id, url=item.url)
                if existing is None:
                    repository.add(
                        Source(
                            id=str(uuid4()),
                            run_id=run_id,
                            thread_id=thread_id,
                            title=item.title[:500] or None,
                            url=item.url,
                            snippet=item.snippet[:1000] or None,
                            source_type=item.source_type,
                            created_at=utc_now(),
                        )
                    )
                    continue
                if item.source_type == "web_page":
                    existing.title = item.title[:500] or existing.title
                    existing.snippet = item.snippet[:1000] or existing.snippet
                    existing.source_type = "web_page"
            session.commit()

    def list_public(self, *, run_id: str, thread_id: str) -> list[dict[str, str]]:
        """Return bounded fields suitable for message metadata and SSE."""
        with self._database.session_factory() as session:
            sources = SourceRepository(session).list_for_run(run_id=run_id, thread_id=thread_id)
            return [
                {
                    "title": source.title or source.url,
                    "url": source.url,
                    "snippet": source.snippet or "",
                    "source_type": source.source_type,
                }
                for source in sources
            ]
