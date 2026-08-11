"""Parser for Gherkin feature files."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from automation_repository_explorer.core.exceptions import ParserError
from automation_repository_explorer.core.text_reader import read_repository_text
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
    """Static parser for Cucumber .feature files independent of folder structure."""

    _FEATURE_RE = re.compile(r"^\s*Feature\s*:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
    _RULE_RE = re.compile(r"^\s*Rule\s*:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
    _BACKGROUND_RE = re.compile(r"^\s*Background\s*:\s*(?P<name>.*?)\s*$", re.IGNORECASE)
    _SCENARIO_RE = re.compile(
        r"^\s*(?P<keyword>Scenario(?:\s+Outline)?|Scenario Template)\s*:\s*(?P<name>.+?)\s*$",
        re.IGNORECASE,
    )
    _STEP_RE = re.compile(r"^\s*(?P<keyword>Given|When|Then|And|But|\*)\s+(?P<text>.+?)\s*$")
    _EXAMPLES_RE = re.compile(r"^\s*Examples\s*:\s*(?P<name>.*?)\s*$", re.IGNORECASE)
    _LANGUAGE_RE = re.compile(r"^\s*#\s*language\s*:\s*(?P<language>[\w-]+)\s*$", re.IGNORECASE)

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".feature"})

    def parse(self, file_path: Path) -> ParseResult[FeatureDocument]:
        LOGGER.debug("Parsing feature file %s", file_path)
        read_result = read_repository_text(file_path)
        lines = read_result.text.splitlines()
        warnings: list[str] = []
        if read_result.used_fallback:
            warnings.append(
                f"UTF-8 decoding failed; parsed successfully using {read_result.encoding}."
            )

        feature_name = ""
        feature_line = 1
        feature_tags: list[str] = []
        pending_tags: list[str] = []
        scenarios: list[Scenario] = []

        feature_background_steps: list[Step] = []
        rule_background_steps: list[Step] = []
        in_rule = False
        background_target: list[Step] | None = None

        current_name = ""
        current_keyword = ""
        current_line = 1
        current_tags: tuple[str, ...] = ()
        current_steps: list[Step] = []
        current_examples: list[ExamplesTable] = []

        def effective_background() -> list[Step]:
            return [*feature_background_steps, *rule_background_steps]

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

            language_match = self._LANGUAGE_RE.match(raw)
            if language_match:
                language = language_match.group("language").lower()
                if language not in {"en", "en-us", "en-gb"}:
                    raise ParserError(
                        f"Unsupported Gherkin language '{language}' in {file_path}. "
                        "ARE currently parses English Cucumber keywords."
                    )
                index += 1
                continue

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

            rule_match = self._RULE_RE.match(raw)
            if rule_match:
                flush_scenario()
                in_rule = True
                rule_background_steps = []
                background_target = None
                pending_tags.clear()
                index += 1
                continue

            if self._BACKGROUND_RE.match(raw):
                flush_scenario()
                background_target = rule_background_steps if in_rule else feature_background_steps
                background_target.clear()
                pending_tags.clear()
                index += 1
                continue

            scenario_match = self._SCENARIO_RE.match(raw)
            if scenario_match:
                flush_scenario()
                background_target = None
                current_name = scenario_match.group("name").strip()
                current_keyword = scenario_match.group("keyword").strip()
                current_line = line_number
                current_tags = tuple(pending_tags)
                pending_tags.clear()
                current_steps = effective_background()
                index += 1
                continue

            step_match = self._STEP_RE.match(raw)
            if step_match:
                step = Step(
                    keyword=step_match.group("keyword").title(),
                    text=step_match.group("text").strip(),
                    location=SourceLocation(file_path, line_number),
                )
                if current_name:
                    current_steps.append(step)
                elif background_target is not None:
                    background_target.append(step)
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
                    warnings=warnings,
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
            warnings=tuple(warnings),
        )

    def _parse_examples_table(
        self,
        lines: list[str],
        file_path: Path,
        start_index: int,
        tags: tuple[str, ...],
        warnings: list[str],
    ) -> tuple[ExamplesTable | None, int]:
        index = start_index

        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith("#"):
                index += 1
                continue
            if stripped.startswith("|"):
                break
            if (
                stripped.startswith("@")
                or self._SCENARIO_RE.match(lines[index])
                or self._RULE_RE.match(lines[index])
            ):
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
                warnings.append(
                    f"Examples row {index + 1} has {len(values)} values but "
                    f"{len(headers)} headers; row skipped and remaining file continued."
                )
                index += 1
                continue

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
        r"""Split a Gherkin table row while preserving escaped pipes (\|)."""

        text = row.strip()
        if text.startswith("|"):
            text = text[1:]
        if text.endswith("|") and not text.endswith("\\|"):
            text = text[:-1]

        cells: list[str] = []
        current: list[str] = []
        escaped = False
        for char in text:
            if escaped:
                if char == "n":
                    current.append("\n")
                else:
                    current.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == "|":
                cells.append("".join(current).strip())
                current = []
                continue
            current.append(char)

        if escaped:
            current.append("\\")
        cells.append("".join(current).strip())
        return cells
