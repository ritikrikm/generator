"""Parser for Gherkin feature files."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from automation_repository_explorer.core.exceptions import ParserError
from automation_repository_explorer.models.domain import (
    ExamplesTable,
    FeatureDocument,
    Scenario,
    SourceLocation,
    Step,
)
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser

LOGGER = logging.getLogger(__name__)


class FeatureParser(RepositoryParser[FeatureDocument]):
    """Static parser for Cucumber .feature files."""

    _FEATURE_RE = re.compile(r"^\s*Feature\s*:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
    _SCENARIO_RE = re.compile(
        r"^\s*(?P<keyword>Scenario(?:\s+Outline)?|Scenario Template)\s*:\s*(?P<name>.+?)\s*$",
        re.IGNORECASE,
    )
    _STEP_RE = re.compile(r"^\s*(?P<keyword>Given|When|Then|And|But|\*)\s+(?P<text>.+?)\s*$")
    _EXAMPLES_RE = re.compile(r"^\s*Examples\s*:\s*$", re.IGNORECASE)

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".feature"})

    def parse(self, file_path: Path) -> ParseResult[FeatureDocument]:
        LOGGER.debug("Parsing feature file %s", file_path)
        try:
            lines = file_path.read_text(encoding="utf-8-sig").splitlines()
        except OSError as exc:
            raise ParserError(f"Unable to read feature file {file_path}") from exc

        feature_name = ""
        feature_line = 1
        feature_tags: list[str] = []
        pending_tags: list[str] = []
        scenarios: list[Scenario] = []

        current_name = ""
        current_keyword = ""
        current_line = 1
        current_tags: tuple[str, ...] = ()
        current_steps: list[Step] = []
        current_examples: list[ExamplesTable] = []

        def flush_scenario() -> None:
            nonlocal current_name, current_keyword, current_line, current_tags
            nonlocal current_steps, current_examples
            if not current_name:
                return
            scenarios.append(
                Scenario(
                    name=current_name,
                    keyword=current_keyword,
                    tags=current_tags,
                    location=SourceLocation(file_path, current_line),
                    steps=tuple(current_steps),
                    examples=tuple(current_examples),
                )
            )
            current_name = ""
            current_keyword = ""
            current_line = 1
            current_tags = ()
            current_steps = []
            current_examples = []

        index = 0
        while index < len(lines):
            raw = lines[index]
            stripped = raw.strip()
            line_number = index + 1

            if not stripped or stripped.startswith("#"):
                index += 1
                continue

            if stripped.startswith("@"):
                pending_tags.extend(stripped.split())
                index += 1
                continue

            feature_match = self._FEATURE_RE.match(raw)
            if feature_match:
                flush_scenario()
                feature_name = feature_match.group("name").strip()
                feature_line = line_number
                feature_tags = pending_tags.copy()
                pending_tags.clear()
                index += 1
                continue

            scenario_match = self._SCENARIO_RE.match(raw)
            if scenario_match:
                flush_scenario()
                current_name = scenario_match.group("name").strip()
                current_keyword = scenario_match.group("keyword").strip()
                current_line = line_number
                current_tags = tuple(pending_tags)
                pending_tags.clear()
                index += 1
                continue

            step_match = self._STEP_RE.match(raw)
            if step_match and current_name:
                current_steps.append(
                    Step(
                        keyword=step_match.group("keyword").title(),
                        text=step_match.group("text").strip(),
                        location=SourceLocation(file_path, line_number),
                    )
                )
                index += 1
                continue

            if self._EXAMPLES_RE.match(raw) and current_name:
                examples_tags = tuple(pending_tags)
                pending_tags.clear()
                table, next_index = self._parse_examples_table(
                    lines=lines,
                    file_path=file_path,
                    start_index=index + 1,
                    tags=examples_tags,
                )
                if table is not None:
                    current_examples.append(table)
                index = next_index
                continue

            index += 1

        flush_scenario()

        if not feature_name:
            raise ParserError(f"No Feature declaration found in {file_path}")

        return ParseResult(
            file_path=file_path,
            items=(
                FeatureDocument(
                    name=feature_name,
                    location=SourceLocation(file_path, feature_line),
                    tags=tuple(feature_tags),
                    scenarios=tuple(scenarios),
                ),
            ),
        )

    def _parse_examples_table(
        self,
        lines: list[str],
        file_path: Path,
        start_index: int,
        tags: tuple[str, ...],
    ) -> tuple[ExamplesTable | None, int]:
        index = start_index

        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith("#"):
                index += 1
                continue
            if stripped.startswith("|"):
                break
            if stripped.startswith("@") or self._SCENARIO_RE.match(lines[index]):
                return None, index
            index += 1

        if index >= len(lines):
            return None, index

        header_line = index + 1
        headers = tuple(self._split_table_row(lines[index]))
        index += 1

        rows: list[dict[str, str]] = []
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                continue
            if not stripped.startswith("|"):
                break

            values = self._split_table_row(lines[index])
            if len(values) != len(headers):
                raise ParserError(
                    f"Examples row in {file_path}:{index + 1} has {len(values)} values "
                    f"but {len(headers)} headers"
                )
            rows.append(dict(zip(headers, values, strict=True)))
            index += 1

        return (
            ExamplesTable(
                headers=headers,
                rows=tuple(rows),
                tags=tags,
                location=SourceLocation(file_path, header_line),
            ),
            index,
        )

    @staticmethod
    def _split_table_row(row: str) -> list[str]:
        return [cell.strip().replace("\\n", "\n") for cell in row.strip().strip("|").split("|")]
