"""Reusable Streamlit components."""

from __future__ import annotations

from automation_repository_explorer.models.graph import GraphNode


def node_label(node: GraphNode) -> str:
    """Return a compact display label for graph nodes."""

    location = ""
    if node.file_path is not None and node.line is not None:
        location = f" ({node.file_path.name}:{node.line})"
    return f"{node.type.value}: {node.name}{location}"


def node_table_rows(nodes: tuple[GraphNode, ...]) -> list[dict[str, object]]:
    """Convert graph nodes to table-ready rows."""

    return [
        {
            "Type": node.type.value,
            "Name": node.name,
            "File": str(node.file_path) if node.file_path else "",
            "Line": node.line or "",
            "ID": node.id,
        }
        for node in nodes
    ]
