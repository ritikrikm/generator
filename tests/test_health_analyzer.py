"""Tests for conservative repository-health analysis."""

from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.analyzers.health_analyzer import (
    HealthConfidence,
    HealthSeverity,
    RepositoryHealthAnalyzer,
)
from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.graph import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationType,
)


class RepositoryHealthAnalyzerTests(unittest.TestCase):
    def test_health_checks_use_relationship_evidence(self) -> None:
        graph = RepositoryGraph()

        unmatched = GraphNode(
            id="step:unmatched",
            type=NodeType.STEP,
            name="When unmatched",
            file_path=Path("sample.feature"),
            line=10,
        )
        ambiguous = GraphNode(
            id="step:ambiguous",
            type=NodeType.STEP,
            name="When ambiguous",
            file_path=Path("sample.feature"),
            line=20,
        )
        step_def_one = GraphNode(
            id="stepdef:one",
            type=NodeType.STEP_DEFINITION,
            name='@When("one")',
            file_path=Path("Steps.java"),
            line=10,
        )
        step_def_two = GraphNode(
            id="stepdef:two",
            type=NodeType.STEP_DEFINITION,
            name='@When("two")',
            file_path=Path("Steps.java"),
            line=20,
        )
        orphan_step_def = GraphNode(
            id="stepdef:orphan",
            type=NodeType.STEP_DEFINITION,
            name='@When("orphan")',
            file_path=Path("Steps.java"),
            line=30,
        )
        used_method = GraphNode(
            id="method:used",
            type=NodeType.JAVA_METHOD,
            name="Steps.used",
            file_path=Path("Steps.java"),
            line=11,
        )
        orphan_method = GraphNode(
            id="method:orphan",
            type=NodeType.JAVA_METHOD,
            name="Helpers.orphan",
            file_path=Path("Helpers.java"),
            line=15,
        )
        used_property = GraphNode(
            id="property:used",
            type=NodeType.PROPERTY_KEY,
            name="Button.Submit",
            file_path=Path("objects.properties"),
            line=1,
        )
        unused_property = GraphNode(
            id="property:unused",
            type=NodeType.PROPERTY_KEY,
            name="Button.Old",
            file_path=Path("objects.properties"),
            line=2,
        )

        for node in (
            unmatched,
            ambiguous,
            step_def_one,
            step_def_two,
            orphan_step_def,
            used_method,
            orphan_method,
            used_property,
            unused_property,
        ):
            graph.add_node(node)

        graph.add_edge(
            GraphEdge(
                ambiguous.id,
                step_def_one.id,
                RelationType.MATCHES_STEP_DEFINITION,
            )
        )
        graph.add_edge(
            GraphEdge(
                ambiguous.id,
                step_def_two.id,
                RelationType.MATCHES_STEP_DEFINITION,
            )
        )
        graph.add_edge(
            GraphEdge(
                step_def_one.id,
                used_method.id,
                RelationType.IMPLEMENTED_BY,
            )
        )
        graph.add_edge(
            GraphEdge(
                used_method.id,
                used_property.id,
                RelationType.USES_PROPERTY,
            )
        )

        report = RepositoryHealthAnalyzer().analyze(graph)
        by_check = report.count_by_check()

        self.assertEqual(by_check["Unmatched Gherkin Step"], 1)
        self.assertEqual(by_check["Ambiguous Gherkin Step"], 1)
        self.assertEqual(
            by_check["Step Definition With No Known Feature Usage"],
            1,
        )
        self.assertEqual(
            by_check["Property Key With No Known Java Reference"],
            1,
        )
        self.assertEqual(by_check["Method With No Known Caller"], 1)

        unmatched_finding = next(
            finding
            for finding in report.findings
            if finding.check_id == "unmatched_step"
        )
        self.assertEqual(unmatched_finding.severity, HealthSeverity.HIGH)
        self.assertEqual(unmatched_finding.confidence, HealthConfidence.HIGH)

        review_ids = {
            finding.node_id
            for finding in report.findings
            if finding.severity == HealthSeverity.REVIEW
        }
        self.assertIn(orphan_method.id, review_ids)
        self.assertIn(unused_property.id, review_ids)
        self.assertNotIn(used_method.id, review_ids)
        self.assertNotIn(used_property.id, review_ids)

    def test_page_object_is_not_checked_as_method_without_caller(self) -> None:
        graph = RepositoryGraph()
        page_object = GraphNode(
            id="page:MMSRBClientPortfolioListViewPage",
            type=NodeType.PAGE_OBJECT,
            name="MMSRBClientPortfolioListViewPage",
            file_path=Path("MMSRBClientPortfolioListViewPage.java"),
            line=20,
        )
        orphan_java_method = GraphNode(
            id="method:orphan-java",
            type=NodeType.JAVA_METHOD,
            name="Helpers.orphanJavaMethod",
            file_path=Path("Helpers.java"),
            line=10,
        )
        orphan_wrapper_method = GraphNode(
            id="wrapper:orphan",
            type=NodeType.WRAPPER_METHOD,
            name="Wrapper.orphanWrapperMethod",
            file_path=Path("Wrapper.java"),
            line=15,
        )

        for node in (page_object, orphan_java_method, orphan_wrapper_method):
            graph.add_node(node)

        report = RepositoryHealthAnalyzer().analyze(graph)
        method_findings = {
            finding.node_id
            for finding in report.findings
            if finding.check_id == "method_without_known_caller"
        }

        self.assertNotIn(page_object.id, method_findings)
        self.assertIn(orphan_java_method.id, method_findings)
        self.assertIn(orphan_wrapper_method.id, method_findings)


if __name__ == "__main__":
    unittest.main()
