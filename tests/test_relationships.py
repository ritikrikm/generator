from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation_repository_explorer.analyzers.graph_builder import RepositoryGraphBuilder
from automation_repository_explorer.models.graph import RelationType
from automation_repository_explorer.services.indexer import RepositoryIndexer


class RelationshipTest(unittest.TestCase):
    def test_builds_feature_to_step_definition_and_property_relationships(self) -> None:
        root = Path("sample_repo/huntress_MMSRB")
        index = RepositoryIndexer().build_index(root)
        graph = RepositoryGraphBuilder().build(index)

        relations = {edge.relation for edge in graph.edges}
        self.assertIn(RelationType.MATCHES_STEP_DEFINITION, relations)
        self.assertIn(RelationType.IMPLEMENTED_BY, relations)
        self.assertIn(RelationType.USES_PROPERTY, relations)

    def test_resolves_unique_and_class_qualified_calls_without_folder_conventions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = root / "odd" / "layout"
            code.mkdir(parents=True)
            (code / "Caller.java").write_text(
                """
                package arbitrary;
                class Caller {
                    public void run() {
                        Target.openLead();
                    }
                }
                """,
                encoding="utf-8",
            )
            (code / "Target.java").write_text(
                """
                package arbitrary;
                class Target {
                    public static void openLead() {}
                }
                """,
                encoding="utf-8",
            )

            index = RepositoryIndexer().build_index(root)
            graph = RepositoryGraphBuilder().build(index)

        call_edges = [edge for edge in graph.edges if edge.relation == RelationType.CALLS]
        self.assertEqual(len(call_edges), 1)
        self.assertEqual(call_edges[0].metadata.get("call"), "Target.openLead")

    def test_does_not_create_false_edges_for_ambiguous_same_named_methods(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("First", "Second"):
                (root / f"{name}.java").write_text(
                    f"class {name} {{ public void click() {{}} }}",
                    encoding="utf-8",
                )
            (root / "Caller.java").write_text(
                "class Caller { public void run() { helper.click(); } }",
                encoding="utf-8",
            )

            index = RepositoryIndexer().build_index(root)
            graph = RepositoryGraphBuilder().build(index)

        call_edges = [edge for edge in graph.edges if edge.relation == RelationType.CALLS]
        self.assertEqual(call_edges, [])
