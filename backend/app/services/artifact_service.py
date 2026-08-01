"""Thread-isolated generated-file creation, preview, and download orchestration."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy import text

from app.core.exceptions import (
    FileAccessDeniedError,
    FileNotFoundError,
    FileTypeUnsupportedError,
    ThreadNotFoundError,
)
from app.db.database import Database
from app.db.models.file import File
from app.db.models.thread import utc_now
from app.db.repositories.file_repository import FileRepository
from app.db.repositories.thread_repository import ThreadRepository
from app.schemas.file import FilePage, FileResponse
from app.services.file_service import FileService
from app.storage.file_storage import FileStorage
from app.storage.filename import validate_artifact_filename

ARTIFACT_MIME_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".csv": "text/csv",
    ".json": "application/json",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
}


@dataclass(frozen=True, slots=True)
class ArtifactContent:
    """A safe, bounded Artifact payload ready for an HTTP response."""

    metadata: FileResponse
    content: bytes
    content_type: str
    content_disposition: str
    content_security_policy: str | None


class ArtifactService:
    """Coordinate Artifact metadata with controlled output-file storage."""

    def __init__(
        self,
        *,
        database: Database,
        storage: FileStorage,
        max_artifact_bytes: int,
        frame_ancestors: tuple[str, ...],
    ) -> None:
        self._database = database
        self._storage = storage
        self._max_artifact_bytes = max_artifact_bytes
        self._frame_ancestors = frame_ancestors

    def write(
        self,
        *,
        thread_id: str,
        filename: str,
        content: str,
        description: str | None,
    ) -> FileResponse:
        """Persist one UTF-8 Artifact under a collision-safe visible filename."""
        safe_name, extension = validate_artifact_filename(filename)
        artifact_id = str(uuid4())
        stored_path: str | None = None
        with self._database.session_factory() as session:
            try:
                session.execute(text("BEGIN IMMEDIATE"))
                thread = ThreadRepository(session).get(thread_id)
                if thread is None:
                    raise ThreadNotFoundError
                repository = FileRepository(session)
                resolved_name = self._available_name(
                    repository,
                    thread_id=thread_id,
                    filename=safe_name,
                )
                stored_path, size_bytes = self._storage.write_artifact(
                    thread_id=thread_id,
                    file_id=artifact_id,
                    filename=resolved_name,
                    content=content,
                    max_bytes=self._max_artifact_bytes,
                )
                timestamp = utc_now()
                artifact = File(
                    id=artifact_id,
                    thread_id=thread_id,
                    source_file_id=None,
                    category="artifact",
                    original_name=resolved_name,
                    stored_name=Path(stored_path).name,
                    stored_path=stored_path,
                    extension=extension,
                    mime_type=ARTIFACT_MIME_TYPES[extension],
                    size_bytes=size_bytes,
                    parse_status=None,
                    parse_error=None,
                    description=(description.strip() or None) if description else None,
                    created_at=timestamp,
                )
                repository.add(artifact)
                ThreadRepository(session).touch(thread, timestamp)
                session.commit()
            except Exception:
                session.rollback()
                if stored_path is not None:
                    self._storage.remove(thread_id=thread_id, stored_path=stored_path)
                raise
        return FileService.to_response(artifact, None)

    def list_page(self, *, thread_id: str, page: int, page_size: int) -> FilePage:
        """Return generated files for one existing thread, newest first."""
        with self._database.session_factory() as session:
            if ThreadRepository(session).get(thread_id) is None:
                raise ThreadNotFoundError
            repository = FileRepository(session)
            artifacts = repository.list_page(
                thread_id=thread_id,
                category="artifact",
                offset=(page - 1) * page_size,
                limit=page_size,
            )
            return FilePage(
                items=[FileService.to_response(artifact, None) for artifact in artifacts],
                page=page,
                page_size=page_size,
                total=repository.count(thread_id=thread_id, category="artifact"),
            )

    def preview(self, *, thread_id: str, file_id: str) -> ArtifactContent:
        """Read a previewable Artifact with strict HTML isolation metadata."""
        artifact, content = self._read_owned(thread_id=thread_id, file_id=file_id)
        extension = artifact.extension or ""
        content_type = ARTIFACT_MIME_TYPES.get(extension)
        if content_type is None:
            raise FileTypeUnsupportedError
        policy = self._html_policy() if extension == ".html" else None
        return ArtifactContent(
            metadata=FileService.to_response(artifact, None),
            content=content,
            content_type=f"{content_type}; charset=utf-8",
            content_disposition=self._content_disposition("inline", artifact.original_name),
            content_security_policy=policy,
        )

    def download(self, *, thread_id: str, file_id: str) -> ArtifactContent:
        """Read one Artifact for attachment delivery without exposing its local path."""
        artifact, content = self._read_owned(thread_id=thread_id, file_id=file_id)
        content_type = ARTIFACT_MIME_TYPES.get(artifact.extension or "", "application/octet-stream")
        return ArtifactContent(
            metadata=FileService.to_response(artifact, None),
            content=content,
            content_type=content_type,
            content_disposition=self._content_disposition("attachment", artifact.original_name),
            content_security_policy=None,
        )

    def _read_owned(self, *, thread_id: str, file_id: str) -> tuple[File, bytes]:
        with self._database.session_factory() as session:
            if ThreadRepository(session).get(thread_id) is None:
                raise ThreadNotFoundError
            artifact = FileRepository(session).get(file_id)
            if artifact is None:
                raise FileNotFoundError
            if artifact.thread_id != thread_id:
                raise FileAccessDeniedError
            if artifact.category != "artifact":
                raise FileNotFoundError
            path = self._storage.resolve_owned(
                thread_id=thread_id,
                stored_path=artifact.stored_path,
            )
            if not path.is_file():
                raise FileNotFoundError
            return artifact, path.read_bytes()

    @staticmethod
    def _available_name(
        repository: FileRepository,
        *,
        thread_id: str,
        filename: str,
    ) -> str:
        if not repository.artifact_name_exists(thread_id=thread_id, original_name=filename):
            return filename
        suffix = Path(filename).suffix
        stem = filename[: -len(suffix)]
        sequence = 2
        while True:
            marker = f" ({sequence})"
            bounded_stem = stem[: 255 - len(suffix) - len(marker)]
            candidate = f"{bounded_stem}{marker}{suffix}"
            if not repository.artifact_name_exists(
                thread_id=thread_id,
                original_name=candidate,
            ):
                return candidate
            sequence += 1

    @staticmethod
    def _content_disposition(disposition: str, filename: str) -> str:
        ascii_name = "".join(character if character.isascii() else "_" for character in filename)
        escaped_ascii = ascii_name.replace("\\", "_").replace('"', "_")
        encoded = quote(filename, safe="")
        return f"{disposition}; filename=\"{escaped_ascii}\"; filename*=UTF-8''{encoded}"

    def _html_policy(self) -> str:
        ancestors = " ".join(("'self'", *self._frame_ancestors))
        return (
            "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; "
            f"base-uri 'none'; form-action 'none'; frame-ancestors {ancestors}"
        )
