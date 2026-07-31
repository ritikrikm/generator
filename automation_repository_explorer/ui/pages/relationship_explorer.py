"""Relationship explorer page."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import streamlit as st

from automation_repository_explorer.models.graph import GraphEdge, GraphNode, NodeType, RelationType
from automation_repository_explorer.services.explorer_service import ExplorationContext
from automation_repository_explorer.ui.components import node_label, node_table_rows
from automation_repository_explorer.ui.flow_graph import feature_flow_graph, relationship_neighborhood
from automation_repository_explorer.ui.interactive_graph import render_interactive_graph
from automation_repository_explorer.ui.state import get_context

IMPLEMENTATION_NODE_TYPES = {
    NodeType.JAVA_METHOD,
    NodeType.PAGE_OBJECT,
    NodeType.WRAPPER_METHOD,
}


def render_relationship_explorer() -> None:
    """Render relationship explorer page."""

    st.subheader("Relationship Explorer")
    context = get_context()
    if context is None:
        st.warning("Scan a repository first.")
        return

    st.caption(
        "Select one indexed file, then inspect how its feature, scenarios, steps, Java code, "
        "properties, and XPath locators connect."
    )

    selected_file = _render_file_selector(context)
    file_nodes = _nodes_for_file(context, selected_file)
    feature_nodes = tuple(node for node in file_nodes if node.type == NodeType.FEATURE)

    if feature_nodes:
        _render_feature_file_flow(context, selected_file, feature_nodes)
    else:
        _render_non_feature_file_flow(context, selected_file, file_nodes)


def _render_file_selector(context: ExplorationContext) -> Path:
    file_options = {
        _relative_path(context, repository_file.path): repository_file.path
        for repository_file in sorted(context.index.files, key=lambda item: str(item.path))
    }
    selected_label = st.selectbox("File", list(file_options))
    return file_options[selected_label]


def _render_feature_file_flow(
    context: ExplorationContext,
    selected_file: Path,
    feature_nodes: tuple[GraphNode, ...],
) -> None:
    feature_options = {node_label(node): node for node in feature_nodes}
    selected_feature = feature_options[st.selectbox("Feature", list(feature_options))]
    scenario_nodes = _children_of_type(context, selected_feature.id, NodeType.SCENARIO)

    if not scenario_nodes:
        st.info("This feature file has no parsed scenarios.")
        return

    scenario_options = {node_label(node): node for node in scenario_nodes}
    scenario_options["All scenarios in this feature"] = None
    selected_scenario = scenario_options[st.selectbox("Scenario", list(scenario_options))]
    scenarios_to_render = scenario_nodes if selected_scenario is None else (selected_scenario,)

    include_examples = st.toggle("Include Scenario Outline example values", value=False)

    st.write("Selected Feature")
    st.dataframe(node_table_rows((selected_feature,)), use_container_width=True, hide_index=True)

    flow_rows = _feature_flow_rows(context, scenarios_to_render)
    if not include_examples:
        flow_rows = [
            row
            for row in flow_rows
            if row["Node Type"] != NodeType.EXAMPLE_VALUE.value
        ]

    if not flow_rows:
        st.info("No relationships were found for this selection.")
        return

    st.write("Flow Table")
    st.dataframe(flow_rows, use_container_width=True, hide_index=True)

    st.write("Offline Interactive Flow")
    graph_nodes, graph_edges = feature_flow_graph(
        context,
        selected_feature,
        scenarios_to_render,
        include_examples=include_examples,
    )
    render_interactive_graph(graph_nodes, graph_edges)

    with st.expander("Raw selected-file nodes"):
        nodes = tuple(
            node
            for node in _nodes_for_file(context, selected_file)
            if include_examples or node.type != NodeType.EXAMPLE_VALUE
        )
        st.dataframe(node_table_rows(nodes), use_container_width=True, hide_index=True)


def _render_non_feature_file_flow(
    context: ExplorationContext,
    selected_file: Path,
    file_nodes: tuple[GraphNode, ...],
) -> None:
    st.write("File Nodes")
    if not file_nodes:
        st.info("No graph nodes were created for this file.")
        return

    node_options = {
        node_label(node): node
        for node in sorted(file_nodes, key=lambda node: (node.type.value, node.name))
    }
    selected_node = node_options[st.selectbox("Node in file", list(node_options))]

    st.write("Selected Node")
    st.dataframe(node_table_rows((selected_node,)), use_container_width=True, hide_index=True)

    st.write("Direct Relationships")
    rows = _direct_relationship_rows(context, selected_node)
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.write("Offline Interactive Relationships")
    graph_nodes, graph_edges = relationship_neighborhood(
        context,
        selected_node.id,
        max_depth=2,
        include_examples=False,
    )
    render_interactive_graph(graph_nodes, graph_edges)


def _feature_flow_rows(
    context: ExplorationContext,
    scenario_nodes: tuple[GraphNode, ...],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for scenario_node in scenario_nodes:
        rows.append(_row("Scenario", scenario_node, "", "Feature contains scenario"))
        for step_node in _children_of_type(context, scenario_node.id, NodeType.STEP):
            rows.append(_row("Step", step_node, scenario_node.name, "Scenario has step"))
            step_definitions = _children_by_relation(
                context,
                step_node.id,
                RelationType.MATCHES_STEP_DEFINITION,
            )
            for step_definition in step_definitions:
                rows.append(
                    _row("Step Definition", step_definition, step_node.name, "Step matches annotation")
                )
                methods = _children_by_relation(context, step_definition.id, RelationType.IMPLEMENTED_BY)
                for method in methods:
                    _append_method_flow_rows(context, rows, method, step_definition.name, depth=0)

            for example_value in _parents_by_relation(context, step_node.id, RelationType.BINDS_TO_PARAMETER):
                rows.append(
                    _row(
                        "Example Value",
                        example_value,
                        step_node.name,
                        "Example value binds to step parameter",
                    )
                )
    return rows


def _append_method_flow_rows(
    context: ExplorationContext,
    rows: list[dict[str, object]],
    method_node: GraphNode,
    parent_name: str,
    depth: int,
    visited: set[str] | None = None,
) -> None:
    visited = visited or set()
    if method_node.id in visited or depth > 4:
        return
    visited.add(method_node.id)

    rows.append(_row(method_node.type.value, method_node, parent_name, "Java implementation flow"))

    for property_node in _children_by_relation(context, method_node.id, RelationType.USES_PROPERTY):
        rows.append(_row("Property Key", property_node, method_node.name, "Method reads property key"))
        for xpath_node in _children_by_relation(context, property_node.id, RelationType.RESOLVES_TO):
            rows.append(_row("XPath", xpath_node, property_node.name, "Property resolves to XPath"))

    for called_method in _children_by_relation(context, method_node.id, RelationType.CALLS):
        if called_method.type in IMPLEMENTATION_NODE_TYPES:
            _append_method_flow_rows(context, rows, called_method, method_node.name, depth + 1, visited)


def _direct_relationship_rows(
    context: ExplorationContext,
    selected_node: GraphNode,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for edge in context.graph.parent_edges(selected_node.id):
        parent = context.graph.get_node(edge.source_id)
        if parent is not None:
            rows.append(_relationship_row("Parent", edge, parent))
    for edge in context.graph.child_edges(selected_node.id):
        child = context.graph.get_node(edge.target_id)
        if child is not None:
            rows.append(_relationship_row("Child", edge, child))
    return rows


def _row(node_type: str, node: GraphNode, parent: str, relationship: str) -> dict[str, object]:
    return {
        "Node Type": node_type,
        "Name": node.name,
        "Relationship": relationship,
        "From": parent,
        "File": str(node.file_path) if node.file_path else "",
        "Line": node.line or "",
        "Value": node.metadata.get("value", ""),
    }


def _relationship_row(direction: str, edge: GraphEdge, node: GraphNode) -> dict[str, object]:
    return {
        "Direction": direction,
        "Relation": edge.relation.value,
        "Node Type": node.type.value,
        "Name": node.name,
        "File": str(node.file_path) if node.file_path else "",
        "Line": node.line or "",
    }


def _nodes_for_file(context: ExplorationContext, file_path: Path) -> tuple[GraphNode, ...]:
    return tuple(
        sorted(
            (node for node in context.graph.nodes if node.file_path == file_path),
            key=lambda node: (node.line or 0, node.type.value, node.name),
        )
    )


def _children_of_type(
    context: ExplorationContext,
    node_id: str,
    node_type: NodeType,
) -> tuple[GraphNode, ...]:
    return tuple(node for node in context.graph.children(node_id) if node.type == node_type)


def _children_by_relation(
    context: ExplorationContext,
    node_id: str,
    relation: RelationType,
) -> tuple[GraphNode, ...]:
    return _nodes_from_edges(
        context,
        (
            edge.target_id
            for edge in context.graph.child_edges(node_id)
            if edge.relation == relation
        ),
    )


def _parents_by_relation(
    context: ExplorationContext,
    node_id: str,
    relation: RelationType,
) -> tuple[GraphNode, ...]:
    return _nodes_from_edges(
        context,
        (
            edge.source_id
            for edge in context.graph.parent_edges(node_id)
            if edge.relation == relation
        ),
    )


def _nodes_from_edges(context: ExplorationContext, node_ids: Iterable[str]) -> tuple[GraphNode, ...]:
    nodes = [context.graph.get_node(node_id) for node_id in node_ids]
    return tuple(node for node in nodes if node is not None)


def _relative_path(context: ExplorationContext, path: Path) -> str:
    try:
        return str(path.relative_to(context.index.root))
    except ValueError:
        return str(path)
