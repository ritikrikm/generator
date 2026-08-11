"""Tests for understandable incoming/outgoing relationship presentation."""

from pathlib import Path

from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.local_ui.relationship_presenter import build_relationship_view
from automation_repository_explorer.models.graph import GraphEdge, GraphNode, NodeType, RelationType


def test_relationship_view_keeps_incoming_and_outgoing_directions_clear() -> None:
    graph = RepositoryGraph()
    parent = GraphNode("feature", NodeType.FEATURE, "Feature", Path("a.feature"), 1)
    current = GraphNode("scenario", NodeType.SCENARIO, "Scenario", Path("a.feature"), 2)
    child = GraphNode("step", NodeType.STEP, "Given something", Path("a.feature"), 3)
    for node in (parent, current, child):
        graph.add_node(node)
    graph.add_edge(GraphEdge(parent.id, current.id, RelationType.CONTAINS))
    graph.add_edge(GraphEdge(current.id, child.id, RelationType.HAS_STEP))

    view = build_relationship_view(graph, current.id)
    assert view is not None
    assert [card.node_id for card in view.incoming] == ["feature"]
    assert [card.node_id for card in view.outgoing] == ["step"]
    assert view.incoming[0].relation == RelationType.CONTAINS.value
    assert view.outgoing[0].relation == RelationType.HAS_STEP.value
