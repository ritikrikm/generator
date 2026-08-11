"""Parser for supported text resources that are useful for string search."""

from __future__ import annotations

from pathlib import Path

from automation_repository_explorer.core.text_reader import read_repository_text
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
        read_result = read_repository_text(file_path)
        lines = read_result.text.splitlines()

        entries = tuple(
            PropertyEntry(
                key=f"{file_path.name}:{line_number}",
                value=line.strip(),
                location=SourceLocation(file_path, line_number),
            )
            for line_number, line in enumerate(lines, start=1)
            if line.strip()
        )

        warnings: tuple[str, ...] = ()
        if read_result.used_fallback:
            warnings = (
                f"UTF-8 decoding failed; parsed successfully using {read_result.encoding}.",
            )

        return ParseResult(file_path=file_path, items=entries, warnings=warnings)
