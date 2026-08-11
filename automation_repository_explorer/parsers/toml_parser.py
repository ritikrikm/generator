"""TOML parser backed by Python's standard tomllib."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class TomlParser(RepositoryParser[PropertyEntry]):
    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".toml"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        with file_path.open("rb") as handle:
            data = tomllib.load(handle)
        entries = tuple(
            PropertyEntry(
                key=path,
                value=str(value),
                location=SourceLocation(file_path, 1),
            )
            for path, value in _flatten(data)
        )
        return ParseResult(file_path=file_path, items=entries)


def _flatten(value: Any, path: str = "$") -> tuple[tuple[str, Any], ...]:
    leaves: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            leaves.extend(_flatten(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.extend(_flatten(child, f"{path}[{index}]"))
    else:
        leaves.append((path, value))
    return tuple(leaves)
