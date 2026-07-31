"""Tests for interactive flow graph helpers."""

from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.models.graph import NodeType
from automation_repository_explorer.services.explorer_service import ExplorerService
from automation_repository_explorer.ui.flow_graph import feature_flow_graph, relationship_neighborhood
from automation_repository_explorer.ui.interactive_graph import build_interactive_graph_html, _layout_nodes


class InteractiveFlowTests(unittest.TestCase):
    """Validate interactive graph data generation."""

    def test_feature_flow_graph_contains_implementation_and_locator_nodes(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))
        feature = next(node for node in context.graph.nodes if node.type == NodeType.FEATURE)
        scenarios = tuple(
            node
            for node in context.graph.children(feature.id)
            if node.type == NodeType.SCENARIO
        )

        nodes, edges = feature_flow_graph(context, feature, scenarios[:1])
        node_types = {node.type for node in nodes}

        self.assertIn(NodeType.STEP_DEFINITION, node_types)
        self.assertIn(NodeType.PAGE_OBJECT, node_types)
        self.assertIn(NodeType.PROPERTY_KEY, node_types)
        self.assertIn(NodeType.XPATH, node_types)
        self.assertTrue(edges)

    def test_relationship_neighborhood_can_render_interactive_html(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))
        property_node = next(node for node in context.graph.nodes if node.type == NodeType.PROPERTY_KEY)

        nodes, edges = relationship_neighborhood(context, property_node.id)
        rendered = build_interactive_graph_html(nodes, edges)

        self.assertNotIn("https://", rendered)
        self.assertNotIn("unpkg.com", rendered)
        self.assertIn("<svg", rendered)
        self.assertIn("Node Details", rendered)

    def test_interactive_layout_orders_connected_nodes_left_to_right(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))
        feature = next(node for node in context.graph.nodes if node.type == NodeType.FEATURE)
        scenarios = tuple(
            node
            for node in context.graph.children(feature.id)
            if node.type == NodeType.SCENARIO
        )
        nodes, edges = feature_flow_graph(context, feature, scenarios[:1])

        rendered_nodes = _layout_nodes(nodes, edges)
        x_by_id = {str(node["id"]): int(node["x"]) for node in rendered_nodes}

        self.assertTrue(edges)
        self.assertTrue(
            all(x_by_id[edge.source_id] < x_by_id[edge.target_id] for edge in edges)
        )


if __name__ == "__main__":
    unittest.main()
