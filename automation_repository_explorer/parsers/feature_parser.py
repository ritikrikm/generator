"""Official Cucumber Gherkin parser adapter for ARE."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gherkin.parser import Parser as GherkinParser

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


class FeatureParser(RepositoryParser[FeatureDocument]):
    """Parse .feature files with Cucumber's official Gherkin parser."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".feature"})

    def parse(self, file_path: Path) -> ParseResult[FeatureDocument]:
        read_result = read_repository_text(file_path)
        try:
            document = GherkinParser().parse(read_result.text)
        except Exception as exc:
            raise ParserError(f"Gherkin parse failed for {file_path}: {exc}") from exc

        feature = document.get("feature")
        if not feature:
            raise ParserError(f"No Gherkin Feature was found in {file_path}")

        warnings: list[str] = []
        if read_result.used_fallback:
            warnings.append(
                f"UTF-8 decoding failed; parsed successfully using {read_result.encoding}."
            )

        feature_background: tuple[Step, ...] = tuple()
        scenarios: list[Scenario] = []

        for child in feature.get("children", []):
            if "background" in child:
                feature_background = self._steps(
                    child["background"].get("steps", []), file_path
                )
            elif "scenario" in child:
                scenarios.append(
                    self._scenario(
                        child["scenario"],
                        file_path,
                        prefix_steps=feature_background,
                        warnings=warnings,
                    )
                )
            elif "rule" in child:
                scenarios.extend(
                    self._rule_scenarios(
                        child["rule"],
                        file_path,
                        feature_background=feature_background,
                        warnings=warnings,
                    )
                )

        feature_document = FeatureDocument(
            name=str(feature.get("name", "")),
            location=self._location(file_path, feature.get("location")),
            tags=self._tags(feature.get("tags", [])),
            scenarios=tuple(scenarios),
        )
        return ParseResult(
            file_path=file_path,
            items=(feature_document,),
            warnings=tuple(warnings),
        )

    def _rule_scenarios(
        self,
        rule: dict[str, Any],
        file_path: Path,
        *,
        feature_background: tuple[Step, ...],
        warnings: list[str],
    ) -> tuple[Scenario, ...]:
        rule_background: tuple[Step, ...] = tuple()
        scenarios: list[Scenario] = []

        for child in rule.get("children", []):
            if "background" in child:
                rule_background = self._steps(
                    child["background"].get("steps", []), file_path
                )
            elif "scenario" in child:
                scenarios.append(
                    self._scenario(
                        child["scenario"],
                        file_path,
                        prefix_steps=feature_background + rule_background,
                        warnings=warnings,
                    )
                )
        return tuple(scenarios)

    def _scenario(
        self,
        scenario: dict[str, Any],
        file_path: Path,
        *,
        prefix_steps: tuple[Step, ...],
        warnings: list[str],
    ) -> Scenario:
        examples = tuple(
            table
            for example in scenario.get("examples", [])
            if (
                table := self._examples_table(
                    example,
                    file_path,
                    warnings=warnings,
                )
            )
            is not None
        )
        return Scenario(
            name=str(scenario.get("name", "")),
            keyword=str(scenario.get("keyword", "Scenario")).strip(),
            tags=self._tags(scenario.get("tags", [])),
            location=self._location(file_path, scenario.get("location")),
            steps=prefix_steps + self._steps(scenario.get("steps", []), file_path),
            examples=examples,
        )

    def _examples_table(
        self,
        example: dict[str, Any],
        file_path: Path,
        *,
        warnings: list[str],
    ) -> ExamplesTable | None:
        header = example.get("tableHeader")
        if not header:
            return None

        headers = tuple(str(cell.get("value", "")) for cell in header.get("cells", []))
        rows: list[dict[str, str]] = []
        for row in example.get("tableBody", []):
            values = tuple(str(cell.get("value", "")) for cell in row.get("cells", []))
            if len(values) != len(headers):
                line = int(row.get("location", {}).get("line", 1))
                warnings.append(
                    f"Examples row {line} has {len(values)} values but {len(headers)} "
                    "headers; row skipped."
                )
                continue
            rows.append(dict(zip(headers, values, strict=True)))

        return ExamplesTable(
            headers=headers,
            rows=tuple(rows),
            tags=self._tags(example.get("tags", [])),
            location=self._location(file_path, example.get("location")),
        )

    def _steps(
        self,
        steps: list[dict[str, Any]],
        file_path: Path,
    ) -> tuple[Step, ...]:
        return tuple(
            Step(
                keyword=str(step.get("keyword", "")).strip(),
                text=str(step.get("text", "")).strip(),
                location=self._location(file_path, step.get("location")),
            )
            for step in steps
        )

    @staticmethod
    def _tags(tags: list[dict[str, Any]]) -> tuple[str, ...]:
        return tuple(
            str(tag.get("name", "")).strip()
            for tag in tags
            if tag.get("name")
        )

    @staticmethod
    def _location(
        file_path: Path,
        location: dict[str, Any] | None,
    ) -> SourceLocation:
        location = location or {}
        return SourceLocation(
            file_path=file_path,
            line=int(location.get("line", 1)),
            column=int(location.get("column", 1)),
        )
