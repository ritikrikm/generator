"""Tests for complete progressive project-flow navigation."""

from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.local_project_flow import build_local_project_flow_html
from automation_repository_explorer.project_flow import build_project_flow_model
from automation_repository_explorer.services.explorer_service import ExplorerService


class ProjectFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ExplorerService().explore(Path("sample_repo"))
        self.model = build_project_flow_model(self.context)

    def test_project_root_exposes_file_categories(self) -> None:
        category_names = {node.name for node in self.model.children(self.model.root_id)}
        self.assertIn("Feature Files", category_names)
        self.assertIn("Java Files", category_names)
        self.assertIn("Property Files", category_names)

    def test_feature_file_drills_into_feature_scenario_and_step(self) -> None:
        feature_file = self._first_file_under_category("Feature Files")
        feature = next(node for node in self.model.children(feature_file.id) if node.kind == "Feature")
        scenario = next(node for node in self.model.children(feature.id) if node.kind == "Scenario")
        step = next(node for node in self.model.children(scenario.id) if node.kind == "Step")
        self.assertTrue(step.name)

    def test_property_file_can_reach_xpath(self) -> None:
        category = next(
            node for node in self.model.children(self.model.root_id) if node.name == "Property Files"
        )
        queue = list(self.model.children(category.id))
        visited: set[str] = set()
        found_xpath = False
        while queue and not found_xpath:
            node = queue.pop(0)
            if node.id in visited:
                continue
            visited.add(node.id)
            children = self.model.children(node.id)
            if node.kind == "Property Key" and any(child.kind == "XPath" for child in children):
                found_xpath = True
                break
            queue.extend(children)
        self.assertTrue(found_xpath)

    def test_project_flow_html_is_local_progressive_and_paged(self) -> None:
        rendered = build_local_project_flow_html(self.model)
        self.assertNotIn("https://", rendered)
        self.assertIn("Project Home", rendered)
        self.assertIn("Previous cards", rendered)
        self.assertIn("Next cards", rendered)
        self.assertIn("PAGE_SIZE = 24", rendered)
        self.assertIn("Edit File", rendered)

    def _first_file_under_category(self, category_name: str):
        category = next(
            node for node in self.model.children(self.model.root_id) if node.name == category_name
        )
        queue = list(self.model.children(category.id))
        visited: set[str] = set()
        while queue:
            node = queue.pop(0)
            if node.id in visited:
                continue
            visited.add(node.id)
            if node.kind == "File":
                return node
            queue.extend(self.model.children(node.id))
        self.fail(f"No file found under {category_name}")


if __name__ == "__main__":
    unittest.main()
