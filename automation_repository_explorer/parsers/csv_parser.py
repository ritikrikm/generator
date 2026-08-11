"""CSV parser backed by Python's csv module."""

from __future__ import annotations

import csv
from pathlib import Path

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class CsvParser(RepositoryParser[PropertyEntry]):
    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".csv"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        entries: list[PropertyEntry] = []
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_index, row in enumerate(reader, start=2):
                for column, value in row.items():
                    if column is None or value is None:
                        continue
                    entries.append(
                        PropertyEntry(
                            key=f"$row[{row_index - 2}].{column}",
                            value=value,
                            location=SourceLocation(file_path, row_index),
                        )
                    )
        return ParseResult(file_path=file_path, items=tuple(entries))
