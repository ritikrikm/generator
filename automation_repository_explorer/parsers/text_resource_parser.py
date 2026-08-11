"""Parser for supported text resources that are useful for string search."""

from __future__ import annotations

from pathlib import Path

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class TextResourceParser(RepositoryParser[PropertyEntry]):
    """Index common text configuration resources as searchable pseudo properties.

    These formats are intentionally treated as generic text resources rather than assuming a
    team-specific schema. This keeps ARE useful across repositories with different configuration
    layouts while still allowing values to participate in search and graph exploration.
    """

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".json", ".xml", ".yaml", ".yml"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        try:
            lines = file_path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as exc:
            from automation_repository_explorer.core.exceptions import ParserError

            raise ParserError(f"Unable to read text resource {file_path}: {exc}") from exc

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
