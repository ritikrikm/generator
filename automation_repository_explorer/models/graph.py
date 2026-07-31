"""Graph models used to represent repository relationships."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class NodeType(StrEnum):
    """Supported relationship node types."""

    FEATURE = "Feature"
    SCENARIO = "Scenario"
    STEP = "Step"
    STEP_DEFINITION = "Step Definition"
    JAVA_CLASS = "Java Class"
    JAVA_METHOD = "Java Method"
    PAGE_OBJECT = "Page Object"
    WRAPPER_METHOD = "Wrapper Method"
    PROPERTY_KEY = "Property Key"
    XPATH = "XPath"
    EXAMPLE_VALUE = "Example Value"
    STRING_LITERAL = "String Literal"
    FILE = "File"


class RelationType(StrEnum):
    """Relationship edge types."""

    CONTAINS = "contains"
    HAS_STEP = "has_step"
    MATCHES_STEP_DEFINITION = "matches_step_definition"
    IMPLEMENTED_BY = "implemented_by"
    CALLS = "calls"
    USES_PROPERTY = "uses_property"
    RESOLVES_TO = "resolves_to"
    HAS_EXAMPLE_VALUE = "has_example_value"
    BINDS_TO_PARAMETER = "binds_to_parameter"
    DECLARES = "declares"
    REFERENCES_LITERAL = "references_literal"


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node in the repository relationship graph."""

    id: str
    type: NodeType
    name: str
    file_path: Path | None = None
    line: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """A directed relationship between two nodes."""

    source_id: str
    target_id: str
    relation: RelationType
    metadata: dict[str, Any] = field(default_factory=dict)
