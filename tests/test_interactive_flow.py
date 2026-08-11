"""Tests for local relationship flow helpers."""

from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.local_graph import build_local_graph_html
from automation_repository_explorer.models.graph import NodeType
from automation_repository_explorer.services.explorer_service import ExplorerService
from automation_repository_explorer.ui.flow_graph import feature_flow_graph, relationship_neighborhood


class InteractiveFlowTests(unittest.TestCase):
    """Validate relationship graph generation without Streamlit."""

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

    def test_relationship_neighborhood_can_render_local_interactive_html(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))
        property_node = next(
            node
            for node in context.graph.nodes
            if node.type == NodeType.PROPERTY_KEY
        )

        nodes, edges = relationship_neighborhood(context, property_node.id)
        rendered = build_local_graph_html(nodes, edges)

        self.assertNotIn("https://", rendered)
        self.assertNotIn("unpkg.com", rendered)
        self.assertIn("<svg", rendered)
        self.assertIn("Full graph: OFF", rendered)
        self.assertIn("function focusedLayout()", rendered)
        self.assertIn("edge.source === currentNodeId", rendered)
        self.assertIn("Edit File", rendered)


if __name__ == "__main__":
    unittest.main()
