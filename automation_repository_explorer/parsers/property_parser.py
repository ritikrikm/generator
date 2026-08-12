"""Java .properties parser backed by javaproperties."""

from __future__ import annotations

from pathlib import Path

import javaproperties

from automation_repository_explorer.core.text_reader import read_repository_text
from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class PropertyParser(RepositoryParser[PropertyEntry]):
    """Parse Java properties using Java-compatible escaping and continuation rules."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".properties"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        read_result = read_repository_text(file_path)
        entries: list[PropertyEntry] = []
        line = 1

        for element in javaproperties.parse(read_result.text):
            source = element.source
            if isinstance(element, javaproperties.KeyValue):
                entries.append(
                    PropertyEntry(
                        key=element.key,
                        value=element.value,
                        location=SourceLocation(file_path, line),
                    )
                )
            if isinstance(source, bytes):
                line += source.count(b"\n")
            else:
                line += str(source).count("\n")

        warnings: tuple[str, ...] = tuple()
        if read_result.used_fallback:
            warnings = (
                f"UTF-8 decoding failed; parsed successfully using {read_result.encoding}.",
            )
        return ParseResult(file_path=file_path, items=tuple(entries), warnings=warnings)
