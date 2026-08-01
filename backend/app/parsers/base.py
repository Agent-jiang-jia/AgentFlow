"""Shared parser contracts and text helpers."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Normalized result produced by a supported file parser."""

    status: str
    content: str | None
    error: str | None = None


class FileParser(Protocol):
    """Convert one trusted local upload into bounded Markdown."""

    def parse(self, path: Path, *, original_name: str, max_chars: int) -> ParseResult:
        """Parse a trusted path without exposing it in the result."""
        ...


def truncate_text(content: str, max_chars: int) -> str:
    """Bound normalized output while making truncation explicit."""
    if len(content) <= max_chars:
        return content
    marker = "\n\n> 内容已按系统解析上限截断。"
    keep = max(0, max_chars - len(marker))
    return f"{content[:keep].rstrip()}{marker}"


def decode_text(path: Path) -> str:
    """Decode text with deterministic UTF and common Chinese fallbacks."""
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "big5"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unsupported text encoding")


def markdown_cell(value: str) -> str:
    """Escape one value for a compact Markdown table cell."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")
