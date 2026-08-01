"""Cross-platform upload filename validation tests."""

import pytest
from app.core.exceptions import FileTypeUnsupportedError, InvalidFilenameError
from app.storage.filename import validate_upload_filename


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("需求 文档.DOCX", ("需求 文档.DOCX", ".docx")),
        ("数据.csv", ("数据.csv", ".csv")),
        ("notes.md", ("notes.md", ".md")),
    ],
)
def test_valid_upload_names_preserve_display_name(filename: str, expected: tuple[str, str]) -> None:
    """Safe Unicode names and spaces remain user-visible while extensions normalize."""
    assert validate_upload_filename(filename) == expected


@pytest.mark.parametrize(
    "filename",
    [
        None,
        "",
        "..",
        "../secret.txt",
        "folder/file.txt",
        r"folder\file.txt",
        "CON.txt",
        "lpt9.csv",
        "bad?.md",
        "tail. ",
    ],
)
def test_unsafe_or_windows_reserved_names_are_rejected(filename: str | None) -> None:
    """Traversal, separators, illegal characters, and reserved stems are rejected."""
    with pytest.raises(InvalidFilenameError):
        validate_upload_filename(filename)


def test_unsupported_extension_is_distinct_from_invalid_name() -> None:
    """A safe name with a non-V1 extension receives the stable type error."""
    with pytest.raises(FileTypeUnsupportedError):
        validate_upload_filename("slides.pptx")
