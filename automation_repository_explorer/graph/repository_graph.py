"""In-memory bidirectional repository relationship graph."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable

from automation_repository_explorer.models.graph import GraphEdge, GraphNode


class RepositoryGraph:
    """Directed graph with reverse adjacency for reverse mapping."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._children: dict[str, list[GraphEdge]] = defaultdict(list)
        self._parents: dict[str, list[GraphEdge]] = defaultdict(list)

    @property
    def nodes(self) -> tuple[GraphNode, ...]:
        return tuple(self._nodes.values())

    @property
    def edges(self) -> tuple[GraphEdge, ...]:
        return tuple(self._edges)

    def add_node(self, node: GraphNode) -> GraphNode:
        """Add a node if absent and return the stored node."""

        existing = self._nodes.get(node.id)
        if existing is not None:
            return existing
        self._nodes[node.id] = node
        return node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge if source and target nodes exist."""

        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            return
        if edge in self._edges:
            return
        self._edges.append(edge)
        self._children[edge.source_id].append(edge)
        self._parents[edge.target_id].append(edge)

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def children(self, node_id: str) -> tuple[GraphNode, ...]:
        return tuple(
            self._nodes[edge.target_id]
            for edge in self._children.get(node_id, [])
            if edge.target_id in self._nodes
        )

    def parents(self, node_id: str) -> tuple[GraphNode, ...]:
        return tuple(
            self._nodes[edge.source_id]
            for edge in self._parents.get(node_id, [])
            if edge.source_id in self._nodes
        )

    def child_edges(self, node_id: str) -> tuple[GraphEdge, ...]:
        return tuple(self._children.get(node_id, []))

    def parent_edges(self, node_id: str) -> tuple[GraphEdge, ...]:
        return tuple(self._parents.get(node_id, []))

    def related(self, node_id: str) -> tuple[GraphNode, ...]:
        related_nodes = {node.id: node for node in self.children(node_id)}
        related_nodes.update({node.id: node for node in self.parents(node_id)})
        return tuple(related_nodes.values())

    def traverse(self, start_node_id: str, max_depth: int = 8) -> tuple[GraphNode, ...]:
        """Traverse parents and children from a node."""

        visited: set[str] = set()
        ordered: list[GraphNode] = []
        queue: deque[tuple[str, int]] = deque([(start_node_id, 0)])

        while queue:
            node_id, depth = queue.popleft()
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)
            node = self._nodes.get(node_id)
            if node is not None:
                ordered.append(node)
            for edge in self._children.get(node_id, []):
                queue.append((edge.target_id, depth + 1))
            for edge in self._parents.get(node_id, []):
                queue.append((edge.source_id, depth + 1))

        return tuple(ordered)

    def find_by_ids(self, node_ids: Iterable[str]) -> tuple[GraphNode, ...]:
        return tuple(self._nodes[node_id] for node_id in node_ids if node_id in self._nodes)
