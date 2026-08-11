"""Conservative repository-health checks built on the ARE relationship graph."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.graph import GraphNode, NodeType, RelationType


class HealthSeverity(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    REVIEW = "Review"


class HealthConfidence(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"


@dataclass(frozen=True, slots=True)
class HealthCheckDefinition:
    check_id: str
    check_name: str
    severity: HealthSeverity
    confidence: HealthConfidence
    explanation: str


@dataclass(frozen=True, slots=True)
class HealthFinding:
    check_id: str
    check_name: str
    severity: HealthSeverity
    confidence: HealthConfidence
    node_id: str
    message: str
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class RepositoryHealthReport:
    findings: tuple[HealthFinding, ...] = tuple()

    @property
    def total(self) -> int:
        return len(self.findings)

    def count_by_check(self) -> dict[str, int]:
        return dict(Counter(finding.check_name for finding in self.findings))

    def count_by_severity(self) -> dict[HealthSeverity, int]:
        return dict(Counter(finding.severity for finding in self.findings))


_UNMATCHED_STEP = HealthCheckDefinition(
    check_id="unmatched_step",
    check_name="Unmatched Gherkin Step",
    severity=HealthSeverity.HIGH,
    confidence=HealthConfidence.HIGH,
    explanation=(
        "Cucumber's official expression matcher evaluated the discovered Step Definitions "
        "and no implementation matched this Gherkin step."
    ),
)
_UNRESOLVED_STEP_MATCH = HealthCheckDefinition(
    check_id="unresolved_step_match",
    check_name="Gherkin Step Matching Unresolved",
    severity=HealthSeverity.REVIEW,
    confidence=HealthConfidence.MEDIUM,
    explanation=(
        "ARE could not fully evaluate at least one candidate Step Definition expression. "
        "This is not treated as an unmatched High-confidence defect."
    ),
)
_AMBIGUOUS_STEP = HealthCheckDefinition(
    check_id="ambiguous_step",
    check_name="Ambiguous Gherkin Step",
    severity=HealthSeverity.HIGH,
    confidence=HealthConfidence.HIGH,
    explanation=(
        "The official Cucumber matcher resolves this Gherkin step to more than one "
        "Step Definition. The competing mappings should be reviewed."
    ),
)
_ORPHAN_STEP_DEFINITION = HealthCheckDefinition(
    check_id="orphan_step_definition",
    check_name="Step Definition With No Known Feature Usage",
    severity=HealthSeverity.MEDIUM,
    confidence=HealthConfidence.MEDIUM,
    explanation=(
        "No parsed Gherkin step currently maps to this Step Definition. "
        "Runtime or custom parameter behavior should still be checked before cleanup."
    ),
)
_UNREFERENCED_PROPERTY = HealthCheckDefinition(
    check_id="unreferenced_property",
    check_name="Property Key With No Known Java Reference",
    severity=HealthSeverity.REVIEW,
    confidence=HealthConfidence.MEDIUM,
    explanation=(
        "No static Java relationship to this property key was resolved. "
        "Dynamic key construction may still use it, so this is a review candidate only."
    ),
)
_METHOD_WITHOUT_CALLER = HealthCheckDefinition(
    check_id="method_without_known_caller",
    check_name="Method With No Known Caller",
    severity=HealthSeverity.REVIEW,
    confidence=HealthConfidence.MEDIUM,
    explanation=(
        "No Eclipse JDT-resolved caller or Step Definition implementation relationship "
        "was found. Reflection, hooks, framework callbacks, or external callers may still use it."
    ),
)


class RepositoryHealthAnalyzer:
    """Run conservative checks and avoid certainty when analysis is unresolved."""

    _METHOD_TYPES = {
        NodeType.JAVA_METHOD,
        NodeType.WRAPPER_METHOD,
    }

    def analyze(self, graph: RepositoryGraph) -> RepositoryHealthReport:
        findings: list[HealthFinding] = []

        for node in graph.nodes:
            if node.type == NodeType.STEP:
                findings.extend(self._check_step(graph, node))
            elif node.type == NodeType.STEP_DEFINITION:
                finding = self._check_orphan_step_definition(graph, node)
                if finding is not None:
                    findings.append(finding)
            elif node.type == NodeType.PROPERTY_KEY:
                finding = self._check_unreferenced_property(graph, node)
                if finding is not None:
                    findings.append(finding)
            elif node.type in self._METHOD_TYPES:
                finding = self._check_method_without_known_caller(graph, node)
                if finding is not None:
                    findings.append(finding)

        severity_order = {
            HealthSeverity.HIGH: 0,
            HealthSeverity.MEDIUM: 1,
            HealthSeverity.REVIEW: 2,
        }
        findings.sort(
            key=lambda finding: (
                severity_order[finding.severity],
                finding.check_name,
                self._node_sort_key(graph, finding.node_id),
            )
        )
        return RepositoryHealthReport(findings=tuple(findings))

    @staticmethod
    def _check_step(graph: RepositoryGraph, node: GraphNode) -> tuple[HealthFinding, ...]:
        matches = tuple(
            edge
            for edge in graph.child_edges(node.id)
            if edge.relation == RelationType.MATCHES_STEP_DEFINITION
        )
        if not matches:
            if node.metadata.get("step_match_status") == "unresolved":
                reason = str(
                    node.metadata.get(
                        "step_match_reason",
                        "At least one candidate expression could not be evaluated.",
                    )
                )
                return (
                    _finding(
                        _UNRESOLVED_STEP_MATCH,
                        node.id,
                        f"Step matching was unresolved: {reason}",
                    ),
                )
            return (
                _finding(
                    _UNMATCHED_STEP,
                    node.id,
                    "No matching Step Definition was found for this Gherkin step.",
                ),
            )
        if len(matches) > 1:
            return (
                _finding(
                    _AMBIGUOUS_STEP,
                    node.id,
                    f"This Gherkin step matches {len(matches)} Step Definitions.",
                ),
            )
        return tuple()

    @staticmethod
    def _check_orphan_step_definition(
        graph: RepositoryGraph,
        node: GraphNode,
    ) -> HealthFinding | None:
        used_by_step = any(
            edge.relation == RelationType.MATCHES_STEP_DEFINITION
            for edge in graph.parent_edges(node.id)
        )
        if used_by_step:
            return None
        return _finding(
            _ORPHAN_STEP_DEFINITION,
            node.id,
            "No parsed Gherkin step currently maps to this Step Definition.",
        )

    @staticmethod
    def _check_unreferenced_property(
        graph: RepositoryGraph,
        node: GraphNode,
    ) -> HealthFinding | None:
        referenced = any(
            edge.relation == RelationType.USES_PROPERTY
            for edge in graph.parent_edges(node.id)
        )
        if referenced:
            return None
        return _finding(
            _UNREFERENCED_PROPERTY,
            node.id,
            "No static Java reference to this property key was resolved.",
        )

    @staticmethod
    def _check_method_without_known_caller(
        graph: RepositoryGraph,
        node: GraphNode,
    ) -> HealthFinding | None:
        if bool(node.metadata.get("is_constructor")):
            return None

        incoming_relations = {edge.relation for edge in graph.parent_edges(node.id)}
        if RelationType.CALLS in incoming_relations or RelationType.IMPLEMENTED_BY in incoming_relations:
            return None
        return _finding(
            _METHOD_WITHOUT_CALLER,
            node.id,
            "No statically resolved caller or Step Definition implementation was found.",
        )

    @staticmethod
    def _node_sort_key(graph: RepositoryGraph, node_id: str) -> tuple[str, int, str]:
        node = graph.get_node(node_id)
        if node is None:
            return ("", 0, node_id)
        return (str(node.file_path or ""), int(node.line or 0), node.name)


def _finding(
    definition: HealthCheckDefinition,
    node_id: str,
    message: str,
) -> HealthFinding:
    return HealthFinding(
        check_id=definition.check_id,
        check_name=definition.check_name,
        severity=definition.severity,
        confidence=definition.confidence,
        node_id=node_id,
        message=message,
        explanation=definition.explanation,
    )
