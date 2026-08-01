"""Thread-isolated file metadata persistence."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.file import File


class FileRepository:
    """Read and write file records within a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, file: File) -> None:
        """Stage one file metadata record."""
        self._session.add(file)

    def get(self, file_id: str) -> File | None:
        """Return one file without assuming ownership."""
        return self._session.get(File, file_id)

    def get_for_thread(self, *, thread_id: str, file_id: str) -> File | None:
        """Return one file only if it belongs to the requested thread."""
        return self._session.scalar(
            select(File).where(File.id == file_id, File.thread_id == thread_id)
        )

    def parsed_for_source(self, *, thread_id: str, source_file_id: str) -> File | None:
        """Return the normalized derivative owned by the same thread."""
        return self._session.scalar(
            select(File).where(
                File.thread_id == thread_id,
                File.source_file_id == source_file_id,
                File.category == "parsed",
            )
        )

    def artifact_name_exists(self, *, thread_id: str, original_name: str) -> bool:
        """Return whether a generated file already uses this visible name."""
        statement = select(File.id).where(
            File.thread_id == thread_id,
            File.category == "artifact",
            File.original_name == original_name,
        )
        return self._session.scalar(statement) is not None

    def list_page(
        self,
        *,
        thread_id: str,
        category: str,
        offset: int,
        limit: int,
    ) -> list[File]:
        """Return a stable newest-first page for one thread."""
        statement = select(File).where(File.thread_id == thread_id)
        if category != "all":
            statement = statement.where(File.category == category)
        statement = (
            statement.order_by(File.created_at.desc(), File.id.desc()).offset(offset).limit(limit)
        )
        return list(self._session.scalars(statement))

    def list_all(self, *, thread_id: str) -> list[File]:
        """Return all file records for model-facing list_files."""
        statement = (
            select(File)
            .where(File.thread_id == thread_id)
            .order_by(File.created_at.asc(), File.id.asc())
        )
        return list(self._session.scalars(statement))

    def count(self, *, thread_id: str, category: str) -> int:
        """Count one thread's files with an optional category filter."""
        statement = select(func.count()).select_from(File).where(File.thread_id == thread_id)
        if category != "all":
            statement = statement.where(File.category == category)
        return int(self._session.scalar(statement) or 0)

    def delete(self, file: File) -> None:
        """Stage one file record for deletion."""
        self._session.delete(file)
