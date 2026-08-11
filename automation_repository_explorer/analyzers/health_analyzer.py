"""Conservative repository-health checks built on the ARE relationship graph."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.graph import GraphNode, NodeType, RelationType


class HealthSeverity(StrEnum):
    """How urgently a finding should be reviewed."""

    HIGH = "High"
    MEDIUM = "Medium"
    REVIEW = "Review"


class HealthConfidence(StrEnum):
    """Confidence in the static-analysis conclusion."""

    HIGH = "High"
    MEDIUM = "Medium"


@dataclass(frozen=True, slots=True)
class HealthFinding:
    """One evidence-backed repository-health finding."""

    check_id: str
    check_name: str
    severity: HealthSeverity
    confidence: HealthConfidence
    node_id: str
    message: str


@dataclass(frozen=True, slots=True)
class RepositoryHealthReport:
    """Complete health-analysis result for one repository graph."""

    findings: tuple[HealthFinding, ...] = tuple()

    @property
    def total(self) -> int:
        return len(self.findings)

    def count_by_check(self) -> dict[str, int]:
        return dict(Counter(finding.check_name for finding in self.findings))

    def count_by_severity(self) -> dict[HealthSeverity, int]:
        return dict(Counter(finding.severity for finding in self.findings))


class RepositoryHealthAnalyzer:
    """Run deterministic, conservative health checks over a repository graph."""

    _METHOD_TYPES = {
        NodeType.JAVA_METHOD,
        NodeType.PAGE_OBJECT,
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
            return (
                HealthFinding(
                    check_id="unmatched_step",
                    check_name="Unmatched Gherkin Step",
                    severity=HealthSeverity.HIGH,
                    confidence=HealthConfidence.HIGH,
                    node_id=node.id,
                    message="No matching Step Definition was found for this Gherkin step.",
                ),
            )
        if len(matches) > 1:
            return (
                HealthFinding(
                    check_id="ambiguous_step",
                    check_name="Ambiguous Gherkin Step",
                    severity=HealthSeverity.HIGH,
                    confidence=HealthConfidence.HIGH,
                    node_id=node.id,
                    message=(
                        f"This Gherkin step matches {len(matches)} Step Definitions; "
                        "review the competing mappings."
                    ),
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
        return HealthFinding(
            check_id="orphan_step_definition",
            check_name="Step Definition With No Known Feature Usage",
            severity=HealthSeverity.MEDIUM,
            confidence=HealthConfidence.MEDIUM,
            node_id=node.id,
            message=(
                "No parsed Gherkin step currently maps to this Step Definition. "
                "Review before cleanup because runtime/dynamic usage may exist."
            ),
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
        return HealthFinding(
            check_id="unreferenced_property",
            check_name="Property Key With No Known Java Reference",
            severity=HealthSeverity.REVIEW,
            confidence=HealthConfidence.MEDIUM,
            node_id=node.id,
            message=(
                "No static Java reference to this property key was resolved. "
                "Dynamic key construction may still use it."
            ),
        )

    @staticmethod
    def _check_method_without_known_caller(
        graph: RepositoryGraph,
        node: GraphNode,
    ) -> HealthFinding | None:
        incoming_relations = {edge.relation for edge in graph.parent_edges(node.id)}
        if (
            RelationType.CALLS in incoming_relations
            or RelationType.IMPLEMENTED_BY in incoming_relations
        ):
            return None
        return HealthFinding(
            check_id="method_without_known_caller",
            check_name="Method With No Known Caller",
            severity=HealthSeverity.REVIEW,
            confidence=HealthConfidence.MEDIUM,
            node_id=node.id,
            message=(
                "No static caller or Step Definition implementation relationship was resolved. "
                "Framework hooks, inheritance, reflection, or external callers may still use it."
            ),
        )

    @staticmethod
    def _node_sort_key(graph: RepositoryGraph, node_id: str) -> tuple[str, int, str]:
        node = graph.get_node(node_id)
        if node is None:
            return ("", 0, node_id)
        return (
            str(node.file_path or ""),
            int(node.line or 0),
            node.name,
        )
