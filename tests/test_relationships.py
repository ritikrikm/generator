from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.models.graph import NodeType
from automation_repository_explorer.search.search_engine import SearchMode
from automation_repository_explorer.services.explorer_service import ExplorerService


class RelationshipTest(unittest.TestCase):
    def test_graph_links_feature_to_xpath_and_reverse(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))

        self.assertEqual(context.summary.features, 1)
        self.assertEqual(context.summary.scenarios, 2)
        self.assertEqual(context.summary.steps, 8)
        self.assertEqual(context.summary.java_classes, 4)
        self.assertGreaterEqual(context.summary.properties, 20)

        xpath_nodes = [
            node
            for node in context.graph.nodes
            if node.type == NodeType.XPATH and "New, Uncalled GIC Maturity Leads" in node.name
        ]
        self.assertTrue(xpath_nodes)

        traversed = context.graph.traverse(xpath_nodes[0].id)
        traversed_types = {node.type for node in traversed}
        self.assertIn(NodeType.PROPERTY_KEY, traversed_types)
        self.assertIn(NodeType.WRAPPER_METHOD, traversed_types)
        self.assertIn(NodeType.PAGE_OBJECT, traversed_types)
        self.assertIn(NodeType.STEP_DEFINITION, traversed_types)
        self.assertIn(NodeType.STEP, traversed_types)
        self.assertIn(NodeType.SCENARIO, traversed_types)
        self.assertIn(NodeType.FEATURE, traversed_types)

    def test_search_finds_property_keys_and_feature_content(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))
        service = ExplorerService()

        property_results = service.search(
            context.graph,
            "MMSRB.Notification.NewUncalledGICMaturityLeads",
            mode=SearchMode.EXACT,
            node_types={NodeType.PROPERTY_KEY},
        )
        self.assertEqual(len(property_results), 1)

        fuzzy_results = service.search(context.graph, "maturty", mode=SearchMode.FUZZY)
        self.assertTrue(any("maturity" in result.node.name.lower() for result in fuzzy_results))

    def test_dynamic_example_values_bind_to_steps(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))

        example_nodes = [
            node
            for node in context.graph.nodes
            if node.type == NodeType.EXAMPLE_VALUE
            and "Notification=MMSRB.Notification.NewUncalledGICMaturityLeads" in node.name
        ]
        self.assertTrue(example_nodes)
        children = context.graph.children(example_nodes[0].id)
        self.assertTrue(any(child.type == NodeType.STEP for child in children))
        self.assertTrue(any(child.type == NodeType.PROPERTY_KEY for child in children))
