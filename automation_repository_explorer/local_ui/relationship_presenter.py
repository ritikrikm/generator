"""Data presentation helpers for the local relationship explorer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.graph import GraphEdge, GraphNode


@dataclass(frozen=True, slots=True)
class RelationshipCard:
    node_id: str
    relation: str
    node_type: str
    name: str
    location: str
    evidence: str


@dataclass(frozen=True, slots=True)
class RelationshipView:
    current: GraphNode
    incoming: tuple[RelationshipCard, ...]
    outgoing: tuple[RelationshipCard, ...]


def build_relationship_view(
    graph: RepositoryGraph,
    node_id: str,
    *,
    path_formatter: Callable[[Path], str] = str,
) -> RelationshipView | None:
    """Build direct incoming/outgoing cards for one graph node."""

    current = graph.get_node(node_id)
    if current is None:
        return None

    incoming = tuple(
        card
        for edge in graph.parent_edges(node_id)
        if (card := _card_for_edge(graph, edge, incoming=True, path_formatter=path_formatter))
        is not None
    )
    outgoing = tuple(
        card
        for edge in graph.child_edges(node_id)
        if (card := _card_for_edge(graph, edge, incoming=False, path_formatter=path_formatter))
        is not None
    )
    return RelationshipView(current=current, incoming=incoming, outgoing=outgoing)


def _card_for_edge(
    graph: RepositoryGraph,
    edge: GraphEdge,
    *,
    incoming: bool,
    path_formatter: Callable[[Path], str],
) -> RelationshipCard | None:
    connected_id = edge.source_id if incoming else edge.target_id
    node = graph.get_node(connected_id)
    if node is None:
        return None

    location = ""
    if node.file_path is not None:
        location = path_formatter(node.file_path)
        if node.line:
            location = f"{location}:{node.line}"

    evidence = "; ".join(f"{key}={value}" for key, value in edge.metadata.items())
    return RelationshipCard(
        node_id=node.id,
        relation=edge.relation.value,
        node_type=node.type.value,
        name=node.name,
        location=location,
        evidence=evidence,
    )
