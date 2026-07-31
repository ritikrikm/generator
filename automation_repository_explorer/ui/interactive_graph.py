"""Offline interactive graph rendering for Streamlit."""

from __future__ import annotations

import json
from collections import defaultdict

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

NODE_TYPE_LAYER = {
    NodeType.FILE: 0,
    NodeType.FEATURE: 1,
    NodeType.SCENARIO: 2,
    NodeType.STEP: 3,
    NodeType.STEP_DEFINITION: 4,
    NodeType.JAVA_CLASS: 5,
    NodeType.JAVA_METHOD: 5,
    NodeType.PAGE_OBJECT: 6,
    NodeType.WRAPPER_METHOD: 7,
    NodeType.PROPERTY_KEY: 8,
    NodeType.XPATH: 9,
    NodeType.EXAMPLE_VALUE: 3,
    NodeType.STRING_LITERAL: 8,
}

NODE_WIDTH = 220
NODE_HEIGHT = 58


def render_interactive_graph(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    height: int = 650,
) -> None:
    """Render an offline interactive relationship graph."""

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
    """Build standalone HTML for an offline interactive SVG graph."""

    node_ids = {node.id for node in nodes}
    graph_nodes = _layout_nodes(nodes, edges)
    graph_edges = [
        {
            "id": f"edge-{index}",
            "source": edge.source_id,
            "target": edge.target_id,
            "label": edge.relation.value,
        }
        for index, edge in enumerate(edges)
        if edge.source_id in node_ids and edge.target_id in node_ids
    ]
    graph_columns = _column_labels(graph_nodes)
    graph_width = max(1100, max((node["x"] for node in graph_nodes), default=0) + NODE_WIDTH + 140)
    graph_height = max(height - 20, max((node["y"] for node in graph_nodes), default=0) + NODE_HEIGHT + 80)
    graph_id = f"are-svg-network-{abs(hash(tuple(sorted(node_ids))))}"

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f172a;
      color: #e2e8f0;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 330px;
      gap: 12px;
      height: {height - 12}px;
      padding: 6px;
      box-sizing: border-box;
    }}
    .canvas {{
      border: 1px solid #334155;
      border-radius: 8px;
      background: #020617;
      overflow: hidden;
      cursor: grab;
    }}
    .canvas.dragging {{
      cursor: grabbing;
    }}
    .details {{
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
    .toolbar {{
      position: absolute;
      top: 12px;
      left: 12px;
      display: flex;
      gap: 6px;
      z-index: 3;
    }}
    .toolbar button {{
      border: 1px solid #475569;
      background: #111827;
      color: #e5e7eb;
      border-radius: 6px;
      padding: 5px 9px;
      cursor: pointer;
      font-size: 12px;
    }}
    .svg-wrap {{
      position: relative;
      height: 100%;
    }}
    .node rect {{
      stroke: #e2e8f0;
      stroke-width: 1;
      rx: 8;
      filter: drop-shadow(0 3px 3px rgba(0, 0, 0, 0.45));
    }}
    .node text {{
      fill: #f8fafc;
      font-size: 12px;
      pointer-events: none;
    }}
    .node.selected rect {{
      stroke: #f97316;
      stroke-width: 3;
    }}
    .edge-line {{
      fill: none;
      stroke: #94a3b8;
      stroke-width: 1.6;
      marker-end: url(#arrow);
    }}
    .edge-label {{
      fill: #cbd5e1;
      font-size: 10px;
      paint-order: stroke;
      stroke: #020617;
      stroke-width: 3px;
    }}
    .column-label {{
      fill: #93c5fd;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
    }}
  </style>
</head>
<body>
  <div class="layout">
    <div class="svg-wrap">
      <div class="toolbar">
        <button type="button" id="{graph_id}-zoom-in">Zoom +</button>
        <button type="button" id="{graph_id}-zoom-out">Zoom -</button>
        <button type="button" id="{graph_id}-reset">Reset</button>
      </div>
      <svg id="{graph_id}" class="canvas" width="100%" height="100%"
        viewBox="0 0 {graph_width} {graph_height}">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"></path>
          </marker>
        </defs>
        <g id="{graph_id}-viewport"></g>
      </svg>
    </div>
    <aside id="{graph_id}-details" class="details">
      <h3>Node Details</h3>
      <p class="hint">
        Offline interactive graph. Drag nodes, pan background, scroll to zoom, or click Reset.
      </p>
    </aside>
  </div>
  <script>
    const graphNodes = {json.dumps(graph_nodes)};
    const graphEdges = {json.dumps(graph_edges)};
    const graphColumns = {json.dumps(graph_columns)};
    const svg = document.getElementById("{graph_id}");
    const viewport = document.getElementById("{graph_id}-viewport");
    const details = document.getElementById("{graph_id}-details");
    const nodeById = new Map(graphNodes.map(node => [node.id, node]));
    let scale = 1;
    let panX = 0;
    let panY = 0;
    let activeNode = null;
    let panning = false;
    let dragStart = null;

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }}

    function pointFromEvent(event) {{
      const point = svg.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      const transformed = point.matrixTransform(svg.getScreenCTM().inverse());
      return {{ x: (transformed.x - panX) / scale, y: (transformed.y - panY) / scale }};
    }}

    function applyTransform() {{
      viewport.setAttribute("transform", `translate(${{panX}}, ${{panY}}) scale(${{scale}})`);
    }}

    function render() {{
      viewport.innerHTML = "";
      const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const labelLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      viewport.appendChild(labelLayer);
      viewport.appendChild(edgeLayer);
      viewport.appendChild(nodeLayer);

      for (const column of graphColumns) {{
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.classList.add("column-label");
        label.setAttribute("x", column.x);
        label.setAttribute("y", 24);
        label.textContent = column.label;
        labelLayer.appendChild(label);
      }}

      for (const edge of graphEdges) {{
        const source = nodeById.get(edge.source);
        const target = nodeById.get(edge.target);
        if (!source || !target) continue;
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.classList.add("edge-line");
        path.dataset.edgeId = edge.id;
        edgeLayer.appendChild(path);

        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.classList.add("edge-label");
        label.dataset.edgeLabelId = edge.id;
        label.textContent = edge.label;
        edgeLayer.appendChild(label);
      }}

      for (const node of graphNodes) {{
        const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
        group.classList.add("node");
        group.dataset.nodeId = node.id;
        group.setAttribute("transform", `translate(${{node.x}}, ${{node.y}})`);

        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("width", node.width);
        rect.setAttribute("height", node.height);
        rect.setAttribute("fill", node.color);
        group.appendChild(rect);

        const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
        title.setAttribute("x", 10);
        title.setAttribute("y", 20);
        title.setAttribute("font-weight", "700");
        title.textContent = node.type;
        group.appendChild(title);

        const name = document.createElementNS("http://www.w3.org/2000/svg", "text");
        name.setAttribute("x", 10);
        name.setAttribute("y", 40);
        name.textContent = node.label;
        group.appendChild(name);

        group.addEventListener("mousedown", event => {{
          event.stopPropagation();
          activeNode = node;
          dragStart = pointFromEvent(event);
          showDetails(node);
          selectNode(group);
        }});
        group.addEventListener("click", event => {{
          event.stopPropagation();
          showDetails(node);
          selectNode(group);
        }});
        nodeLayer.appendChild(group);
      }}

      updateEdges();
      applyTransform();
    }}

    function updateEdges() {{
      for (const edge of graphEdges) {{
        const source = nodeById.get(edge.source);
        const target = nodeById.get(edge.target);
        const path = viewport.querySelector(`[data-edge-id="${{edge.id}}"]`);
        const label = viewport.querySelector(`[data-edge-label-id="${{edge.id}}"]`);
        if (!source || !target || !path || !label) continue;

        const x1 = source.x + source.width;
        const y1 = source.y + source.height / 2;
        const x2 = target.x;
        const y2 = target.y + target.height / 2;
        const bend = Math.max(50, Math.abs(x2 - x1) / 2);
        path.setAttribute(
          "d",
          `M ${{x1}} ${{y1}} C ${{x1 + bend}} ${{y1}}, ${{x2 - bend}} ${{y2}}, ${{x2}} ${{y2}}`
        );
        label.setAttribute("x", (x1 + x2) / 2);
        label.setAttribute("y", (y1 + y2) / 2 - 4);
      }}
    }}

    function selectNode(group) {{
      viewport.querySelectorAll(".node").forEach(node => node.classList.remove("selected"));
      group.classList.add("selected");
    }}

    function showDetails(node) {{
      details.innerHTML = `
        <h3>${{escapeHtml(node.type)}}</h3>
        <dl>
          <dt>Name</dt><dd>${{escapeHtml(node.fullName)}}</dd>
          <dt>File</dt><dd>${{escapeHtml(node.file)}}</dd>
          <dt>Line</dt><dd>${{escapeHtml(node.line)}}</dd>
          <dt>Value</dt><dd>${{escapeHtml(node.value)}}</dd>
        </dl>
      `;
    }}

    svg.addEventListener("mousedown", event => {{
      panning = true;
      dragStart = {{ x: event.clientX, y: event.clientY, panX, panY }};
      svg.classList.add("dragging");
    }});

    window.addEventListener("mousemove", event => {{
      if (activeNode && dragStart) {{
        const point = pointFromEvent(event);
        activeNode.x += point.x - dragStart.x;
        activeNode.y += point.y - dragStart.y;
        dragStart = point;
        const group = viewport.querySelector(`[data-node-id="${{CSS.escape(activeNode.id)}}"]`);
        if (group) group.setAttribute("transform", `translate(${{activeNode.x}}, ${{activeNode.y}})`);
        updateEdges();
        return;
      }}
      if (panning && dragStart) {{
        panX = dragStart.panX + event.clientX - dragStart.x;
        panY = dragStart.panY + event.clientY - dragStart.y;
        applyTransform();
      }}
    }});

    window.addEventListener("mouseup", () => {{
      activeNode = null;
      panning = false;
      dragStart = null;
      svg.classList.remove("dragging");
    }});

    svg.addEventListener("wheel", event => {{
      event.preventDefault();
      const zoom = event.deltaY < 0 ? 1.1 : 0.9;
      scale = Math.min(2.5, Math.max(0.25, scale * zoom));
      applyTransform();
    }}, {{ passive: false }});

    document.getElementById("{graph_id}-zoom-in").addEventListener("click", () => {{
      scale = Math.min(2.5, scale * 1.15);
      applyTransform();
    }});
    document.getElementById("{graph_id}-zoom-out").addEventListener("click", () => {{
      scale = Math.max(0.25, scale * 0.85);
      applyTransform();
    }});
    document.getElementById("{graph_id}-reset").addEventListener("click", () => {{
      scale = 1;
      panX = 0;
      panY = 0;
      applyTransform();
    }});

    render();
  </script>
</body>
</html>
"""


def _layout_nodes(nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]) -> list[dict[str, object]]:
    ranks = _rank_nodes(nodes, edges)
    layers: dict[int, list[GraphNode]] = defaultdict(list)
    for node in nodes:
        layers[ranks[node.id]].append(node)

    graph_nodes: list[dict[str, object]] = []
    y_by_id: dict[str, int] = {}
    for layer_index, layer in sorted(layers.items()):
        ordered_layer = _order_layer(layer, edges, y_by_id)
        for row_index, node in enumerate(ordered_layer):
            y_position = 54 + row_index * 96
            y_by_id[node.id] = y_position
            graph_nodes.append(
                _network_node(
                    node,
                    x=40 + layer_index * 270,
                    y=y_position,
                )
            )
    return graph_nodes


def _rank_nodes(nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]) -> dict[str, int]:
    node_ids = {node.id for node in nodes}
    ranks = {node.id: NODE_TYPE_LAYER.get(node.type, 10) for node in nodes}
    relevant_edges = [
        edge
        for edge in edges
        if edge.source_id in node_ids and edge.target_id in node_ids
    ]

    for _ in range(len(nodes)):
        changed = False
        for edge in relevant_edges:
            source_rank = ranks[edge.source_id]
            target_rank = ranks[edge.target_id]
            if target_rank <= source_rank:
                ranks[edge.target_id] = source_rank + 1
                changed = True
        if not changed:
            break

    compacted = {rank: index for index, rank in enumerate(sorted(set(ranks.values())))}
    return {node_id: compacted[rank] for node_id, rank in ranks.items()}


def _order_layer(
    layer: list[GraphNode],
    edges: tuple[GraphEdge, ...],
    y_by_id: dict[str, int],
) -> list[GraphNode]:
    parent_y: dict[str, list[int]] = defaultdict(list)
    layer_node_ids = {node.id for node in layer}
    for edge in edges:
        if edge.target_id in layer_node_ids and edge.source_id in y_by_id:
            parent_y[edge.target_id].append(y_by_id[edge.source_id])
    return sorted(
        layer,
        key=lambda node: (
            sum(parent_y[node.id]) / len(parent_y[node.id]) if parent_y[node.id] else 10_000,
            node.line or 0,
            node.type.value,
            node.name,
        ),
    )


def _column_labels(graph_nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    labels_by_x: dict[int, set[str]] = defaultdict(set)
    for node in graph_nodes:
        labels_by_x[int(node["x"])].add(str(node["type"]))
    return [
        {"x": x, "label": " / ".join(sorted(labels))}
        for x, labels in sorted(labels_by_x.items())
    ]


def _network_node(node: GraphNode, *, x: int, y: int) -> dict[str, object]:
    value = node.metadata.get("value", "")
    return {
        "id": node.id,
        "label": _short_label(node),
        "type": node.type.value,
        "fullName": node.name,
        "file": str(node.file_path) if node.file_path else "",
        "line": node.line or "",
        "value": value,
        "color": NODE_COLORS.get(node.type, "#475569"),
        "x": x,
        "y": y,
        "width": NODE_WIDTH,
        "height": NODE_HEIGHT,
    }


def _short_label(node: GraphNode) -> str:
    name = node.name.replace("\n", " ")
    if len(name) > 34:
        name = f"{name[:31]}..."
    return name
