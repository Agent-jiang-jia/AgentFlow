"""Controlled upload and parsed-file operations."""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import UUID, uuid4

from app.core.exceptions import ArtifactTooLargeError, FileParseError, FileTooLargeError

_CHUNK_SIZE = 64 * 1024
_MANAGED_FILE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_")
_STAGED_FILE = re.compile(r"^\.(?P<original>.+)\.deleting-[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class FileRecoveryResult:
    """Counts produced while reconciling managed files and metadata."""

    restored: int = 0
    purged: int = 0
    missing: int = 0


class FileStorage:
    """Read and write files only inside one canonical thread tree."""

    def __init__(self, data_dir: Path) -> None:
        self._data_root = data_dir.resolve()
        self._threads_root = (self._data_root / "threads").resolve()

    @staticmethod
    def _canonical_uuid(value: str, label: str) -> str:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError(f"{label} identifier is not canonical")
        return value

    def _thread_directory(self, thread_id: str, category: str) -> Path:
        self._canonical_uuid(thread_id, "Thread")
        if category not in {"uploads", "parsed", "outputs"}:
            raise ValueError("Unknown file category")
        directory = (self._threads_root / thread_id / category).resolve()
        thread_root = (self._threads_root / thread_id).resolve()
        if not thread_root.is_relative_to(self._threads_root):
            raise ValueError("Thread directory escaped the storage root")
        if not directory.is_relative_to(thread_root):
            raise ValueError("File directory escaped the thread root")
        return directory

    def write_upload(
        self,
        *,
        thread_id: str,
        file_id: str,
        safe_filename: str,
        stream: BinaryIO,
        max_bytes: int,
    ) -> tuple[str, int]:
        """Stream one bounded upload to a server-owned unique name."""
        self._canonical_uuid(file_id, "File")
        directory = self._thread_directory(thread_id, "uploads")
        stored_name = f"{file_id}_{safe_filename}"
        destination = (directory / stored_name).resolve()
        if not destination.is_relative_to(directory):
            raise ValueError("Upload path escaped the controlled directory")

        size = 0
        try:
            with destination.open("xb") as target:
                while chunk := stream.read(_CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise FileTooLargeError
                    target.write(chunk)
            if size == 0:
                raise FileParseError
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return self._relative(destination), size

    def write_parsed(
        self,
        *,
        thread_id: str,
        file_id: str,
        source_stem: str,
        content: str,
    ) -> tuple[str, str, int]:
        """Write normalized Markdown for one successfully parsed upload."""
        self._canonical_uuid(file_id, "File")
        directory = self._thread_directory(thread_id, "parsed")
        original_name = f"{source_stem}.md"
        stored_name = f"{file_id}_{original_name}"
        destination = (directory / stored_name).resolve()
        if not destination.is_relative_to(directory):
            raise ValueError("Parsed path escaped the controlled directory")
        encoded = content.encode("utf-8")
        try:
            with destination.open("xb") as target:
                target.write(encoded)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return self._relative(destination), original_name, len(encoded)

    def write_artifact(
        self,
        *,
        thread_id: str,
        file_id: str,
        filename: str,
        content: str,
        max_bytes: int,
    ) -> tuple[str, int]:
        """Write one bounded UTF-8 Artifact to the current thread outputs directory."""
        self._canonical_uuid(file_id, "File")
        directory = self._thread_directory(thread_id, "outputs")
        encoded = content.encode("utf-8")
        if len(encoded) > max_bytes:
            raise ArtifactTooLargeError
        stored_name = f"{file_id}_{filename}"
        destination = (directory / stored_name).resolve()
        if not destination.is_relative_to(directory):
            raise ValueError("Artifact path escaped the controlled directory")
        try:
            with destination.open("xb") as target:
                target.write(encoded)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return self._relative(destination), len(encoded)

    def resolve_owned(self, *, thread_id: str, stored_path: str) -> Path:
        """Resolve trusted metadata and prove it remains in the expected thread."""
        self._canonical_uuid(thread_id, "Thread")
        logical = PurePosixPath(stored_path)
        if logical.is_absolute() or len(logical.parts) != 4:
            raise ValueError("Stored path has an invalid shape")
        if logical.parts[:2] != ("threads", thread_id):
            raise ValueError("Stored path does not belong to the thread")
        if logical.parts[2] not in {"uploads", "parsed", "outputs"}:
            raise ValueError("Stored path has an invalid category")
        candidate = self._data_root.joinpath(*logical.parts).resolve()
        thread_root = (self._threads_root / thread_id).resolve()
        if not thread_root.is_relative_to(self._threads_root):
            raise ValueError("Thread directory escaped the storage root")
        if not candidate.is_relative_to(thread_root):
            raise ValueError("Stored path escaped the thread root")
        return candidate

    def remove(self, *, thread_id: str, stored_path: str) -> None:
        """Remove one owned path without accepting a client filesystem path."""
        self.resolve_owned(thread_id=thread_id, stored_path=stored_path).unlink(missing_ok=True)

    def stage_delete(
        self, *, thread_id: str, stored_paths: tuple[str, ...]
    ) -> tuple[tuple[Path, Path], ...]:
        """Move owned files aside so database deletion can be rolled back."""
        staged: list[tuple[Path, Path]] = []
        try:
            for stored_path in stored_paths:
                original = self.resolve_owned(thread_id=thread_id, stored_path=stored_path)
                if not original.exists():
                    continue
                temporary = original.with_name(f".{original.name}.deleting-{uuid4().hex}")
                original.rename(temporary)
                staged.append((original, temporary))
        except Exception:
            self.restore_staged(tuple(staged))
            raise
        return tuple(staged)

    @staticmethod
    def restore_staged(staged: tuple[tuple[Path, Path], ...]) -> None:
        """Restore staged files after a transaction rollback."""
        for original, temporary in reversed(staged):
            if temporary.exists():
                temporary.rename(original)

    @staticmethod
    def purge_staged(staged: tuple[tuple[Path, Path], ...]) -> None:
        """Remove staged files after the metadata transaction commits."""
        for _original, temporary in staged:
            temporary.unlink(missing_ok=True)

    def recover(self, stored_paths: set[str]) -> FileRecoveryResult:
        """Resolve interrupted deletes and remove unreferenced managed files."""
        restored = 0
        purged = 0
        expected = set(stored_paths)

        if self._threads_root.exists():
            for thread_root in tuple(self._threads_root.iterdir()):
                if thread_root.is_symlink() or not thread_root.is_dir():
                    continue
                try:
                    thread_id = self._canonical_uuid(thread_root.name, "Thread")
                except ValueError:
                    continue
                for category in ("uploads", "parsed", "outputs"):
                    directory = self._thread_directory(thread_id, category)
                    if not directory.exists():
                        continue
                    for candidate in tuple(directory.iterdir()):
                        match = _STAGED_FILE.fullmatch(candidate.name)
                        if match is None:
                            continue
                        original = candidate.with_name(match.group("original"))
                        logical = self._relative(original)
                        if logical in expected and not original.exists():
                            candidate.rename(original)
                            restored += 1
                        else:
                            candidate.unlink(missing_ok=True)
                            purged += 1

                    for candidate in tuple(directory.iterdir()):
                        if not _MANAGED_FILE.match(candidate.name):
                            continue
                        logical = self._relative(candidate)
                        if candidate.is_symlink() or logical not in expected:
                            candidate.unlink(missing_ok=True)
                            purged += 1

        missing = 0
        for stored_path in expected:
            expected_logical = PurePosixPath(stored_path)
            if len(expected_logical.parts) != 4:
                missing += 1
                continue
            try:
                resolved = self.resolve_owned(
                    thread_id=expected_logical.parts[1],
                    stored_path=stored_path,
                )
            except (ValueError, OSError):
                missing += 1
                continue
            if not resolved.is_file():
                missing += 1

        return FileRecoveryResult(restored=restored, purged=purged, missing=missing)

    def _relative(self, path: Path) -> str:
        return path.relative_to(self._data_root).as_posix()
