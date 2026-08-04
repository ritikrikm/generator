"""Parser for supported text resources that are useful for string search."""

from __future__ import annotations

from pathlib import Path

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser
from automation_repository_explorer.parsers.text_reader import read_text_file


class TextResourceParser(RepositoryParser[PropertyEntry]):
    """Index JSON and XML leaf-like lines as searchable pseudo properties."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".json", ".xml"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        file_kind = file_path.suffix.lower().lstrip(".") or "text"
        lines = read_text_file(file_path, file_kind).splitlines()
        entries = tuple(
            PropertyEntry(
                key=f"{file_path.name}:{line_number}",
                value=line.strip(),
                location=SourceLocation(file_path, line_number),
            )
            for line_number, line in enumerate(lines, start=1)
            if line.strip()
        )
        return ParseResult(file_path=file_path, items=entries)
