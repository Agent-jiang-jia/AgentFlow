"""PDF text extraction without OCR."""

from pathlib import Path

import fitz  # type: ignore[import-untyped]  # PyMuPDF does not publish typing metadata.

from app.parsers.base import ParseResult, truncate_text

_MIN_VISIBLE_CHARACTERS = 20


class PdfParser:
    """Extract page-aware Markdown from text PDFs."""

    def parse(self, path: Path, *, original_name: str, max_chars: int) -> ParseResult:
        """Mark page-bearing PDFs with too little text as unsupported OCR."""
        sections = [f"# 文件: {original_name}"]
        visible_characters = 0
        with fitz.open(path) as document:
            if document.page_count == 0:
                raise ValueError("PDF has no pages")
            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                visible_characters += sum(not character.isspace() for character in text)
                sections.append(f"## 第 {page_number} 页\n\n{text}")
        if visible_characters < _MIN_VISIBLE_CHARACTERS:
            return ParseResult(
                status="unsupported_ocr",
                content=None,
                error="该 PDF 可能是扫描件; V1 暂不支持 OCR。",
            )
        return ParseResult(
            status="success",
            content=truncate_text("\n\n".join(sections).strip() + "\n", max_chars),
        )
