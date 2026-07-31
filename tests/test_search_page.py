"""Tests for Search page filtering helpers."""

from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.search.search_engine import SearchMode
from automation_repository_explorer.services.explorer_service import ExplorerService
from automation_repository_explorer.ui.pages.search import (
    SearchArea,
    _filter_results,
    _group_results,
)


class SearchPageTests(unittest.TestCase):
    """Validate area grouping and file filtering used by the Streamlit search page."""

    def test_search_results_group_by_repository_area(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))
        results = ExplorerService().search(
            context.graph,
            "Maturity",
            mode=SearchMode.CASE_INSENSITIVE,
            limit=500,
        )

        filtered = _filter_results(
            results,
            area=SearchArea.ALL,
            selected_file=None,
            include_examples=False,
        )
        grouped = _group_results(filtered)

        self.assertIn(SearchArea.FEATURE, grouped)
        self.assertIn(SearchArea.PROPERTY, grouped)

    def test_search_results_can_filter_to_feature_files(self) -> None:
        context = ExplorerService().explore(Path("sample_repo"))
        results = ExplorerService().search(
            context.graph,
            "Maturity",
            mode=SearchMode.CASE_INSENSITIVE,
            limit=500,
        )

        filtered = _filter_results(
            results,
            area=SearchArea.FEATURE,
            selected_file=None,
            include_examples=False,
        )

        self.assertTrue(filtered)
        self.assertTrue(
            all(
                result.node.file_path and result.node.file_path.suffix == ".feature"
                for result in filtered
            )
        )


if __name__ == "__main__":
    unittest.main()
