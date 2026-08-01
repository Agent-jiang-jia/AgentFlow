"""Supported extension to parser registry."""

from app.parsers.base import FileParser
from app.parsers.csv import CsvParser
from app.parsers.docx import DocxParser
from app.parsers.pdf import PdfParser
from app.parsers.text import TextParser


class ParserRegistry:
    """Resolve exactly one parser for every supported upload extension."""

    def __init__(self) -> None:
        text_parser = TextParser()
        self._parsers: dict[str, FileParser] = {
            ".pdf": PdfParser(),
            ".docx": DocxParser(),
            ".txt": text_parser,
            ".md": text_parser,
            ".csv": CsvParser(),
        }

    def get(self, extension: str) -> FileParser:
        """Return the parser for a previously validated extension."""
        try:
            return self._parsers[extension]
        except KeyError as exc:
            raise ValueError("No parser registered for extension") from exc
