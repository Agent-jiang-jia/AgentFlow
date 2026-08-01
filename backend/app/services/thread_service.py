"""Thread CRUD and message query orchestration."""

import logging
from uuid import uuid4

from sqlalchemy import text

from app.core.exceptions import ThreadBusyError, ThreadNotFoundError
from app.db.database import Database
from app.db.models.thread import Thread, utc_now
from app.db.repositories.message_repository import MessageRepository
from app.db.repositories.thread_repository import ThreadRepository
from app.schemas.message import MessagePage, MessageResponse
from app.schemas.thread import ThreadCreate, ThreadPage, ThreadResponse
from app.storage.thread_storage import ThreadStorage

logger = logging.getLogger(__name__)


class ThreadService:
    """Coordinate thread persistence with its controlled local directory."""

    def __init__(self, *, database: Database, storage: ThreadStorage) -> None:
        self._database = database
        self._storage = storage

    def create(self, request: ThreadCreate | None) -> ThreadResponse:
        """Create one persisted thread and its isolated directory tree."""
        thread_id = str(uuid4())
        timestamp = utc_now()
        thread = Thread(
            id=thread_id,
            title=request.title if request is not None else "新会话",
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._storage.create(thread_id)
        try:
            with self._database.session_factory() as session:
                ThreadRepository(session).add(thread)
                session.commit()
        except Exception:
            self._storage.remove_created(thread_id)
            raise
        return ThreadResponse.model_validate(thread)

    def list(self, *, page: int, page_size: int) -> ThreadPage:
        """Return a page of threads ordered by recent activity."""
        with self._database.session_factory() as session:
            repository = ThreadRepository(session)
            items = repository.list_page(offset=(page - 1) * page_size, limit=page_size)
            total = repository.count()
            return ThreadPage(
                items=[ThreadResponse.model_validate(item) for item in items],
                page=page,
                page_size=page_size,
                total=total,
            )

    def get(self, thread_id: str) -> ThreadResponse:
        """Return one thread or a stable not-found error."""
        with self._database.session_factory() as session:
            thread = ThreadRepository(session).get(thread_id)
            if thread is None:
                raise ThreadNotFoundError
            return ThreadResponse.model_validate(thread)

    def list_messages(self, *, thread_id: str, page: int, page_size: int) -> MessagePage:
        """Return only messages owned by the requested thread."""
        with self._database.session_factory() as session:
            if ThreadRepository(session).get(thread_id) is None:
                raise ThreadNotFoundError
            repository = MessageRepository(session)
            items = repository.list_page(
                thread_id=thread_id,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
            return MessagePage(
                items=[MessageResponse.model_validate(item) for item in items],
                page=page,
                page_size=page_size,
                total=repository.count(thread_id),
            )

    def delete(self, thread_id: str) -> None:
        """Delete a non-running thread and its local tree with rollback compensation."""
        staged_directory = None
        with self._database.session_factory() as session:
            try:
                session.execute(text("BEGIN IMMEDIATE"))
                repository = ThreadRepository(session)
                thread = repository.get(thread_id)
                if thread is None:
                    raise ThreadNotFoundError
                if repository.has_active_run(thread_id):
                    raise ThreadBusyError
                staged_directory = self._storage.stage_delete(thread_id)
                repository.delete(thread)
                session.commit()
            except Exception:
                session.rollback()
                self._storage.restore_staged(thread_id, staged_directory)
                raise

        try:
            self._storage.purge_staged(staged_directory)
        except OSError:
            logger.exception("Thread directory cleanup failed", extra={"thread_id": thread_id})
            raise
