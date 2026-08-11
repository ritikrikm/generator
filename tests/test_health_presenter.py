"""Tests for grouped, filterable, paged repository-health presentation."""

from pathlib import Path

from automation_repository_explorer.analyzers.health_analyzer import (
    HealthConfidence,
    HealthFinding,
    HealthSeverity,
    RepositoryHealthReport,
)
from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.local_ui.health_presenter import (
    DEFAULT_HEALTH_PAGE_SIZE,
    group_health_findings,
    page_health_group,
)
from automation_repository_explorer.models.graph import GraphNode, NodeType


def _graph_with_nodes(count: int) -> RepositoryGraph:
    graph = RepositoryGraph()
    for index in range(count):
        graph.add_node(
            GraphNode(
                id=f"step:{index}",
                type=NodeType.STEP,
                name=f"Step {index}",
                file_path=Path("features/example.feature"),
                line=index + 1,
            )
        )
    return graph


def test_health_findings_group_by_check_within_selected_severity() -> None:
    report = RepositoryHealthReport(
        findings=(
            HealthFinding(
                check_id="unmatched",
                check_name="Unmatched Step",
                severity=HealthSeverity.HIGH,
                confidence=HealthConfidence.HIGH,
                node_id="step:0",
                message="No match.",
            ),
            HealthFinding(
                check_id="unmatched",
                check_name="Unmatched Step",
                severity=HealthSeverity.HIGH,
                confidence=HealthConfidence.HIGH,
                node_id="step:1",
                message="No match.",
            ),
            HealthFinding(
                check_id="review",
                check_name="Needs Review",
                severity=HealthSeverity.REVIEW,
                confidence=HealthConfidence.MEDIUM,
                node_id="step:2",
                message="Review it.",
            ),
        )
    )

    high_groups = group_health_findings(report, severity=HealthSeverity.HIGH)
    assert len(high_groups) == 1
    assert high_groups[0].count == 2
    assert high_groups[0].check_name == "Unmatched Step"


def test_one_hundred_findings_render_on_one_health_page() -> None:
    graph = _graph_with_nodes(DEFAULT_HEALTH_PAGE_SIZE)
    findings = tuple(
        HealthFinding(
            check_id="unmatched",
            check_name="Unmatched Step",
            severity=HealthSeverity.HIGH,
            confidence=HealthConfidence.HIGH,
            node_id=f"step:{index}",
            message="No match.",
        )
        for index in range(DEFAULT_HEALTH_PAGE_SIZE)
    )
    group = group_health_findings(RepositoryHealthReport(findings=findings))[0]
    page = page_health_group(group, graph)

    assert len(page.cards) == DEFAULT_HEALTH_PAGE_SIZE
    assert page.page_count == 1
    assert page.can_previous is False
    assert page.can_next is False


def test_health_pages_are_bounded_for_large_groups() -> None:
    total = DEFAULT_HEALTH_PAGE_SIZE + 7
    graph = _graph_with_nodes(total)
    findings = tuple(
        HealthFinding(
            check_id="unmatched",
            check_name="Unmatched Step",
            severity=HealthSeverity.HIGH,
            confidence=HealthConfidence.HIGH,
            node_id=f"step:{index}",
            message="No match.",
        )
        for index in range(total)
    )
    group = group_health_findings(RepositoryHealthReport(findings=findings))[0]

    first = page_health_group(group, graph, page_index=0)
    second = page_health_group(group, graph, page_index=1)
    assert len(first.cards) == DEFAULT_HEALTH_PAGE_SIZE
    assert first.can_next is True
    assert len(second.cards) == 7
    assert second.can_previous is True
