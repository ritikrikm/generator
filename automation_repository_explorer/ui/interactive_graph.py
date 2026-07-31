"""Interactive graph rendering for Streamlit."""

from __future__ import annotations

import html
import json

import streamlit.components.v1 as components

from automation_repository_explorer.models.graph import GraphEdge, GraphNode, NodeType

NODE_COLORS = {
    NodeType.FEATURE: "#2563eb",
    NodeType.SCENARIO: "#0891b2",
    NodeType.STEP: "#0f766e",
    NodeType.STEP_DEFINITION: "#7c3aed",
    NodeType.JAVA_CLASS: "#9333ea",
    NodeType.JAVA_METHOD: "#c026d3",
    NodeType.PAGE_OBJECT: "#db2777",
    NodeType.WRAPPER_METHOD: "#ea580c",
    NodeType.PROPERTY_KEY: "#ca8a04",
    NodeType.XPATH: "#16a34a",
    NodeType.EXAMPLE_VALUE: "#64748b",
    NodeType.STRING_LITERAL: "#475569",
    NodeType.FILE: "#334155",
}


def render_interactive_graph(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    height: int = 650,
) -> None:
    """Render an interactive relationship graph."""

    if not nodes:
        return

    components.html(
        build_interactive_graph_html(nodes, edges, height=height),
        height=height,
        scrolling=False,
    )


def build_interactive_graph_html(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    height: int = 650,
) -> str:
    """Build standalone HTML for an interactive vis-network graph."""

    node_ids = {node.id for node in nodes}
    network_nodes = [_network_node(node) for node in nodes]
    network_edges = [
        {
            "from": edge.source_id,
            "to": edge.target_id,
            "label": edge.relation.value,
            "arrows": "to",
            "font": {"align": "middle", "size": 11},
            "color": {"color": "#94a3b8", "highlight": "#0f172a"},
        }
        for edge in edges
        if edge.source_id in node_ids and edge.target_id in node_ids
    ]
    graph_id = f"are-network-{abs(hash(tuple(sorted(node_ids))))}"

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f172a;
      color: #e2e8f0;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 12px;
      height: {height - 12}px;
      padding: 6px;
      box-sizing: border-box;
    }}
    #{graph_id} {{
      height: 100%;
      border: 1px solid #334155;
      border-radius: 8px;
      background: #020617;
    }}
    .details {{
      height: 100%;
      border: 1px solid #334155;
      border-radius: 8px;
      background: #111827;
      padding: 12px;
      box-sizing: border-box;
      overflow: auto;
      font-size: 13px;
    }}
    .details h3 {{
      margin: 0 0 8px;
      font-size: 15px;
      color: #f8fafc;
    }}
    .details dl {{
      margin: 0;
    }}
    .details dt {{
      color: #93c5fd;
      margin-top: 8px;
      font-weight: 600;
    }}
    .details dd {{
      margin: 2px 0 0;
      color: #e5e7eb;
      overflow-wrap: anywhere;
    }}
    .hint {{
      color: #cbd5e1;
      line-height: 1.4;
    }}
  </style>
</head>
<body>
  <div class="layout">
    <div id="{graph_id}"></div>
    <aside id="{graph_id}-details" class="details">
      <h3>Node Details</h3>
      <p class="hint">Click a node to inspect its type, file, line, and value. Drag nodes to rearrange. Scroll or pinch to zoom.</p>
    </aside>
  </div>
  <script>
    const nodes = new vis.DataSet({json.dumps(network_nodes)});
    const edges = new vis.DataSet({json.dumps(network_edges)});
    const container = document.getElementById("{graph_id}");
    const details = document.getElementById("{graph_id}-details");
    const network = new vis.Network(container, {{ nodes, edges }}, {{
      interaction: {{
        hover: true,
        navigationButtons: true,
        keyboard: true,
        multiselect: true
      }},
      physics: {{
        solver: "forceAtlas2Based",
        stabilization: {{ iterations: 180 }}
      }},
      layout: {{
        improvedLayout: true
      }},
      nodes: {{
        shape: "box",
        margin: 10,
        borderWidth: 1,
        shadow: true,
        font: {{ color: "#f8fafc", size: 13, face: "Inter, Segoe UI, sans-serif" }}
      }},
      edges: {{
        smooth: {{ type: "dynamic" }},
        width: 1.5
      }}
    }});

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }}

    function renderDetails(node) {{
      details.innerHTML = `
        <h3>${{escapeHtml(node.type)}}</h3>
        <dl>
          <dt>Name</dt><dd>${{escapeHtml(node.fullName)}}</dd>
          <dt>File</dt><dd>${{escapeHtml(node.file || "")}}</dd>
          <dt>Line</dt><dd>${{escapeHtml(node.line || "")}}</dd>
          <dt>Value</dt><dd>${{escapeHtml(node.value || "")}}</dd>
        </dl>
      `;
    }}

    network.on("selectNode", function(params) {{
      const node = nodes.get(params.nodes[0]);
      renderDetails(node);
    }});
  </script>
</body>
</html>
"""


def _network_node(node: GraphNode) -> dict[str, object]:
    value = node.metadata.get("value", "")
    return {
        "id": node.id,
        "label": _short_label(node),
        "title": _title(node),
        "type": node.type.value,
        "fullName": node.name,
        "file": str(node.file_path) if node.file_path else "",
        "line": node.line or "",
        "value": value,
        "color": {
            "background": NODE_COLORS.get(node.type, "#475569"),
            "border": "#e2e8f0",
            "highlight": {
                "background": "#f97316",
                "border": "#fff7ed",
            },
        },
    }


def _short_label(node: GraphNode) -> str:
    name = node.name
    if len(name) > 54:
        name = f"{name[:51]}..."
    return f"{node.type.value}\n{name}"


def _title(node: GraphNode) -> str:
    lines = [
        f"<strong>{html.escape(node.type.value)}</strong>",
        html.escape(node.name),
    ]
    if node.file_path is not None:
        lines.append(f"File: {html.escape(str(node.file_path))}")
    if node.line is not None:
        lines.append(f"Line: {node.line}")
    value = node.metadata.get("value")
    if value:
        lines.append(f"Value: {html.escape(str(value))}")
    return "<br>".join(lines)
