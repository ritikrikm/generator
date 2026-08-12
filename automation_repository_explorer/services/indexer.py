"""Repository indexing service."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from automation_repository_explorer.models.domain import (
    FeatureDocument,
    JavaClass,
    PropertyEntry,
    RepositoryFile,
)
from automation_repository_explorer.parsers.base import RepositoryParser
from automation_repository_explorer.parsers.csv_parser import CsvParser
from automation_repository_explorer.parsers.feature_parser import FeatureParser
from automation_repository_explorer.parsers.ini_parser import IniParser
from automation_repository_explorer.parsers.jdt_project_analyzer import JdtProjectAnalyzer
from automation_repository_explorer.parsers.json_parser import JsonParser
from automation_repository_explorer.parsers.property_parser import PropertyParser
from automation_repository_explorer.parsers.toml_parser import TomlParser
from automation_repository_explorer.parsers.xml_parser import XmlParser
from automation_repository_explorer.parsers.yaml_parser import YamlParser
from automation_repository_explorer.services.scanner import ProgressCallback, RepositoryScanner

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParseIssue:
    file_path: Path
    parser_name: str
    message: str
    severity: str = "error"


@dataclass(slots=True)
class RepositoryIndex:
    root: Path
    files: tuple[RepositoryFile, ...]
    features: tuple[FeatureDocument, ...] = field(default_factory=tuple)
    java_classes: tuple[JavaClass, ...] = field(default_factory=tuple)
    properties: tuple[PropertyEntry, ...] = field(default_factory=tuple)
    parse_issues: tuple[ParseIssue, ...] = field(default_factory=tuple)
    java_analysis_complete: bool = True
    java_analysis_backend: str = "eclipse-jdt"


class RepositoryIndexer:
    """Build an index using official/standards-based parsers plus Eclipse JDT."""

    def __init__(
        self,
        parsers: tuple[RepositoryParser[object], ...] | None = None,
        java_analyzer: JdtProjectAnalyzer | None = None,
    ) -> None:
        self._parsers = parsers or (
            FeatureParser(),
            PropertyParser(),
            JsonParser(),
            XmlParser(),
            YamlParser(),
            CsvParser(),
            TomlParser(),
            IniParser(),
        )
        self._java_analyzer = java_analyzer or JdtProjectAnalyzer()

    @property
    def supported_extensions(self) -> set[str]:
        extensions = {
            extension
            for parser in self._parsers
            for extension in parser.supported_extensions
        }
        extensions.add(".java")
        return extensions

    def build_index(
        self,
        repository_path: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> RepositoryIndex:
        scanner = RepositoryScanner(self.supported_extensions)
        files = scanner.scan(repository_path, progress_callback=progress_callback)

        features: list[FeatureDocument] = []
        java_classes: list[JavaClass] = []
        properties: list[PropertyEntry] = []
        parse_issues: list[ParseIssue] = []

        parser_by_extension = self._parser_map()
        non_java_files = tuple(
            repository_file
            for repository_file in files
            if repository_file.extension != ".java"
        )
        java_files = tuple(
            repository_file.path
            for repository_file in files
            if repository_file.extension == ".java"
        )

        total_non_java = len(non_java_files)
        for index, repository_file in enumerate(non_java_files, start=1):
            if progress_callback and total_non_java:
                percent = 10 + int((index / total_non_java) * 52)
                progress_callback(
                    percent,
                    f"Parsing {index}/{total_non_java}: {repository_file.path.name}",
                )

            parser = parser_by_extension.get(repository_file.extension)
            if parser is None:
                parse_issues.append(
                    ParseIssue(
                        file_path=repository_file.path,
                        parser_name="none",
                        message=f"No parser registered for {repository_file.extension}",
                    )
                )
                continue

            try:
                result = parser.parse(repository_file.path)
            except Exception as exc:  # noqa: BLE001 - isolate malformed files
                parse_issues.append(
                    ParseIssue(
                        file_path=repository_file.path,
                        parser_name=parser.__class__.__name__,
                        message=str(exc) or exc.__class__.__name__,
                    )
                )
                LOGGER.warning(
                    "Failed to parse %s with %s: %s",
                    repository_file.path,
                    parser.__class__.__name__,
                    exc,
                )
                continue

            for warning in result.warnings:
                parse_issues.append(
                    ParseIssue(
                        file_path=repository_file.path,
                        parser_name=parser.__class__.__name__,
                        message=warning,
                        severity="warning",
                    )
                )

            for item in result.items:
                if isinstance(item, FeatureDocument):
                    features.append(item)
                elif isinstance(item, JavaClass):
                    java_classes.append(item)
                elif isinstance(item, PropertyEntry):
                    properties.append(item)

        java_analysis_complete = True
        if java_files:
            if progress_callback:
                progress_callback(
                    64,
                    f"Analyzing {len(java_files)} Java file(s) with Eclipse JDT...",
                )
            try:
                jdt_result = self._java_analyzer.analyze(repository_path, java_files)
                java_classes.extend(jdt_result.classes)
                java_analysis_complete = jdt_result.semantic_complete
                parse_issues.extend(
                    ParseIssue(
                        file_path=diagnostic.file_path,
                        parser_name="EclipseJDT",
                        message=diagnostic.message,
                        severity=diagnostic.severity,
                    )
                    for diagnostic in jdt_result.diagnostics
                )
            except Exception as exc:  # noqa: BLE001 - surface JDT failure without fake certainty
                java_analysis_complete = False
                parse_issues.append(
                    ParseIssue(
                        file_path=repository_path,
                        parser_name="EclipseJDT",
                        message=str(exc) or exc.__class__.__name__,
                        severity="error",
                    )
                )
                LOGGER.warning("Eclipse JDT analysis failed: %s", exc)

        if progress_callback:
            errors = sum(issue.severity == "error" for issue in parse_issues)
            warnings = sum(issue.severity == "warning" for issue in parse_issues)
            progress_callback(
                80,
                f"Indexed {len(files)} supported files with "
                f"{errors} error(s) and {warnings} warning(s).",
            )

        return RepositoryIndex(
            root=repository_path,
            files=files,
            features=tuple(features),
            java_classes=tuple(java_classes),
            properties=tuple(properties),
            parse_issues=tuple(parse_issues),
            java_analysis_complete=java_analysis_complete,
            java_analysis_backend="eclipse-jdt",
        )

    def _parser_map(self) -> dict[str, RepositoryParser[object]]:
        parser_by_extension: dict[str, RepositoryParser[object]] = {}
        for parser in self._parsers:
            for extension in parser.supported_extensions:
                parser_by_extension[extension] = parser
        return parser_by_extension
