"""TXT and Markdown parsers."""

from pathlib import Path

from app.parsers.base import ParseResult, decode_text, truncate_text


class TextParser:
    """Normalize plain text and Markdown to UTF-8 Markdown."""

    def parse(self, path: Path, *, original_name: str, max_chars: int) -> ParseResult:
        """Preserve paragraph structure and bound the normalized text."""
        text = decode_text(path).replace("\r\n", "\n").replace("\r", "\n")
        if not text.strip():
            raise ValueError("Text file is empty")
        content = f"# 文件: {original_name}\n\n{text.strip()}\n"
        return ParseResult(status="success", content=truncate_text(content, max_chars))
