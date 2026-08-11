from pathlib import Path

from automation_repository_explorer.analyzers.health_analyzer import RepositoryHealthAnalyzer
from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.graph import GraphNode, NodeType


def test_unresolved_same_name_call_blocks_false_unused_method_finding() -> None:
    graph = RepositoryGraph()
    target = graph.add_node(
        GraphNode(
            id="target",
            type=NodeType.JAVA_METHOD,
            name="Page.save",
            file_path=Path("Page.java"),
            line=10,
            metadata={
                "analysis_backend": "eclipse-jdt",
                "binding_key": "target-binding",
            },
        )
    )
    graph.add_node(
        GraphNode(
            id="caller",
            type=NodeType.JAVA_METHOD,
            name="Steps.run",
            file_path=Path("Steps.java"),
            line=20,
            metadata={
                "analysis_backend": "eclipse-jdt",
                "binding_key": "caller-binding",
                "unresolved_calls": ("page.save",),
            },
        )
    )

    report = RepositoryHealthAnalyzer().analyze(graph)

    assert all(finding.node_id != target.id for finding in report.findings)


def test_jdt_method_without_binding_is_not_called_unused() -> None:
    graph = RepositoryGraph()
    target = graph.add_node(
        GraphNode(
            id="target",
            type=NodeType.JAVA_METHOD,
            name="Page.save",
            file_path=Path("Page.java"),
            line=10,
            metadata={"analysis_backend": "eclipse-jdt", "binding_key": None},
        )
    )

    report = RepositoryHealthAnalyzer().analyze(graph)

    assert all(finding.node_id != target.id for finding in report.findings)
