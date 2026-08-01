"""Trusted format validation and parser orchestration."""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from app.core.exceptions import FileTypeUnsupportedError
from app.parsers import ParseResult, ParserRegistry

_ALLOWED_MIME_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".docx": frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    ".txt": frozenset({"text/plain"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".csv": frozenset({"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"}),
}


class ParserService:
    """Validate declared and actual formats before normalization."""

    def __init__(self, *, registry: ParserRegistry, max_chars: int) -> None:
        self._registry = registry
        self._max_chars = max_chars

    def validate_mime_type(self, *, extension: str, mime_type: str | None) -> str:
        """Return a normalized allow-listed media type for one extension."""
        normalized = (mime_type or "").partition(";")[0].strip().lower()
        if normalized not in _ALLOWED_MIME_TYPES[extension]:
            raise FileTypeUnsupportedError
        return normalized

    def parse(self, path: Path, *, original_name: str, extension: str) -> ParseResult:
        """Verify lightweight magic and invoke the registered format parser."""
        self._validate_actual_format(path, extension)
        return self._registry.get(extension).parse(
            path,
            original_name=original_name,
            max_chars=self._max_chars,
        )

    @staticmethod
    def _validate_actual_format(path: Path, extension: str) -> None:
        if extension == ".pdf":
            if not path.read_bytes()[:5] == b"%PDF-":
                raise FileTypeUnsupportedError
            return
        if extension == ".docx":
            try:
                with ZipFile(path) as archive:
                    names = frozenset(archive.namelist())
            except BadZipFile as exc:
                raise FileTypeUnsupportedError from exc
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise FileTypeUnsupportedError
            return
        if b"\x00" in path.read_bytes()[:8192]:
            raise FileTypeUnsupportedError
