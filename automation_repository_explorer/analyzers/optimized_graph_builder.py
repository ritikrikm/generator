"""Scalable relationship graph builder for large Java/Cucumber repositories."""

from __future__ import annotations

from collections import defaultdict

from automation_repository_explorer.analyzers.graph_builder import (
    ProgressCallback,
    RepositoryGraphBuilder,
)
from automation_repository_explorer.analyzers.step_matcher import StepMatchStatus
from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.domain import JavaClass, JavaMethod, Scenario, Step
from automation_repository_explorer.models.graph import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationType,
)
from automation_repository_explorer.services.indexer import RepositoryIndex

StepDefinitionMethod = tuple[JavaClass, JavaMethod, GraphNode]


class OptimizedRepositoryGraphBuilder(RepositoryGraphBuilder):
    """Graph builder using official Cucumber matching and JDT binding keys."""

    def _add_java_class(
        self,
        graph: RepositoryGraph,
        java_class: JavaClass,
    ) -> GraphNode:
        node = super()._add_java_class(graph, java_class)
        node.metadata["analysis_backend"] = java_class.analysis_backend
        if java_class.binding_key:
            node.metadata["binding_key"] = java_class.binding_key
        return node

    def _add_java_method(
        self,
        graph: RepositoryGraph,
        java_class: JavaClass,
        method: JavaMethod,
        class_node: GraphNode,
    ) -> GraphNode:
        node = super()._add_java_method(graph, java_class, method, class_node)
        node.metadata["is_constructor"] = method.is_constructor
        node.metadata["analysis_backend"] = java_class.analysis_backend
        node.metadata["unresolved_calls"] = method.unresolved_call_expressions
        if method.binding_key:
            node.metadata["binding_key"] = method.binding_key
        return node

    @classmethod
    def _method_node_type(
        cls,
        java_class: JavaClass,
        method: JavaMethod,
    ) -> NodeType:
        if method.is_constructor:
            return NodeType.JAVA_METHOD
        return super()._method_node_type(java_class, method)

    def _link_method_calls(
        self,
        graph: RepositoryGraph,
        java_classes: tuple[JavaClass, ...],
        methods_by_name: dict[str, list[StepDefinitionMethod]],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Prefer Eclipse JDT method/constructor bindings; never guess for JDT code."""

        methods_by_binding: dict[str, GraphNode] = {}
        for methods in methods_by_name.values():
            for _java_class, method, node in methods:
                if method.binding_key:
                    methods_by_binding[method.binding_key] = node

        total_methods = sum(len(java_class.methods) for java_class in java_classes)
        processed = 0

        if progress_callback:
            progress_callback(
                91,
                f"Linking {total_methods} Java methods using Eclipse JDT bindings...",
            )

        for java_class in java_classes:
            for method in java_class.methods:
                source_id = self._method_id(java_class, method)

                if java_class.analysis_backend == "eclipse-jdt":
                    for target_key in method.resolved_call_keys:
                        target_node = methods_by_binding.get(target_key)
                        if target_node is None or target_node.id == source_id:
                            continue
                        graph.add_edge(
                            GraphEdge(
                                source_id,
                                target_node.id,
                                RelationType.CALLS,
                                metadata={
                                    "resolution": "eclipse-jdt-binding",
                                    "binding_key": target_key,
                                },
                            )
                        )
                else:
                    # Compatibility only for externally supplied legacy models. The default
                    # ARE indexer no longer uses the regex Java parser.
                    for call_expression in method.call_expressions or method.calls:
                        receiver, call_name = self._split_call_expression(call_expression)
                        candidates = methods_by_name.get(call_name, [])
                        resolved = self._resolve_call_candidates(
                            java_class=java_class,
                            receiver=receiver,
                            candidates=candidates,
                        )
                        if len(resolved) != 1:
                            continue
                        _target_class, _target_method, target_node = resolved[0]
                        if target_node.id == source_id:
                            continue
                        graph.add_edge(
                            GraphEdge(
                                source_id,
                                target_node.id,
                                RelationType.CALLS,
                                metadata={
                                    "call": call_expression,
                                    "resolution": "legacy-deterministic",
                                },
                            )
                        )

                processed += 1
                if progress_callback and total_methods and (
                    processed == total_methods or processed % max(1, total_methods // 20) == 0
                ):
                    progress_callback(
                        91 + int((processed / total_methods) * 2),
                        f"Linking Java methods {processed}/{total_methods}...",
                    )

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

        if not index.java_analysis_complete:
            for scenario, step in occurrences:
                node = graph.get_node(self._step_id(scenario, step))
                if node is not None:
                    node.metadata["step_match_status"] = "unresolved"
                    node.metadata["step_match_reason"] = (
                        "Eclipse JDT Java analysis did not complete."
                    )
            if progress_callback:
                progress_callback(
                    91,
                    "Cucumber matching unresolved because Java analysis did not complete.",
                )
            return

        if progress_callback:
            progress_callback(
                89,
                f"Preparing {total_steps} Cucumber step occurrences "
                f"({total_unique} unique texts) against "
                f"{len(step_definition_methods)} step definitions...",
            )

        if not occurrences:
            if progress_callback:
                progress_callback(91, "No Cucumber step relationships to resolve.")
            return

        if not step_definition_methods:
            if progress_callback:
                progress_callback(91, "No Java Cucumber Step Definitions were discovered.")
            return

        anchored: dict[str, list[StepDefinitionMethod]] = defaultdict(list)
        fallback: list[StepDefinitionMethod] = []
        for item in step_definition_methods:
            step_definition = item[1].step_definition
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
                f"Indexed {len(step_definition_methods) - len(fallback)} safe anchors; "
                f"{len(fallback)} definitions use full official matching.",
            )

        matches_by_text: dict[str, tuple[StepDefinitionMethod, ...]] = {}
        unresolved_by_text: dict[str, str] = {}
        unique_text_list = tuple(unique_texts)
        last_reported = -1

        for unique_index, step_text in enumerate(unique_text_list, start=1):
            candidate_by_node_id: dict[str, StepDefinitionMethod] = {
                item[2].id: item for item in fallback
            }
            for token in self._step_matcher.text_tokens(step_text):
                for item in anchored.get(token, ()):
                    candidate_by_node_id[item[2].id] = item

            matching: list[StepDefinitionMethod] = []
            unresolved_reasons: list[str] = []
            for item in candidate_by_node_id.values():
                result = self._step_matcher.match_result_text(step_text, item[1])
                if result.status == StepMatchStatus.MATCH:
                    matching.append(item)
                elif result.status == StepMatchStatus.UNRESOLVED:
                    unresolved_reasons.append(result.reason or "Expression unresolved.")

            matches_by_text[step_text] = tuple(matching)
            if unresolved_reasons and not matching:
                unresolved_by_text[step_text] = unresolved_reasons[0]

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
                f"Official Cucumber matching complete; linking {total_steps} occurrences...",
            )

        last_reported = -1
        for occurrence_index, (scenario, step) in enumerate(occurrences, start=1):
            step_node_id = self._step_id(scenario, step)
            matching = matches_by_text.get(step.normalized_text, ())
            for _java_class, method, _method_node in matching:
                step_def_node_id = (
                    f"stepdef:{method.location.file_path}:"
                    f"{method.location.line}:{method.name}"
                )
                graph.add_edge(
                    GraphEdge(
                        step_node_id,
                        step_def_node_id,
                        RelationType.MATCHES_STEP_DEFINITION,
                        metadata={"resolution": "cucumber-expressions"},
                    )
                )

            unresolved_reason = unresolved_by_text.get(step.normalized_text)
            if not matching and unresolved_reason:
                node = graph.get_node(step_node_id)
                if node is not None:
                    node.metadata["step_match_status"] = "unresolved"
                    node.metadata["step_match_reason"] = unresolved_reason

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
