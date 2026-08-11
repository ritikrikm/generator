"""Parser for Java .properties files."""

from __future__ import annotations

import logging
from pathlib import Path

from automation_repository_explorer.core.text_reader import read_repository_text
from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser

LOGGER = logging.getLogger(__name__)


class PropertyParser(RepositoryParser[PropertyEntry]):
    """Parse key/value pairs from .properties files without assuming one encoding."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".properties"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        LOGGER.debug("Parsing properties file %s", file_path)
        read_result = read_repository_text(file_path)
        lines = read_result.text.splitlines()

        entries: list[PropertyEntry] = []
        continuation = ""
        continuation_line = 1

        for index, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue

            if continuation:
                line = continuation + line
            else:
                continuation_line = index

            if line.endswith("\\"):
                continuation = line[:-1]
                continue
            continuation = ""

            separator_index = self._find_separator(line)
            if separator_index < 0:
                key = line.strip()
                value = ""
            else:
                key = line[:separator_index].strip()
                value = line[separator_index + 1 :].strip()

            if key:
                entries.append(
                    PropertyEntry(
                        key=key,
                        value=value,
                        location=SourceLocation(file_path, continuation_line),
                    )
                )

        warnings: tuple[str, ...] = ()
        if read_result.used_fallback:
            warnings = (
                f"UTF-8 decoding failed; parsed successfully using {read_result.encoding}.",
            )

        return ParseResult(
            file_path=file_path,
            items=tuple(entries),
            warnings=warnings,
        )

    @staticmethod
    def _find_separator(line: str) -> int:
        equals_index = line.find("=")
        colon_index = line.find(":")
        indexes = [idx for idx in (equals_index, colon_index) if idx >= 0]
        return min(indexes) if indexes else -1
