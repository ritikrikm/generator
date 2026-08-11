"""Tests for repository search behavior used by the local desktop UI."""

from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.models.graph import NodeType
from automation_repository_explorer.search.search_engine import SearchMode
from automation_repository_explorer.services.explorer_service import ExplorerService


class SearchTests(unittest.TestCase):
    """Validate search without importing any web UI framework."""

    def test_search_returns_results_across_repository_areas(self) -> None:
        service = ExplorerService()
        context = service.explore(Path("sample_repo"))
        results = service.search(
            context.graph,
            "Maturity",
            mode=SearchMode.CASE_INSENSITIVE,
            limit=500,
        )

        self.assertTrue(results)
        suffixes = {
            result.node.file_path.suffix
            for result in results
            if result.node.file_path is not None
        }
        self.assertIn(".feature", suffixes)
        self.assertTrue({".properties", ".java"} & suffixes)

    def test_search_can_filter_to_feature_nodes(self) -> None:
        service = ExplorerService()
        context = service.explore(Path("sample_repo"))
        results = service.search(
            context.graph,
            "Maturity",
            mode=SearchMode.CASE_INSENSITIVE,
            node_types={NodeType.FEATURE, NodeType.SCENARIO, NodeType.STEP},
            limit=500,
        )

        self.assertTrue(results)
        self.assertTrue(
            all(
                result.node.type in {NodeType.FEATURE, NodeType.SCENARIO, NodeType.STEP}
                for result in results
            )
        )


if __name__ == "__main__":
    unittest.main()
