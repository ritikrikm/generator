"""Parser for supported text resources that are useful for string search."""

from __future__ import annotations

from pathlib import Path

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class TextResourceParser(RepositoryParser[PropertyEntry]):
    """Index JSON and XML leaf-like lines as searchable pseudo properties."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".json", ".xml"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        lines = file_path.read_text(encoding="utf-8-sig").splitlines()
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
