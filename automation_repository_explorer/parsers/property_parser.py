"""Java .properties parser backed by javaproperties."""

from __future__ import annotations

from pathlib import Path

import javaproperties

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class PropertyParser(RepositoryParser[PropertyEntry]):
    """Parse Java properties using Java-compatible escaping and continuation rules."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".properties"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        entries: list[PropertyEntry] = []
        line = 1

        for element in javaproperties.parse(file_path.read_bytes()):
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

        return ParseResult(file_path=file_path, items=tuple(entries))
