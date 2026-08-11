"""Build a scalable project-level navigation model on top of the ARE graph.

Synthetic Project/Category/Folder nodes exist only in this navigation model. They are
never inserted into the repository relationship graph, so static-analysis evidence stays
pure while the UI can still provide a complete project -> file -> implementation drill-down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from automation_repository_explorer.models.graph import NodeType, RelationType
from automation_repository_explorer.services.explorer_service import ExplorationContext


@dataclass(frozen=True, slots=True)
class ProjectFlowNode:
    """One card in the project-flow navigator."""

    id: str
    kind: str
    name: str
    file_path: Path | None = None
    line: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    graph_node_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectFlowEdge:
    """A directed drill-down relationship between two project-flow cards."""

    source_id: str
    target_id: str
    label: str


@dataclass(frozen=True, slots=True)
class ProjectFlowModel:
    """Complete project-flow navigation data for one scanned repository."""

    root_id: str
    nodes: tuple[ProjectFlowNode, ...]
    edges: tuple[ProjectFlowEdge, ...]

    def get_node(self, node_id: str) -> ProjectFlowNode | None:
        return next((node for node in self.nodes if node.id == node_id), None)

    def children(self, node_id: str) -> tuple[ProjectFlowNode, ...]:
        node_by_id = {node.id: node for node in self.nodes}
        return tuple(
            node_by_id[edge.target_id]
            for edge in self.edges
            if edge.source_id == node_id and edge.target_id in node_by_id
        )


_VISIBLE_GRAPH_NODE_TYPES = {
    NodeType.FILE,
    NodeType.FEATURE,
    NodeType.SCENARIO,
    NodeType.STEP,
    NodeType.STEP_DEFINITION,
    NodeType.JAVA_CLASS,
    NodeType.JAVA_METHOD,
    NodeType.PAGE_OBJECT,
    NodeType.WRAPPER_METHOD,
    NodeType.PROPERTY_KEY,
    NodeType.XPATH,
}

_HIDDEN_RELATIONS = {
    RelationType.REFERENCES_LITERAL,
    RelationType.HAS_EXAMPLE_VALUE,
    RelationType.BINDS_TO_PARAMETER,
}

_CATEGORY_ORDER = (
    ("feature", "Feature Files", ".feature"),
    ("java", "Java Files", ".java"),
    ("properties", "Property Files", ".properties"),
    ("resources", "Other Indexed Files", None),
)


def build_project_flow_model(context: ExplorationContext) -> ProjectFlowModel:
    """Create the complete progressive project-flow model for a scanned repository.

    Navigation hierarchy:
        Project -> file category -> folders -> file -> real repository graph relationships.

    Large repositories remain manageable because folders are retained instead of flattening
    thousands of files into one screen.
    """

    root = context.index.root
    root_id = "project:root"
    nodes: dict[str, ProjectFlowNode] = {
        root_id: ProjectFlowNode(
            id=root_id,
            kind="Project",
            name=root.name or str(root),
            file_path=root,
            metadata={
                "indexed_files": len(context.index.files),
                "graph_nodes": len(context.graph.nodes),
                "graph_edges": len(context.graph.edges),
            },
        )
    }
    edges: list[ProjectFlowEdge] = []
    edge_keys: set[tuple[str, str, str]] = set()

    def add_node(node: ProjectFlowNode) -> None:
        nodes.setdefault(node.id, node)

    def add_edge(source_id: str, target_id: str, label: str) -> None:
        key = (source_id, target_id, label)
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append(ProjectFlowEdge(source_id=source_id, target_id=target_id, label=label))

    graph_file_nodes = {
        node.file_path: node
        for node in context.graph.nodes
        if node.type == NodeType.FILE and node.file_path is not None
    }

    files_by_category: dict[str, list[object]] = {key: [] for key, _label, _ext in _CATEGORY_ORDER}
    for repository_file in context.index.files:
        files_by_category[_category_key(repository_file.extension)].append(repository_file)

    for category_key, category_label, _extension in _CATEGORY_ORDER:
        category_files = files_by_category[category_key]
        if not category_files:
            continue

        category_id = f"project:category:{category_key}"
        add_node(
            ProjectFlowNode(
                id=category_id,
                kind="File Category",
                name=category_label,
                metadata={"file_count": len(category_files)},
            )
        )
        add_edge(root_id, category_id, "contains")

        for repository_file in sorted(category_files, key=lambda item: str(item.path)):
            try:
                relative = repository_file.path.relative_to(root)
            except ValueError:
                relative = Path(repository_file.path.name)

            parent_id = category_id
            parent_parts: list[str] = []
            for part in relative.parts[:-1]:
                parent_parts.append(part)
                folder_path = "/".join(parent_parts)
                folder_id = f"project:folder:{category_key}:{folder_path}"
                add_node(
                    ProjectFlowNode(
                        id=folder_id,
                        kind="Folder",
                        name=part,
                        file_path=root.joinpath(*parent_parts),
                        metadata={"relative_path": folder_path},
                    )
                )
                add_edge(parent_id, folder_id, "contains")
                parent_id = folder_id

            graph_file = graph_file_nodes.get(repository_file.path)
            file_id = graph_file.id if graph_file is not None else f"project:file:{repository_file.path}"
            add_node(
                ProjectFlowNode(
                    id=file_id,
                    kind="File",
                    name=repository_file.path.name,
                    file_path=repository_file.path,
                    line=1,
                    metadata={
                        "extension": repository_file.extension,
                        "size_bytes": repository_file.size_bytes,
                        "relative_path": str(relative),
                    },
                    graph_node_id=graph_file.id if graph_file is not None else None,
                )
            )
            add_edge(parent_id, file_id, "contains")

    visible_graph_ids = {
        node.id
        for node in context.graph.nodes
        if node.type in _VISIBLE_GRAPH_NODE_TYPES
    }
    for graph_node in context.graph.nodes:
        if graph_node.id not in visible_graph_ids:
            continue
        if graph_node.type == NodeType.FILE and graph_node.id in nodes:
            continue
        add_node(
            ProjectFlowNode(
                id=graph_node.id,
                kind=graph_node.type.value,
                name=graph_node.name,
                file_path=graph_node.file_path,
                line=graph_node.line,
                metadata=dict(graph_node.metadata),
                graph_node_id=graph_node.id,
            )
        )

    for graph_edge in context.graph.edges:
        if graph_edge.relation in _HIDDEN_RELATIONS:
            continue
        if graph_edge.source_id not in visible_graph_ids or graph_edge.target_id not in visible_graph_ids:
            continue
        if graph_edge.source_id not in nodes or graph_edge.target_id not in nodes:
            continue
        add_edge(graph_edge.source_id, graph_edge.target_id, graph_edge.relation.value)

    return ProjectFlowModel(
        root_id=root_id,
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
    )


def project_flow_category_counts(model: ProjectFlowModel) -> tuple[tuple[str, int], ...]:
    """Return category labels and file counts for the desktop Project Flow tab."""

    counts: list[tuple[str, int]] = []
    for node in model.nodes:
        if node.kind != "File Category":
            continue
        counts.append((node.name, int(node.metadata.get("file_count", 0))))
    return tuple(counts)


def _category_key(extension: str) -> str:
    extension = extension.lower()
    if extension == ".feature":
        return "feature"
    if extension == ".java":
        return "java"
    if extension == ".properties":
        return "properties"
    return "resources"
