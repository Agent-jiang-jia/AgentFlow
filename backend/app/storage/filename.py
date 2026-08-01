"""Cross-platform validation for user-visible file names."""

import re
from pathlib import Path

from app.core.exceptions import FileTypeUnsupportedError, InvalidFilenameError

ALLOWED_UPLOAD_EXTENSIONS = frozenset({".pdf", ".docx", ".txt", ".md", ".csv"})
ALLOWED_ARTIFACT_EXTENSIONS = frozenset(
    {".md", ".txt", ".html", ".csv", ".json", ".py", ".js", ".ts", ".yaml", ".yml"}
)
_INVALID_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


def validate_upload_filename(filename: str | None) -> tuple[str, str]:
    """Return a safe original name and lowercase supported extension."""
    if filename is None:
        raise InvalidFilenameError
    normalized = filename.strip()
    if (
        not normalized
        or len(normalized) > 255
        or normalized in {".", ".."}
        or normalized.endswith((".", " "))
        or _INVALID_CHARACTERS.search(normalized) is not None
    ):
        raise InvalidFilenameError

    reserved_stem = normalized.split(".", maxsplit=1)[0].upper()
    if reserved_stem in _WINDOWS_RESERVED:
        raise InvalidFilenameError

    extension = Path(normalized).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise FileTypeUnsupportedError
    return normalized, extension


def validate_artifact_filename(filename: str) -> tuple[str, str]:
    """Return a safe leaf name and approved generated-file extension."""
    normalized = filename.strip()
    if ".." in normalized:
        raise InvalidFilenameError
    if (
        not normalized
        or len(normalized) > 255
        or normalized.endswith((".", " "))
        or _INVALID_CHARACTERS.search(normalized) is not None
    ):
        raise InvalidFilenameError

    reserved_stem = normalized.split(".", maxsplit=1)[0].upper()
    if reserved_stem in _WINDOWS_RESERVED:
        raise InvalidFilenameError

    extension = Path(normalized).suffix.lower()
    if extension not in ALLOWED_ARTIFACT_EXTENSIONS:
        raise FileTypeUnsupportedError
    return normalized, extension
