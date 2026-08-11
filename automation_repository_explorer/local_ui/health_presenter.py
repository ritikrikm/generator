"""Grouping, filtering, and paging for repository-health findings."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from automation_repository_explorer.analyzers.health_analyzer import (
    HealthFinding,
    HealthSeverity,
    RepositoryHealthReport,
)
from automation_repository_explorer.graph.repository_graph import RepositoryGraph

DEFAULT_HEALTH_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class HealthFindingCard:
    id: str
    node_id: str
    confidence: str
    node_type: str
    name: str
    location: str
    message: str


@dataclass(frozen=True, slots=True)
class HealthIssueGroup:
    id: str
    check_name: str
    severity: HealthSeverity
    description: str
    findings: tuple[HealthFinding, ...]

    @property
    def count(self) -> int:
        return len(self.findings)


@dataclass(frozen=True, slots=True)
class HealthFindingPage:
    group: HealthIssueGroup
    page_index: int
    page_count: int
    total: int
    cards: tuple[HealthFindingCard, ...]

    @property
    def can_previous(self) -> bool:
        return self.page_index > 0

    @property
    def can_next(self) -> bool:
        return self.page_index + 1 < self.page_count


def group_health_findings(
    report: RepositoryHealthReport,
    *,
    severity: HealthSeverity | None = None,
) -> tuple[HealthIssueGroup, ...]:
    """Group findings by check within an optional severity filter."""

    grouped: dict[tuple[HealthSeverity, str, str], list[HealthFinding]] = defaultdict(list)
    for finding in report.findings:
        if severity is not None and finding.severity != severity:
            continue
        grouped[(finding.severity, finding.check_id, finding.check_name)].append(finding)

    groups = [
        HealthIssueGroup(
            id=f"{group_severity.value}:{check_id}",
            check_name=check_name,
            severity=group_severity,
            description=findings[0].message if findings else "",
            findings=tuple(findings),
        )
        for (group_severity, check_id, check_name), findings in grouped.items()
    ]
    severity_order = {item: index for index, item in enumerate(HealthSeverity)}
    groups.sort(key=lambda group: (severity_order[group.severity], group.check_name))
    return tuple(groups)


def severity_counts(report: RepositoryHealthReport) -> dict[HealthSeverity, int]:
    counts = report.count_by_severity()
    return {severity: counts.get(severity, 0) for severity in HealthSeverity}


def page_health_group(
    group: HealthIssueGroup,
    graph: RepositoryGraph,
    *,
    page_index: int = 0,
    page_size: int = DEFAULT_HEALTH_PAGE_SIZE,
    path_formatter: Callable[[Path], str] = str,
) -> HealthFindingPage:
    """Convert one grouped check into a bounded page of detailed finding cards."""

    safe_page_size = max(1, int(page_size))
    total = group.count
    page_count = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = min(max(0, int(page_index)), page_count - 1)
    start = safe_page * safe_page_size
    selected = group.findings[start : start + safe_page_size]

    cards: list[HealthFindingCard] = []
    for offset, finding in enumerate(selected, start=start):
        node = graph.get_node(finding.node_id)
        if node is None:
            continue
        location = ""
        if node.file_path is not None:
            location = path_formatter(node.file_path)
            if node.line:
                location = f"{location}:{node.line}"
        cards.append(
            HealthFindingCard(
                id=f"{group.id}:{offset}:{node.id}",
                node_id=node.id,
                confidence=finding.confidence.value,
                node_type=node.type.value,
                name=node.name,
                location=location,
                message=finding.message,
            )
        )

    return HealthFindingPage(
        group=group,
        page_index=safe_page,
        page_count=page_count,
        total=total,
        cards=tuple(cards),
    )
