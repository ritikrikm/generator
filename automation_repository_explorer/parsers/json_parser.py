"""JSON parser backed by Python's standards-compliant json module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class JsonParser(RepositoryParser[PropertyEntry]):
    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".json"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        with file_path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        entries = tuple(
            PropertyEntry(
                key=path,
                value=_scalar_text(value),
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


def _scalar_text(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
