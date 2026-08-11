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
        return f"{self.file_path}:{self.line}:{self.column}"


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    path: Path
    extension: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ExamplesTable:
    headers: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    tags: tuple[str, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Step:
    keyword: str
    text: str
    location: SourceLocation

    @property
    def normalized_text(self) -> str:
        return self.text.strip()


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    keyword: str
    tags: tuple[str, ...]
    location: SourceLocation
    steps: tuple[Step, ...] = field(default_factory=tuple)
    examples: tuple[ExamplesTable, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FeatureDocument:
    name: str
    location: SourceLocation
    tags: tuple[str, ...]
    scenarios: tuple[Scenario, ...]


@dataclass(frozen=True, slots=True)
class StepDefinition:
    keyword: str
    pattern: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class JavaMethod:
    """A Java method or constructor discovered by the configured Java analyzer."""

    name: str
    return_type: str
    parameters: tuple[str, ...]
    location: SourceLocation
    end_line: int
    body: str
    calls: tuple[str, ...]
    string_literals: tuple[str, ...]
    step_definition: StepDefinition | None = None
    call_expressions: tuple[str, ...] = field(default_factory=tuple)
    is_constructor: bool = False
    binding_key: str | None = None
    resolved_call_keys: tuple[str, ...] = field(default_factory=tuple)
    unresolved_call_expressions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def qualified_name(self) -> str:
        return f"{self.location.file_path.name}::{self.name}"


@dataclass(frozen=True, slots=True)
class JavaClass:
    """A Java class/interface/enum/record and its analyzed members."""

    name: str
    package: str
    imports: tuple[str, ...]
    location: SourceLocation
    methods: tuple[JavaMethod, ...]
    binding_key: str | None = None
    analysis_backend: str = "legacy"

    @property
    def qualified_name(self) -> str:
        return f"{self.package}.{self.name}" if self.package else self.name


@dataclass(frozen=True, slots=True)
class PropertyEntry:
    key: str
    value: str
    location: SourceLocation
