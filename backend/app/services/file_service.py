"""File upload, metadata, deletion, and safe read orchestration."""

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast
from uuid import uuid4

from sqlalchemy import text

from app.core.exceptions import (
    FileAccessDeniedError,
    FileNotFoundError,
    FileParseError,
    FileTypeUnsupportedError,
    OcrNotSupportedError,
    ThreadNotFoundError,
)
from app.db.database import Database
from app.db.models.file import File
from app.db.models.thread import utc_now
from app.db.repositories.file_repository import FileRepository
from app.db.repositories.thread_repository import ThreadRepository
from app.schemas.file import FileCategory, FilePage, FileResponse
from app.services.parser_service import ParserService
from app.storage.file_storage import FileStorage
from app.storage.filename import validate_upload_filename


@dataclass(frozen=True, slots=True)
class FileReadResult:
    """Bounded model-facing text read from a thread-owned normalized file."""

    file_id: str
    filename: str
    content: str
    start_line: int
    end_line: int
    total_lines: int
    truncated: bool


class FileService:
    """Coordinate file metadata, parsing, and controlled local storage."""

    def __init__(
        self,
        *,
        database: Database,
        storage: FileStorage,
        parser_service: ParserService,
        max_upload_bytes: int,
    ) -> None:
        self._database = database
        self._storage = storage
        self._parser_service = parser_service
        self._max_upload_bytes = max_upload_bytes

    def upload(
        self,
        *,
        thread_id: str,
        filename: str | None,
        mime_type: str | None,
        stream: BinaryIO,
    ) -> FileResponse:
        """Validate, persist, synchronously parse, and record one upload."""
        self._require_thread(thread_id)
        safe_name, extension = validate_upload_filename(filename)
        normalized_mime = self._parser_service.validate_mime_type(
            extension=extension,
            mime_type=mime_type,
        )
        upload_id = str(uuid4())
        upload_path: str | None = None
        parsed_path: str | None = None
        persisted = False
        try:
            upload_path, size_bytes = self._storage.write_upload(
                thread_id=thread_id,
                file_id=upload_id,
                safe_filename=safe_name,
                stream=stream,
                max_bytes=self._max_upload_bytes,
            )
            absolute_upload = self._storage.resolve_owned(
                thread_id=thread_id,
                stored_path=upload_path,
            )
            try:
                parse_result = self._parser_service.parse(
                    absolute_upload,
                    original_name=safe_name,
                    extension=extension,
                )
            except FileTypeUnsupportedError:
                self._storage.remove(thread_id=thread_id, stored_path=upload_path)
                raise
            except Exception as exc:
                self._persist_failed_upload(
                    thread_id=thread_id,
                    upload_id=upload_id,
                    safe_name=safe_name,
                    extension=extension,
                    mime_type=normalized_mime,
                    size_bytes=size_bytes,
                    stored_path=upload_path,
                )
                persisted = True
                raise FileParseError from exc

            parsed_record: File | None = None
            if parse_result.status == "success":
                if parse_result.content is None:
                    raise RuntimeError("Successful parser result has no content")
                parsed_id = str(uuid4())
                parsed_path, parsed_name, parsed_size = self._storage.write_parsed(
                    thread_id=thread_id,
                    file_id=parsed_id,
                    source_stem=Path(safe_name).stem,
                    content=parse_result.content,
                )
                parsed_record = File(
                    id=parsed_id,
                    thread_id=thread_id,
                    source_file_id=upload_id,
                    category="parsed",
                    original_name=parsed_name,
                    stored_name=Path(parsed_path).name,
                    stored_path=parsed_path,
                    extension=".md",
                    mime_type="text/markdown",
                    size_bytes=parsed_size,
                    parse_status="success",
                    parse_error=None,
                    description=None,
                    created_at=utc_now(),
                )

            upload_record = File(
                id=upload_id,
                thread_id=thread_id,
                source_file_id=None,
                category="upload",
                original_name=safe_name,
                stored_name=Path(upload_path).name,
                stored_path=upload_path,
                extension=extension,
                mime_type=normalized_mime,
                size_bytes=size_bytes,
                parse_status=parse_result.status,
                parse_error=parse_result.error,
                description=None,
                created_at=utc_now(),
            )
            self._persist_upload(upload_record, parsed_record)
            persisted = True
            return self._response(upload_record, parsed_record.id if parsed_record else None)
        except Exception:
            if not persisted:
                if parsed_path is not None:
                    self._storage.remove(thread_id=thread_id, stored_path=parsed_path)
                if upload_path is not None:
                    self._storage.remove(thread_id=thread_id, stored_path=upload_path)
            raise

    def list_page(
        self,
        *,
        thread_id: str,
        category: str,
        page: int,
        page_size: int,
    ) -> FilePage:
        """Return a safe metadata page for an existing thread."""
        with self._database.session_factory() as session:
            if ThreadRepository(session).get(thread_id) is None:
                raise ThreadNotFoundError
            repository = FileRepository(session)
            files = repository.list_page(
                thread_id=thread_id,
                category=category,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
            return FilePage(
                items=[self._response(file, self._parsed_id(repository, file)) for file in files],
                page=page,
                page_size=page_size,
                total=repository.count(thread_id=thread_id, category=category),
            )

    def get(self, *, thread_id: str, file_id: str) -> FileResponse:
        """Return one file while distinguishing missing from cross-thread access."""
        with self._database.session_factory() as session:
            if ThreadRepository(session).get(thread_id) is None:
                raise ThreadNotFoundError
            repository = FileRepository(session)
            file = self._require_owned(repository, thread_id=thread_id, file_id=file_id)
            return self._response(file, self._parsed_id(repository, file))

    def delete(self, *, thread_id: str, file_id: str) -> None:
        """Delete metadata and owned paths with filesystem rollback compensation."""
        staged: tuple[tuple[Path, Path], ...] = ()
        with self._database.session_factory() as session:
            try:
                session.execute(text("BEGIN IMMEDIATE"))
                if ThreadRepository(session).get(thread_id) is None:
                    raise ThreadNotFoundError
                repository = FileRepository(session)
                file = self._require_owned(repository, thread_id=thread_id, file_id=file_id)
                records = [file]
                if file.category == "upload":
                    parsed = repository.parsed_for_source(
                        thread_id=thread_id,
                        source_file_id=file.id,
                    )
                    if parsed is not None:
                        records.append(parsed)
                staged = self._storage.stage_delete(
                    thread_id=thread_id,
                    stored_paths=tuple(record.stored_path for record in records),
                )
                repository.delete(file)
                thread = ThreadRepository(session).get(thread_id)
                if thread is None:
                    raise ThreadNotFoundError
                ThreadRepository(session).touch(thread, utc_now())
                session.commit()
            except Exception:
                session.rollback()
                self._storage.restore_staged(staged)
                raise
        self._storage.purge_staged(staged)

    def validate_file_ids(self, *, thread_id: str, file_ids: tuple[str, ...]) -> None:
        """Validate chat attachments without revealing another thread's ownership."""
        with self._database.session_factory() as session:
            if ThreadRepository(session).get(thread_id) is None:
                raise ThreadNotFoundError
            repository = FileRepository(session)
            for file_id in file_ids:
                self._require_owned(repository, thread_id=thread_id, file_id=file_id)

    def list_for_tool(self, *, thread_id: str) -> list[dict[str, object]]:
        """Return model-facing metadata for all files in one thread."""
        with self._database.session_factory() as session:
            if ThreadRepository(session).get(thread_id) is None:
                raise ThreadNotFoundError
            repository = FileRepository(session)
            return [
                {
                    "file_id": file.id,
                    "filename": file.original_name,
                    "category": file.category,
                    "extension": file.extension,
                    "mime_type": file.mime_type,
                    "size_bytes": file.size_bytes,
                    "parse_status": file.parse_status,
                    "parsed_file_id": self._parsed_id(repository, file),
                }
                for file in repository.list_all(thread_id=thread_id)
            ]

    def read_for_tool(
        self,
        *,
        thread_id: str,
        file_id: str,
        start_line: int,
        max_lines: int,
        max_chars: int,
    ) -> FileReadResult:
        """Read bounded UTF-8 content, preferring an upload's parsed derivative."""
        with self._database.session_factory() as session:
            repository = FileRepository(session)
            requested = self._require_owned(repository, thread_id=thread_id, file_id=file_id)
            target = requested
            if requested.category == "upload":
                parsed = repository.parsed_for_source(
                    thread_id=thread_id,
                    source_file_id=requested.id,
                )
                if parsed is None:
                    if requested.parse_status == "unsupported_ocr":
                        raise OcrNotSupportedError
                    raise FileParseError
                target = parsed
            path = self._storage.resolve_owned(
                thread_id=thread_id,
                stored_path=target.stored_path,
            )
            if not path.is_file():
                raise FileNotFoundError
            content = path.read_text(encoding="utf-8")

        lines = content.splitlines()
        offset = min(start_line - 1, len(lines))
        selected = lines[offset : offset + max_lines]
        joined = "\n".join(selected)
        line_truncated = offset + len(selected) < len(lines)
        char_truncated = len(joined) > max_chars
        bounded = joined[:max_chars] if char_truncated else joined
        end_line = offset + len(selected)
        return FileReadResult(
            file_id=requested.id,
            filename=requested.original_name,
            content=bounded,
            start_line=start_line,
            end_line=end_line,
            total_lines=len(lines),
            truncated=line_truncated or char_truncated,
        )

    def _require_thread(self, thread_id: str) -> None:
        with self._database.session_factory() as session:
            if ThreadRepository(session).get(thread_id) is None:
                raise ThreadNotFoundError

    def _persist_upload(self, upload: File, parsed: File | None) -> None:
        with self._database.session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            thread = ThreadRepository(session).get(upload.thread_id)
            if thread is None:
                raise ThreadNotFoundError
            repository = FileRepository(session)
            repository.add(upload)
            if parsed is not None:
                repository.add(parsed)
            ThreadRepository(session).touch(thread, utc_now())
            session.commit()

    def _persist_failed_upload(
        self,
        *,
        thread_id: str,
        upload_id: str,
        safe_name: str,
        extension: str,
        mime_type: str,
        size_bytes: int,
        stored_path: str,
    ) -> None:
        upload = File(
            id=upload_id,
            thread_id=thread_id,
            source_file_id=None,
            category="upload",
            original_name=safe_name,
            stored_name=Path(stored_path).name,
            stored_path=stored_path,
            extension=extension,
            mime_type=mime_type,
            size_bytes=size_bytes,
            parse_status="failed",
            parse_error="文件解析失败",
            description=None,
            created_at=utc_now(),
        )
        self._persist_upload(upload, None)

    @staticmethod
    def _require_owned(repository: FileRepository, *, thread_id: str, file_id: str) -> File:
        file = repository.get(file_id)
        if file is None:
            raise FileNotFoundError
        if file.thread_id != thread_id:
            raise FileAccessDeniedError
        return file

    @staticmethod
    def _parsed_id(repository: FileRepository, file: File) -> str | None:
        if file.category != "upload":
            return None
        parsed = repository.parsed_for_source(thread_id=file.thread_id, source_file_id=file.id)
        return parsed.id if parsed is not None else None

    @staticmethod
    def _response(file: File, parsed_file_id: str | None) -> FileResponse:
        return FileResponse(
            id=file.id,
            thread_id=file.thread_id,
            source_file_id=file.source_file_id,
            category=cast(FileCategory, file.category),
            original_name=file.original_name,
            extension=file.extension,
            mime_type=file.mime_type,
            size_bytes=file.size_bytes,
            parse_status=file.parse_status,
            parse_error=file.parse_error,
            parsed_file_id=parsed_file_id,
            created_at=file.created_at,
        )
