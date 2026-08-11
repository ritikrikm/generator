"""Flow graph helpers shared by ARE user interfaces."""

from __future__ import annotations

from collections.abc import Callable

from automation_repository_explorer.models.graph import GraphEdge, GraphNode, NodeType, RelationType
from automation_repository_explorer.services.explorer_service import ExplorationContext

IMPLEMENTATION_NODE_TYPES = {
    NodeType.JAVA_METHOD,
    NodeType.PAGE_OBJECT,
    NodeType.WRAPPER_METHOD,
}


def relationship_neighborhood(
    context: ExplorationContext,
    selected_node_id: str,
    *,
    max_depth: int = 5,
    include_examples: bool = False,
    max_nodes: int | None = 120,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return a focused interactive subgraph around one selected node.

    Repository analysis itself remains complete. ``max_nodes`` only limits the visual
    neighborhood so a high-degree node in a large repository cannot create an unreadable
    diagram containing thousands of nodes. The traversal is breadth-first, so the selected
    node and its nearest relationships are retained first.
    """

    nodes = tuple(
        node
        for node in context.graph.traverse(selected_node_id, max_depth=max_depth)
        if include_examples or node.type != NodeType.EXAMPLE_VALUE
    )
    if max_nodes is not None and max_nodes > 0:
        nodes = nodes[:max_nodes]

    node_ids = {node.id for node in nodes}
    edges = tuple(
        edge
        for edge in context.graph.edges
        if edge.source_id in node_ids and edge.target_id in node_ids
    )
    return nodes, edges


def feature_flow_graph(
    context: ExplorationContext,
    feature_node: GraphNode,
    scenario_nodes: tuple[GraphNode, ...],
    *,
    include_examples: bool = False,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Return the forward feature implementation flow subgraph."""

    node_ids: set[str] = {feature_node.id}
    edge_keys: set[tuple[str, str, RelationType]] = set()

    def include_edge(edge: GraphEdge) -> None:
        node_ids.add(edge.source_id)
        node_ids.add(edge.target_id)
        edge_keys.add((edge.source_id, edge.target_id, edge.relation))

    for scenario_node in scenario_nodes:
        _include_edge_between(context, feature_node.id, scenario_node.id, include_edge)
        for step_edge in _child_edges_by_relation(context, scenario_node.id, RelationType.HAS_STEP):
            include_edge(step_edge)
            step_node_id = step_edge.target_id
            for step_definition_edge in _child_edges_by_relation(
                context,
                step_node_id,
                RelationType.MATCHES_STEP_DEFINITION,
            ):
                include_edge(step_definition_edge)
                for method_edge in _child_edges_by_relation(
                    context,
                    step_definition_edge.target_id,
                    RelationType.IMPLEMENTED_BY,
                ):
                    include_edge(method_edge)
                    _include_method_flow(context, method_edge.target_id, include_edge, depth=0)
            if include_examples:
                for example_edge in _parent_edges_by_relation(
                    context,
                    step_node_id,
                    RelationType.BINDS_TO_PARAMETER,
                ):
                    include_edge(example_edge)

    nodes = tuple(
        node
        for node in context.graph.find_by_ids(node_ids)
        if include_examples or node.type != NodeType.EXAMPLE_VALUE
    )
    visible_node_ids = {node.id for node in nodes}
    edges = tuple(
        edge
        for edge in context.graph.edges
        if (edge.source_id, edge.target_id, edge.relation) in edge_keys
        and edge.source_id in visible_node_ids
        and edge.target_id in visible_node_ids
    )
    return nodes, edges


def _include_method_flow(
    context: ExplorationContext,
    method_node_id: str,
    include_edge: Callable[[GraphEdge], None],
    *,
    depth: int,
    visited: set[str] | None = None,
) -> None:
    visited = visited or set()
    if method_node_id in visited or depth > 4:
        return
    visited.add(method_node_id)

    for property_edge in _child_edges_by_relation(context, method_node_id, RelationType.USES_PROPERTY):
        include_edge(property_edge)
        for xpath_edge in _child_edges_by_relation(
            context,
            property_edge.target_id,
            RelationType.RESOLVES_TO,
        ):
            include_edge(xpath_edge)

    for call_edge in _child_edges_by_relation(context, method_node_id, RelationType.CALLS):
        called_node = context.graph.get_node(call_edge.target_id)
        if called_node is None or called_node.type not in IMPLEMENTATION_NODE_TYPES:
            continue
        include_edge(call_edge)
        _include_method_flow(context, call_edge.target_id, include_edge, depth=depth + 1, visited=visited)


def _include_edge_between(
    context: ExplorationContext,
    source_id: str,
    target_id: str,
    include_edge: Callable[[GraphEdge], None],
) -> None:
    for edge in context.graph.child_edges(source_id):
        if edge.target_id == target_id:
            include_edge(edge)


def _child_edges_by_relation(
    context: ExplorationContext,
    node_id: str,
    relation: RelationType,
) -> tuple[GraphEdge, ...]:
    return tuple(edge for edge in context.graph.child_edges(node_id) if edge.relation == relation)


def _parent_edges_by_relation(
    context: ExplorationContext,
    node_id: str,
    relation: RelationType,
) -> tuple[GraphEdge, ...]:
    return tuple(edge for edge in context.graph.parent_edges(node_id) if edge.relation == relation)
