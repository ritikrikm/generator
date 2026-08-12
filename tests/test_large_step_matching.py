from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.analyzers.optimized_graph_builder import (
    OptimizedRepositoryGraphBuilder,
)
from automation_repository_explorer.analyzers.step_matcher import StepDefinitionMatcher
from automation_repository_explorer.models.domain import (
    FeatureDocument,
    JavaClass,
    JavaMethod,
    Scenario,
    SourceLocation,
    Step,
    StepDefinition,
)
from automation_repository_explorer.models.graph import RelationType
from automation_repository_explorer.services.indexer import RepositoryIndex


class CountingMatcher(StepDefinitionMatcher):
    def __init__(self) -> None:
        self.calls = 0

    def match_result_text(self, step_text: str, method: JavaMethod):
        self.calls += 1
        return super().match_result_text(step_text, method)


class LargeStepMatchingTests(unittest.TestCase):
    def test_repeated_step_text_is_matched_once_then_reused(self) -> None:
        feature_path = Path("features/repeated.feature")
        java_path = Path("steps/LoginSteps.java")

        repeated_text = "the user logs in as admin"
        scenario_one = Scenario(
            name="First",
            keyword="Scenario",
            tags=(),
            location=SourceLocation(feature_path, 2),
            steps=(Step("Given", repeated_text, SourceLocation(feature_path, 3)),),
        )
        scenario_two = Scenario(
            name="Second",
            keyword="Scenario",
            tags=(),
            location=SourceLocation(feature_path, 5),
            steps=(Step("Given", repeated_text, SourceLocation(feature_path, 6)),),
        )
        feature = FeatureDocument(
            name="Repeated",
            location=SourceLocation(feature_path, 1),
            tags=(),
            scenarios=(scenario_one, scenario_two),
        )

        method = JavaMethod(
            name="login",
            return_type="void",
            parameters=(),
            location=SourceLocation(java_path, 10),
            end_line=12,
            body="",
            calls=(),
            string_literals=(),
            step_definition=StepDefinition(
                keyword="Given",
                pattern="the user logs in as {word}",
                location=SourceLocation(java_path, 9),
            ),
        )
        java_class = JavaClass(
            name="LoginSteps",
            package="example.steps",
            imports=(),
            location=SourceLocation(java_path, 1),
            methods=(method,),
        )

        repository_index = RepositoryIndex(
            root=Path("."),
            files=(),
            features=(feature,),
            java_classes=(java_class,),
            properties=(),
        )

        matcher = CountingMatcher()
        graph = OptimizedRepositoryGraphBuilder(step_matcher=matcher).build(repository_index)

        matched_edges = [
            edge
            for edge in graph.edges
            if edge.relation == RelationType.MATCHES_STEP_DEFINITION
        ]
        self.assertEqual(len(matched_edges), 2)
        self.assertEqual(matcher.calls, 1)

    def test_regex_prefix_anchor_is_conservative(self) -> None:
        self.assertEqual(
            StepDefinitionMatcher.anchor_token(r'^the user logs in as "(.*)"$'),
            "user",
        )
        self.assertIsNone(StepDefinitionMatcher.anchor_token(r"^(?:admin|user) logs in$"))


if __name__ == "__main__":
    unittest.main()
