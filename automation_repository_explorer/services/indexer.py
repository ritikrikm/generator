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
from automation_repository_explorer.parsers.feature_parser import FeatureParser
from automation_repository_explorer.parsers.java_parser import JavaParser
from automation_repository_explorer.parsers.property_parser import PropertyParser
from automation_repository_explorer.parsers.text_resource_parser import TextResourceParser
from automation_repository_explorer.services.scanner import ProgressCallback, RepositoryScanner

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParseIssue:
    """A parser diagnostic produced while exploring a supported repository file."""

    file_path: Path
    parser_name: str
    message: str
    severity: str = "error"


@dataclass(slots=True)
class RepositoryIndex:
    """Static repository index produced from parsers."""

    root: Path
    files: tuple[RepositoryFile, ...]
    features: tuple[FeatureDocument, ...] = field(default_factory=tuple)
    java_classes: tuple[JavaClass, ...] = field(default_factory=tuple)
    properties: tuple[PropertyEntry, ...] = field(default_factory=tuple)
    parse_issues: tuple[ParseIssue, ...] = field(default_factory=tuple)


class RepositoryIndexer:
    """Coordinates scanner and parsers to build a repository index."""

    def __init__(
        self,
        parsers: tuple[RepositoryParser[object], ...] | None = None,
    ) -> None:
        self._feature_parser = FeatureParser()
        self._java_parser = JavaParser()
        self._property_parser = PropertyParser()
        self._text_resource_parser = TextResourceParser()
        self._parsers = parsers or (
            self._feature_parser,
            self._java_parser,
            self._property_parser,
            self._text_resource_parser,
        )

    @property
    def supported_extensions(self) -> set[str]:
        """Return every extension understood by configured parsers."""

        return {
            extension
            for parser in self._parsers
            for extension in parser.supported_extensions
        }

    def build_index(
        self,
        repository_path: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> RepositoryIndex:
        """Scan and parse a repository while retaining non-fatal diagnostics."""

        scanner = RepositoryScanner(self.supported_extensions)
        files = scanner.scan(repository_path, progress_callback=progress_callback)

        features: list[FeatureDocument] = []
        java_classes: list[JavaClass] = []
        properties: list[PropertyEntry] = []
        parse_issues: list[ParseIssue] = []

        parser_by_extension = self._parser_map()
        total_files = len(files)
        last_reported_percent = -1

        for index, repository_file in enumerate(files, start=1):
            if progress_callback and total_files:
                percent = 10 + int((index / total_files) * 70)
                if percent != last_reported_percent or index == total_files:
                    progress_callback(
                        percent,
                        f"Parsing {index}/{total_files}: {repository_file.path.name}",
                    )
                    last_reported_percent = percent

            parser = parser_by_extension.get(repository_file.extension)
            if parser is None:
                parse_issues.append(
                    ParseIssue(
                        file_path=repository_file.path,
                        parser_name="none",
                        message=f"No parser registered for extension {repository_file.extension}",
                        severity="error",
                    )
                )
                continue

            try:
                result = parser.parse(repository_file.path)
            except Exception as exc:  # noqa: BLE001 - one file must not stop whole repository scan
                issue = ParseIssue(
                    file_path=repository_file.path,
                    parser_name=parser.__class__.__name__,
                    message=str(exc) or exc.__class__.__name__,
                    severity="error",
                )
                parse_issues.append(issue)
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
                LOGGER.warning(
                    "Parsed %s with %s warning: %s",
                    repository_file.path,
                    parser.__class__.__name__,
                    warning,
                )

            for item in result.items:
                if isinstance(item, FeatureDocument):
                    features.append(item)
                elif isinstance(item, JavaClass):
                    java_classes.append(item)
                elif isinstance(item, PropertyEntry):
                    properties.append(item)

        if progress_callback:
            errors = sum(issue.severity == "error" for issue in parse_issues)
            warnings = sum(issue.severity == "warning" for issue in parse_issues)
            if errors or warnings:
                progress_callback(
                    80,
                    f"Parsed {total_files} supported files with {errors} error(s) and "
                    f"{warnings} warning(s).",
                )
            else:
                progress_callback(80, f"Parsed all {total_files} supported files successfully.")

        return RepositoryIndex(
            root=repository_path,
            files=files,
            features=tuple(features),
            java_classes=tuple(java_classes),
            properties=tuple(properties),
            parse_issues=tuple(parse_issues),
        )

    def _parser_map(self) -> dict[str, RepositoryParser[object]]:
        parser_by_extension: dict[str, RepositoryParser[object]] = {}
        for parser in self._parsers:
            for extension in parser.supported_extensions:
                parser_by_extension[extension] = parser
        return parser_by_extension
