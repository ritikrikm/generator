"""Scalable relationship graph builder for large Java/Cucumber repositories."""

from __future__ import annotations

from collections import defaultdict

from automation_repository_explorer.analyzers.graph_builder import (
    ProgressCallback,
    RepositoryGraphBuilder,
)
from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.domain import JavaClass, JavaMethod, Scenario, Step
from automation_repository_explorer.models.graph import GraphEdge, GraphNode, RelationType
from automation_repository_explorer.services.indexer import RepositoryIndex

StepDefinitionMethod = tuple[JavaClass, JavaMethod, GraphNode]


class OptimizedRepositoryGraphBuilder(RepositoryGraphBuilder):
    """RepositoryGraphBuilder with scalable Cucumber step matching.

    The original graph semantics are preserved. The optimization is entirely in candidate
    selection and reuse:

    * identical step text is matched once and reused across all occurrences;
    * step definitions with a guaranteed literal anchor are indexed by that token;
    * regex/Cucumber patterns that cannot be narrowed safely remain in an always-checked
      fallback bucket;
    * final acceptance still goes through StepDefinitionMatcher, so candidate narrowing never
      replaces the real Cucumber/regex match.
    """

    def _link_steps_to_step_definitions(
        self,
        graph: RepositoryGraph,
        index: RepositoryIndex,
        methods_by_name: dict[str, list[StepDefinitionMethod]],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        step_definition_methods: tuple[StepDefinitionMethod, ...] = tuple(
            (java_class, method, node)
            for methods in methods_by_name.values()
            for java_class, method, node in methods
            if method.step_definition is not None
        )

        occurrences: list[tuple[Scenario, Step]] = []
        unique_texts: dict[str, None] = {}
        for feature in index.features:
            for scenario in feature.scenarios:
                for step in scenario.steps:
                    occurrences.append((scenario, step))
                    unique_texts.setdefault(step.normalized_text, None)

        total_steps = len(occurrences)
        total_unique = len(unique_texts)

        if progress_callback:
            progress_callback(
                89,
                f"Preparing {total_steps} Cucumber step occurrences "
                f"({total_unique} unique texts) against "
                f"{len(step_definition_methods)} step definitions...",
            )

        if not occurrences or not step_definition_methods:
            if progress_callback:
                progress_callback(91, "No Cucumber step relationships to resolve.")
            return

        anchored: dict[str, list[StepDefinitionMethod]] = defaultdict(list)
        fallback: list[StepDefinitionMethod] = []
        for item in step_definition_methods:
            method = item[1]
            step_definition = method.step_definition
            if step_definition is None:
                continue
            anchor = self._step_matcher.anchor_token(step_definition.pattern)
            if anchor is None:
                fallback.append(item)
            else:
                anchored[anchor].append(item)

        if progress_callback:
            progress_callback(
                89,
                f"Indexed {len(step_definition_methods) - len(fallback)} anchored step definitions; "
                f"{len(fallback)} require fallback matching.",
            )

        matches_by_text: dict[str, tuple[StepDefinitionMethod, ...]] = {}
        unique_text_list = tuple(unique_texts)
        last_reported = -1

        for unique_index, step_text in enumerate(unique_text_list, start=1):
            candidate_by_node_id: dict[str, StepDefinitionMethod] = {
                item[2].id: item for item in fallback
            }
            for token in self._step_matcher.text_tokens(step_text):
                for item in anchored.get(token, ()):  # guaranteed literal candidate
                    candidate_by_node_id[item[2].id] = item

            matching = tuple(
                item
                for item in candidate_by_node_id.values()
                if self._step_matcher.matches_text(step_text, item[1])
            )
            matches_by_text[step_text] = matching

            if progress_callback and total_unique:
                bucket = int((unique_index / total_unique) * 100)
                if bucket != last_reported and (bucket % 5 == 0 or unique_index == total_unique):
                    progress_callback(
                        89,
                        f"Matching unique Cucumber steps {unique_index}/{total_unique} "
                        f"({total_steps} total occurrences)...",
                    )
                    last_reported = bucket

        if progress_callback:
            progress_callback(
                90,
                f"Unique Cucumber matching complete; linking {total_steps} step occurrences...",
            )

        last_reported = -1
        for occurrence_index, (scenario, step) in enumerate(occurrences, start=1):
            step_node_id = self._step_id(scenario, step)
            for _java_class, method, _method_node in matches_by_text.get(
                step.normalized_text,
                (),
            ):
                step_def_node_id = (
                    f"stepdef:{method.location.file_path}:"
                    f"{method.location.line}:{method.name}"
                )
                graph.add_edge(
                    GraphEdge(
                        step_node_id,
                        step_def_node_id,
                        RelationType.MATCHES_STEP_DEFINITION,
                    )
                )
                # STEP_DEFINITION -> METHOD (IMPLEMENTED_BY) was already created when Java
                # methods were added to the graph. Do not re-add it for every feature occurrence.

            if progress_callback and total_steps:
                bucket = int((occurrence_index / total_steps) * 100)
                if bucket != last_reported and (bucket % 5 == 0 or occurrence_index == total_steps):
                    progress_callback(
                        90 + (1 if bucket >= 50 else 0),
                        f"Linking Cucumber step occurrences {occurrence_index}/{total_steps}...",
                    )
                    last_reported = bucket

        if progress_callback:
            progress_callback(
                91,
                f"Cucumber relationships linked: {total_steps} occurrences, "
                f"{total_unique} unique step texts.",
            )
