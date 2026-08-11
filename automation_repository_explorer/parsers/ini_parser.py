"""INI/CFG parser backed by Python's standard configparser."""

from __future__ import annotations

import configparser
from pathlib import Path

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class IniParser(RepositoryParser[PropertyEntry]):
    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".ini", ".cfg"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        parser = configparser.ConfigParser(interpolation=None)
        with file_path.open("r", encoding="utf-8-sig") as handle:
            parser.read_file(handle)

        entries: list[PropertyEntry] = []
        for section in parser.sections():
            for key, value in parser.items(section, raw=True):
                entries.append(
                    PropertyEntry(
                        key=f"{section}.{key}",
                        value=value,
                        location=SourceLocation(file_path, 1),
                    )
                )
        return ParseResult(file_path=file_path, items=tuple(entries))
