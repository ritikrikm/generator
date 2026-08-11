"""Build repository relationship graph from parsed repository index."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from automation_repository_explorer.analyzers.step_matcher import StepDefinitionMatcher
from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.domain import (
    FeatureDocument,
    JavaClass,
    JavaMethod,
    PropertyEntry,
    Scenario,
    Step,
)
from automation_repository_explorer.models.graph import GraphEdge, GraphNode, NodeType, RelationType
from automation_repository_explorer.services.indexer import RepositoryIndex

ProgressCallback = Callable[[int, str], None]


class RepositoryGraphBuilder:
    """Constructs graph nodes and relationships from a repository index."""

    _PLACEHOLDER_RE = re.compile(r"<(?P<name>[^>]+)>")
    _SELENIUM_IMPORT_PREFIXES = (
        "org.openqa.selenium",
        "org.openqa.selenium.support",
    )
    _SELENIUM_CALL_NAMES = frozenset(
        {
            "findElement",
            "findElements",
            "click",
            "sendKeys",
            "clear",
            "submit",
            "getText",
            "getAttribute",
            "isDisplayed",
            "isEnabled",
            "isSelected",
            "selectByVisibleText",
            "selectByValue",
            "until",
            "navigate",
            "get",
            "switchTo",
        }
    )

    def __init__(self, step_matcher: StepDefinitionMatcher | None = None) -> None:
        self._step_matcher = step_matcher or StepDefinitionMatcher()

    def build(
        self,
        index: RepositoryIndex,
        progress_callback: ProgressCallback | None = None,
    ) -> RepositoryGraph:
        graph = RepositoryGraph()
        methods_by_name: dict[str, list[tuple[JavaClass, JavaMethod, GraphNode]]] = {}
        properties_by_key = {entry.key: entry for entry in index.properties}
        property_nodes: dict[str, GraphNode] = {}

        if progress_callback:
            progress_callback(85, "Building graph: indexing repository files...")

        for repository_file in index.files:
            graph.add_node(
                GraphNode(
                    id=self._file_id(repository_file.path),
                    type=NodeType.FILE,
                    name=repository_file.path.name,
                    file_path=repository_file.path,
                    line=1,
                    metadata={
                        "extension": repository_file.extension,
                        "size_bytes": repository_file.size_bytes,
                    },
                )
            )

        if progress_callback:
            progress_callback(86, "Building graph: adding feature/scenario/step nodes...")
        for feature in index.features:
            self._add_feature(graph, feature)

        if progress_callback:
            progress_callback(87, "Building graph: adding Java classes and methods...")
        for java_class in index.java_classes:
            class_node = self._add_java_class(graph, java_class)
            for method in java_class.methods:
                method_node = self._add_java_method(graph, java_class, method, class_node)
                methods_by_name.setdefault(method.name, []).append((java_class, method, method_node))

        if progress_callback:
            progress_callback(88, "Building graph: adding properties and locators...")
        for entry in index.properties:
            property_node = self._add_property(graph, entry)
            property_nodes[entry.key] = property_node
            self._add_xpath_if_applicable(graph, entry, property_node)

        self._link_steps_to_step_definitions(
            graph,
            index,
            methods_by_name,
            progress_callback=progress_callback,
        )
        self._link_method_calls(
            graph,
            index.java_classes,
            methods_by_name,
            progress_callback=progress_callback,
        )

        if progress_callback:
            progress_callback(93, "Building graph: linking Java methods to property keys...")
        self._link_methods_to_properties(
            graph,
            index.java_classes,
            properties_by_key,
            property_nodes,
        )

        if progress_callback:
            progress_callback(94, "Building graph: linking Scenario Outline examples...")
        self._link_examples(graph, index.features, property_nodes)

        if progress_callback:
            progress_callback(
                95,
                f"Relationship graph built: {len(graph.nodes)} nodes, {len(graph.edges)} edges.",
            )

        return graph

    def _add_feature(self, graph: RepositoryGraph, feature: FeatureDocument) -> GraphNode:
        feature_node = graph.add_node(
            GraphNode(
                id=self._feature_id(feature),
                type=NodeType.FEATURE,
                name=feature.name,
                file_path=feature.location.file_path,
                line=feature.location.line,
                metadata={"tags": feature.tags},
            )
        )
        graph.add_edge(
            GraphEdge(self._file_id(feature.location.file_path), feature_node.id, RelationType.DECLARES)
        )
        for scenario in feature.scenarios:
            scenario_node = self._add_scenario(graph, feature, scenario)
            graph.add_edge(GraphEdge(feature_node.id, scenario_node.id, RelationType.CONTAINS))
            for step in scenario.steps:
                step_node = self._add_step(graph, scenario, step)
                graph.add_edge(GraphEdge(scenario_node.id, step_node.id, RelationType.HAS_STEP))
        return feature_node

    def _add_scenario(
        self,
        graph: RepositoryGraph,
        feature: FeatureDocument,
        scenario: Scenario,
    ) -> GraphNode:
        return graph.add_node(
            GraphNode(
                id=self._scenario_id(feature, scenario),
                type=NodeType.SCENARIO,
                name=scenario.name,
                file_path=scenario.location.file_path,
                line=scenario.location.line,
                metadata={"keyword": scenario.keyword, "tags": scenario.tags},
            )
        )

    def _add_step(self, graph: RepositoryGraph, scenario: Scenario, step: Step) -> GraphNode:
        return graph.add_node(
            GraphNode(
                id=self._step_id(scenario, step),
                type=NodeType.STEP,
                name=f"{step.keyword} {step.text}",
                file_path=step.location.file_path,
                line=step.location.line,
                metadata={"keyword": step.keyword, "text": step.text},
            )
        )

    def _add_java_class(self, graph: RepositoryGraph, java_class: JavaClass) -> GraphNode:
        node = graph.add_node(
            GraphNode(
                id=self._class_id(java_class),
                type=self._class_node_type(java_class),
                name=java_class.qualified_name,
                file_path=java_class.location.file_path,
                line=java_class.location.line,
                metadata={"imports": java_class.imports, "package": java_class.package},
            )
        )
        graph.add_edge(
            GraphEdge(self._file_id(java_class.location.file_path), node.id, RelationType.DECLARES)
        )
        return node

    def _add_java_method(
        self,
        graph: RepositoryGraph,
        java_class: JavaClass,
        method: JavaMethod,
        class_node: GraphNode,
    ) -> GraphNode:
        node_type = self._method_node_type(java_class, method)
        method_node = graph.add_node(
            GraphNode(
                id=self._method_id(java_class, method),
                type=node_type,
                name=f"{java_class.name}.{method.name}",
                file_path=method.location.file_path,
                line=method.location.line,
                metadata={
                    "return_type": method.return_type,
                    "parameters": method.parameters,
                    "calls": method.calls,
                    "call_expressions": method.call_expressions,
                    "string_literals": method.string_literals,
                },
            )
        )
        graph.add_edge(GraphEdge(class_node.id, method_node.id, RelationType.DECLARES))
        if method.step_definition is not None:
            step_def_node = graph.add_node(
                GraphNode(
                    id=f"stepdef:{method.location.file_path}:{method.location.line}:{method.name}",
                    type=NodeType.STEP_DEFINITION,
                    name=f"@{method.step_definition.keyword}(\"{method.step_definition.pattern}\")",
                    file_path=method.step_definition.location.file_path,
                    line=method.step_definition.location.line,
                    metadata={"pattern": method.step_definition.pattern},
                )
            )
            graph.add_edge(GraphEdge(step_def_node.id, method_node.id, RelationType.IMPLEMENTED_BY))
        for literal in method.string_literals:
            literal_node = graph.add_node(
                GraphNode(
                    id=f"literal:{method.location.file_path}:{method.location.line}:{literal}",
                    type=NodeType.STRING_LITERAL,
                    name=literal,
                    file_path=method.location.file_path,
                    line=method.location.line,
                )
            )
            graph.add_edge(GraphEdge(method_node.id, literal_node.id, RelationType.REFERENCES_LITERAL))
        return method_node

    def _add_property(self, graph: RepositoryGraph, entry: PropertyEntry) -> GraphNode:
        node = graph.add_node(
            GraphNode(
                id=f"property:{entry.location.file_path}:{entry.key}",
                type=NodeType.PROPERTY_KEY,
                name=entry.key,
                file_path=entry.location.file_path,
                line=entry.location.line,
                metadata={"value": entry.value},
            )
        )
        graph.add_edge(
            GraphEdge(self._file_id(entry.location.file_path), node.id, RelationType.DECLARES)
        )
        return node

    def _add_xpath_if_applicable(
        self,
        graph: RepositoryGraph,
        entry: PropertyEntry,
        property_node: GraphNode,
    ) -> None:
        if not self._looks_like_xpath(entry.value):
            return
        xpath_node = graph.add_node(
            GraphNode(
                id=f"xpath:{entry.location.file_path}:{entry.key}",
                type=NodeType.XPATH,
                name=entry.value,
                file_path=entry.location.file_path,
                line=entry.location.line,
            )
        )
        graph.add_edge(GraphEdge(property_node.id, xpath_node.id, RelationType.RESOLVES_TO))

    def _link_steps_to_step_definitions(
        self,
        graph: RepositoryGraph,
        index: RepositoryIndex,
        methods_by_name: dict[str, list[tuple[JavaClass, JavaMethod, GraphNode]]],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        step_definition_methods = [
            (java_class, method, node)
            for methods in methods_by_name.values()
            for java_class, method, node in methods
            if method.step_definition is not None
        ]
        total_steps = sum(
            len(scenario.steps)
            for feature in index.features
            for scenario in feature.scenarios
        )
        processed_steps = 0
        last_percent = -1

        if progress_callback:
            progress_callback(
                89,
                f"Matching {total_steps} Cucumber steps to "
                f"{len(step_definition_methods)} step definitions...",
            )

        for feature in index.features:
            for scenario in feature.scenarios:
                for step in scenario.steps:
                    step_node_id = self._step_id(scenario, step)
                    for _java_class, method, method_node in step_definition_methods:
                        if not self._step_matcher.matches(step, method):
                            continue
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
                        graph.add_edge(
                            GraphEdge(
                                step_def_node_id,
                                method_node.id,
                                RelationType.IMPLEMENTED_BY,
                            )
                        )

                    processed_steps += 1
                    if progress_callback and total_steps:
                        percent = 89 + int((processed_steps / total_steps) * 2)
                        if percent != last_percent or processed_steps == total_steps:
                            progress_callback(
                                percent,
                                f"Matching Cucumber steps {processed_steps}/{total_steps}...",
                            )
                            last_percent = percent

    def _link_method_calls(
        self,
        graph: RepositoryGraph,
        java_classes: tuple[JavaClass, ...],
        methods_by_name: dict[str, list[tuple[JavaClass, JavaMethod, GraphNode]]],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Link calls only when static evidence identifies a deterministic target."""

        total_methods = sum(len(java_class.methods) for java_class in java_classes)
        processed_methods = 0
        last_percent = -1

        if progress_callback:
            progress_callback(91, f"Resolving Java calls across {total_methods} methods...")

        for java_class in java_classes:
            for method in java_class.methods:
                source_id = self._method_id(java_class, method)
                call_expressions = method.call_expressions or method.calls
                for call_expression in call_expressions:
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
                            metadata={"call": call_expression, "resolution": "deterministic"},
                        )
                    )

                processed_methods += 1
                if progress_callback and total_methods:
                    percent = 91 + int((processed_methods / total_methods) * 2)
                    if percent != last_percent or processed_methods == total_methods:
                        progress_callback(
                            percent,
                            f"Resolving Java calls {processed_methods}/{total_methods}...",
                        )
                        last_percent = percent

    @classmethod
    def _resolve_call_candidates(
        cls,
        java_class: JavaClass,
        receiver: str | None,
        candidates: list[tuple[JavaClass, JavaMethod, GraphNode]],
    ) -> list[tuple[JavaClass, JavaMethod, GraphNode]]:
        if not candidates:
            return []

        if receiver:
            receiver_tokens = receiver.split(".")
            class_like_tokens = {token for token in receiver_tokens if token[:1].isupper()}
            if class_like_tokens:
                qualified = [
                    candidate
                    for candidate in candidates
                    if candidate[0].name in class_like_tokens
                    or candidate[0].qualified_name in receiver
                ]
                if qualified:
                    return qualified

        if receiver is None:
            same_class = [
                candidate
                for candidate in candidates
                if candidate[0].qualified_name == java_class.qualified_name
            ]
            if same_class:
                return same_class

        if len(candidates) == 1:
            return candidates

        imported_class_names = {
            imported.rsplit(".", 1)[-1]
            for imported in java_class.imports
            if not imported.endswith(".*")
        }
        imported = [candidate for candidate in candidates if candidate[0].name in imported_class_names]
        if len(imported) == 1:
            return imported

        return []

    def _link_methods_to_properties(
        self,
        graph: RepositoryGraph,
        java_classes: tuple[JavaClass, ...],
        properties_by_key: dict[str, PropertyEntry],
        property_nodes: dict[str, GraphNode],
    ) -> None:
        for java_class in java_classes:
            for method in java_class.methods:
                method_node_id = self._method_id(java_class, method)
                for literal in method.string_literals:
                    entry = properties_by_key.get(literal)
                    if entry is None:
                        continue
                    property_node = property_nodes[entry.key]
                    graph.add_edge(
                        GraphEdge(method_node_id, property_node.id, RelationType.USES_PROPERTY)
                    )

    def _link_examples(
        self,
        graph: RepositoryGraph,
        features: tuple[FeatureDocument, ...],
        property_nodes: dict[str, GraphNode],
    ) -> None:
        for feature in features:
            for scenario in feature.scenarios:
                placeholder_names = {
                    match.group("name")
                    for step in scenario.steps
                    for match in self._PLACEHOLDER_RE.finditer(step.text)
                }
                for examples_table in scenario.examples:
                    for row_index, row in enumerate(examples_table.rows, start=1):
                        for column, value in row.items():
                            example_node = graph.add_node(
                                GraphNode(
                                    id=(
                                        f"example:{scenario.location.file_path}:"
                                        f"{scenario.location.line}:{row_index}:{column}:{value}"
                                    ),
                                    type=NodeType.EXAMPLE_VALUE,
                                    name=f"{column}={value}",
                                    file_path=examples_table.location.file_path,
                                    line=examples_table.location.line + row_index,
                                    metadata={"column": column, "value": value},
                                )
                            )
                            scenario_id = self._scenario_id(feature, scenario)
                            graph.add_edge(
                                GraphEdge(
                                    scenario_id,
                                    example_node.id,
                                    RelationType.HAS_EXAMPLE_VALUE,
                                )
                            )
                            if column in placeholder_names:
                                for step in scenario.steps:
                                    if f"<{column}>" in step.text:
                                        graph.add_edge(
                                            GraphEdge(
                                                example_node.id,
                                                self._step_id(scenario, step),
                                                RelationType.BINDS_TO_PARAMETER,
                                                metadata={"column": column, "value": value},
                                            )
                                        )
                            property_node = property_nodes.get(value)
                            if property_node is not None:
                                graph.add_edge(
                                    GraphEdge(
                                        example_node.id,
                                        property_node.id,
                                        RelationType.USES_PROPERTY,
                                        metadata={"source": "examples", "column": column},
                                    )
                                )

    @staticmethod
    def _looks_like_xpath(value: str) -> bool:
        stripped = value.strip()
        return (
            stripped.startswith("//")
            or stripped.startswith("(//")
            or "xpath=" in stripped.lower()
        )

    @classmethod
    def _class_node_type(cls, java_class: JavaClass) -> NodeType:
        if any(method.step_definition is not None for method in java_class.methods):
            return NodeType.JAVA_CLASS

        has_selenium_import = any(
            imported.startswith(cls._SELENIUM_IMPORT_PREFIXES)
            for imported in java_class.imports
        )
        has_ui_calls = any(
            cls._simple_call_name(call) in cls._SELENIUM_CALL_NAMES
            for method in java_class.methods
            for call in (method.call_expressions or method.calls)
        )
        if has_selenium_import or has_ui_calls:
            return NodeType.PAGE_OBJECT
        return NodeType.JAVA_CLASS

    @classmethod
    def _method_node_type(cls, java_class: JavaClass, method: JavaMethod) -> NodeType:
        if method.step_definition is not None:
            return NodeType.JAVA_METHOD

        call_expressions = method.call_expressions or method.calls
        direct_selenium_calls = {
            cls._simple_call_name(call)
            for call in call_expressions
            if cls._simple_call_name(call) in cls._SELENIUM_CALL_NAMES
        }
        if len(direct_selenium_calls) >= 2:
            return NodeType.WRAPPER_METHOD
        if cls._class_node_type(java_class) == NodeType.PAGE_OBJECT:
            return NodeType.PAGE_OBJECT
        return NodeType.JAVA_METHOD

    @staticmethod
    def _split_call_expression(call_expression: str) -> tuple[str | None, str]:
        if "." not in call_expression:
            return None, call_expression
        receiver, name = call_expression.rsplit(".", 1)
        return receiver, name

    @staticmethod
    def _simple_call_name(call_expression: str) -> str:
        return call_expression.rsplit(".", 1)[-1]

    @staticmethod
    def _file_id(path: Path) -> str:
        return f"file:{path}"

    @staticmethod
    def _feature_id(feature: FeatureDocument) -> str:
        return f"feature:{feature.location.file_path}:{feature.location.line}"

    @staticmethod
    def _scenario_id(feature: FeatureDocument, scenario: Scenario) -> str:
        return f"scenario:{feature.location.file_path}:{scenario.location.line}"

    @staticmethod
    def _step_id(scenario: Scenario, step: Step) -> str:
        return f"step:{scenario.location.file_path}:{scenario.location.line}:{step.location.line}"

    @staticmethod
    def _class_id(java_class: JavaClass) -> str:
        return f"class:{java_class.qualified_name}:{java_class.location.file_path}"

    @staticmethod
    def _method_id(java_class: JavaClass, method: JavaMethod) -> str:
        return (
            f"method:{java_class.qualified_name}.{method.name}:"
            f"{method.location.file_path}:{method.location.line}"
        )
