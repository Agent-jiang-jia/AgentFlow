"""Bounded CSV to Markdown conversion."""

import csv
from pathlib import Path

from app.parsers.base import ParseResult, decode_text, markdown_cell, truncate_text

_MAX_ROWS = 500


class CsvParser:
    """Read common text encodings and render at most 500 data rows."""

    def parse(self, path: Path, *, original_name: str, max_chars: int) -> ParseResult:
        """Include column names, total rows, and an explicit truncation flag."""
        text = decode_text(path)
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(text.splitlines(), dialect=dialect))
        if not rows or not any(cell.strip() for row in rows for cell in row):
            raise ValueError("CSV contains no data")

        header = rows[0]
        data_rows = rows[1:]
        column_count = max(1, len(header), *(len(row) for row in data_rows))
        normalized_header = header + [""] * (column_count - len(header))
        if not any(cell.strip() for cell in normalized_header):
            normalized_header = [f"列 {index}" for index in range(1, column_count + 1)]
        visible_rows = data_rows[:_MAX_ROWS]
        padded_rows = [row + [""] * (column_count - len(row)) for row in visible_rows]
        truncated = len(data_rows) > _MAX_ROWS
        table_lines = [
            f"| {' | '.join(markdown_cell(cell) for cell in normalized_header)} |",
            f"| {' | '.join(['---'] * column_count)} |",
            *(f"| {' | '.join(markdown_cell(cell) for cell in row)} |" for row in padded_rows),
        ]
        content = "\n\n".join(
            (
                f"# 文件: {original_name}",
                f"总数据行数: {len(data_rows)}\n\n是否截断: {'是' if truncated else '否'}",
                "\n".join(table_lines),
            )
        )
        return ParseResult(status="success", content=truncate_text(content + "\n", max_chars))
