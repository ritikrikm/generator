"""Domain entities discovered from automation repositories."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A source position in a repository file."""

    file_path: Path
    line: int
    column: int = 1

    def display(self) -> str:
        """Return a human-readable location."""

        return f"{self.file_path}:{self.line}:{self.column}"


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    """Metadata for a supported file found during scanning."""

    path: Path
    extension: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ExamplesTable:
    """A Cucumber Examples table."""

    headers: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    tags: tuple[str, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Step:
    """A Cucumber step."""

    keyword: str
    text: str
    location: SourceLocation

    @property
    def normalized_text(self) -> str:
        """Return step text without its Gherkin keyword."""

        return self.text.strip()


@dataclass(frozen=True, slots=True)
class Scenario:
    """A Cucumber Scenario or Scenario Outline."""

    name: str
    keyword: str
    tags: tuple[str, ...]
    location: SourceLocation
    steps: tuple[Step, ...] = field(default_factory=tuple)
    examples: tuple[ExamplesTable, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FeatureDocument:
    """Parsed representation of a .feature file."""

    name: str
    location: SourceLocation
    tags: tuple[str, ...]
    scenarios: tuple[Scenario, ...]


@dataclass(frozen=True, slots=True)
class StepDefinition:
    """A Java Cucumber step definition annotation."""

    keyword: str
    pattern: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class JavaMethod:
    """A Java method discovered from a class."""

    name: str
    return_type: str
    parameters: tuple[str, ...]
    location: SourceLocation
    end_line: int
    body: str
    calls: tuple[str, ...]
    string_literals: tuple[str, ...]
    step_definition: StepDefinition | None = None

    @property
    def qualified_name(self) -> str:
        """Return a readable method identifier."""

        return f"{self.location.file_path.name}::{self.name}"


@dataclass(frozen=True, slots=True)
class JavaClass:
    """A Java class and its parsed methods."""

    name: str
    package: str
    imports: tuple[str, ...]
    location: SourceLocation
    methods: tuple[JavaMethod, ...]

    @property
    def qualified_name(self) -> str:
        """Return package-qualified class name when package exists."""

        return f"{self.package}.{self.name}" if self.package else self.name


@dataclass(frozen=True, slots=True)
class PropertyEntry:
    """A key/value property entry."""

    key: str
    value: str
    location: SourceLocation
