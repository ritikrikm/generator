"""YAML parser backed by ruamel.yaml (YAML 1.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class YamlParser(RepositoryParser[PropertyEntry]):
    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".yaml", ".yml"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        yaml = YAML(typ="rt")
        with file_path.open("r", encoding="utf-8-sig") as handle:
            documents = tuple(yaml.load_all(handle))

        entries: list[PropertyEntry] = []
        for document_index, document in enumerate(documents):
            root = "$" if len(documents) == 1 else f"$doc[{document_index}]"
            entries.extend(self._flatten(document, file_path, root, 1))
        return ParseResult(file_path=file_path, items=tuple(entries))

    def _flatten(
        self,
        value: Any,
        file_path: Path,
        path: str,
        line: int,
    ) -> list[PropertyEntry]:
        entries: list[PropertyEntry] = []
        if isinstance(value, dict):
            for key, child in value.items():
                child_line = self._mapping_line(value, key, line)
                entries.extend(
                    self._flatten(child, file_path, f"{path}.{key}", child_line)
                )
        elif isinstance(value, list):
            for index, child in enumerate(value):
                child_line = self._sequence_line(value, index, line)
                entries.extend(
                    self._flatten(child, file_path, f"{path}[{index}]", child_line)
                )
        else:
            entries.append(
                PropertyEntry(
                    key=path,
                    value=_scalar_text(value),
                    location=SourceLocation(file_path, line),
                )
            )
        return entries

    @staticmethod
    def _mapping_line(value: Any, key: Any, fallback: int) -> int:
        try:
            position = value.lc.value(key)
            return int(position[0]) + 1 if position else fallback
        except (AttributeError, KeyError, TypeError):
            return fallback

    @staticmethod
    def _sequence_line(value: Any, index: int, fallback: int) -> int:
        try:
            position = value.lc.item(index)
            return int(position[0]) + 1 if position else fallback
        except (AttributeError, IndexError, TypeError):
            return fallback


def _scalar_text(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
