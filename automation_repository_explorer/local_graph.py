"""Standalone offline HTML relationship graph used by the local desktop UI."""

from __future__ import annotations

import html
import json

from automation_repository_explorer.models.graph import GraphEdge, GraphNode, NodeType


_LAYER = {
    NodeType.FILE: 0,
    NodeType.FEATURE: 1,
    NodeType.SCENARIO: 2,
    NodeType.STEP: 3,
    NodeType.EXAMPLE_VALUE: 3,
    NodeType.STEP_DEFINITION: 4,
    NodeType.JAVA_CLASS: 5,
    NodeType.JAVA_METHOD: 6,
    NodeType.PAGE_OBJECT: 6,
    NodeType.WRAPPER_METHOD: 7,
    NodeType.PROPERTY_KEY: 8,
    NodeType.STRING_LITERAL: 8,
    NodeType.XPATH: 9,
}


def build_local_graph_html(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    title: str = "ARE Relationship Graph",
) -> str:
    """Build a dependency-free interactive HTML/SVG relationship graph.

    The graph opens in focused drill mode. Focused mode renders only the current
    node and its direct outgoing relationships, so a user can progressively follow
    File -> Feature -> Scenario -> Step -> implementation relationships without
    visual noise. Full graph mode can be toggled on when the wider neighborhood is
    useful. The underlying ARE graph is never changed by this visualization mode.
    """

    if not nodes:
        return _empty_graph_html(title)

    focus_node_id = nodes[0].id
    sorted_nodes = sorted(
        nodes,
        key=lambda node: (_LAYER.get(node.type, 6), node.name, node.id),
    )
    node_data = {
        node.id: {
            "id": node.id,
            "type": node.type.value,
            "name": node.name,
            "file": str(node.file_path) if node.file_path else "",
            "line": node.line or "",
            "metadata": node.metadata,
        }
        for node in sorted_nodes
    }
    edge_data = [
        {
            "source": edge.source_id,
            "target": edge.target_id,
            "relation": edge.relation.value,
            "metadata": edge.metadata,
        }
        for edge in edges
        if edge.source_id in node_data and edge.target_id in node_data
    ]

    full_positions, full_width, full_height = _full_layout(sorted_nodes)

    node_markup: list[str] = []
    for node in sorted_nodes:
        label = _truncate(node.name, 32)
        node_markup.append(
            f'<g class="node" data-node-id="{html.escape(node.id, quote=True)}">'
            '<rect width="230" height="64" rx="8" />'
            f'<text class="type" x="10" y="21">{html.escape(node.type.value)}</text>'
            f'<text class="name" x="10" y="44">{html.escape(label)}</text>'
            "</g>"
        )

    edge_markup: list[str] = []
    for index, _edge in enumerate(edge_data):
        edge_markup.append(
            f'<g class="edge-group" data-edge-index="{index}">'
            '<path class="edge" />'
            '<text class="edge-label"></text>'
            "</g>"
        )

    node_json = _safe_json(node_data)
    edge_json = _safe_json(edge_data)
    position_json = _safe_json(full_positions)
    focus_json = json.dumps(focus_node_id)
    safe_title = html.escape(title)

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{safe_title}</title>
<style>
html, body {{ margin:0; height:100%; font-family:Segoe UI, Arial, sans-serif; background:#0f172a; color:#e5e7eb; }}
.layout {{ display:grid; grid-template-columns:minmax(0,1fr) 390px; height:100vh; }}
.canvas-wrap {{ position:relative; overflow:hidden; background:#020617; }}
.toolbar {{ position:absolute; top:10px; left:10px; z-index:5; display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
.graph-summary {{ margin-left:6px; padding:5px 8px; border-radius:5px; background:rgba(15,23,42,.92); color:#cbd5e1; font-size:12px; border:1px solid #334155; }}
button {{ background:#1e293b; color:#e5e7eb; border:1px solid #475569; border-radius:5px; padding:6px 10px; cursor:pointer; }}
button:hover:not(:disabled) {{ border-color:#93c5fd; }}
button:disabled {{ opacity:.55; cursor:not-allowed; }}
#mode {{ border-color:#22c55e; }}
svg {{ width:100%; height:100%; cursor:grab; }}
.node {{ display:none; }}
.node rect {{ fill:#1d4ed8; stroke:#93c5fd; stroke-width:1.2; cursor:pointer; }}
.node.selected rect {{ fill:#c2410c; stroke:#fed7aa; stroke-width:3; }}
.node.related rect {{ stroke:#22c55e; stroke-width:2.5; }}
.node:hover rect {{ stroke:#f97316; stroke-width:3; }}
.node text {{ fill:white; pointer-events:none; }}
.node .type {{ font-weight:700; font-size:12px; }}
.node .name {{ font-size:11px; }}
.edge-group {{ display:none; }}
.edge {{ fill:none; stroke:#64748b; stroke-width:1.4; marker-end:url(#arrow); }}
.edge-group.active .edge {{ stroke:#22c55e; stroke-width:2.4; }}
.edge-label {{ fill:#94a3b8; font-size:9px; paint-order:stroke; stroke:#020617; stroke-width:3px; }}
.details {{ padding:16px; overflow:auto; border-left:1px solid #334155; background:#111827; }}
.details h2 {{ margin:0 0 4px; font-size:18px; word-break:break-word; }}
.node-type {{ color:#93c5fd; font-weight:700; margin-bottom:14px; }}
.details dt {{ color:#93c5fd; font-weight:600; margin-top:9px; }}
.details dd {{ margin-left:0; word-break:break-word; white-space:pre-wrap; }}
.section-title {{ margin:18px 0 8px; font-size:14px; font-weight:700; }}
.relationship-card {{ display:block; width:100%; text-align:left; padding:9px; margin:6px 0; background:#1e293b; border:1px solid #334155; border-radius:7px; color:#e5e7eb; cursor:pointer; }}
.relationship-card:hover {{ border-color:#22c55e; background:#263449; }}
.relationship-card .relation {{ color:#86efac; font-size:11px; font-weight:700; }}
.relationship-card .rtype {{ color:#93c5fd; font-size:11px; }}
.relationship-card .rname {{ margin-top:3px; font-size:12px; word-break:break-word; }}
.empty {{ color:#94a3b8; font-size:12px; }}
.mode-help {{ color:#94a3b8; font-size:12px; margin:0 0 12px; }}
</style>
</head>
<body>
<div class="layout">
  <div class="canvas-wrap">
    <div class="toolbar">
      <button id="zin">Zoom +</button>
      <button id="zout">Zoom -</button>
      <button id="reset">Reset view</button>
      <button id="mode">Full graph: OFF</button>
      <span class="graph-summary" id="summary"></span>
    </div>
    <svg id="graph" viewBox="0 0 900 650">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0 L10 5 L0 10 z" fill="#64748b" />
        </marker>
      </defs>
      <g id="viewport">{''.join(edge_markup)}{''.join(node_markup)}</g>
    </svg>
  </div>
  <aside class="details" id="details"></aside>
</div>

<script id="are-node-data" type="application/json">{node_json}</script>
<script id="are-edge-data" type="application/json">{edge_json}</script>
<script id="are-full-positions" type="application/json">{position_json}</script>
<script>
const svg = document.getElementById('graph');
const viewport = document.getElementById('viewport');
const details = document.getElementById('details');
const summary = document.getElementById('summary');
const modeButton = document.getElementById('mode');
const graphNodes = JSON.parse(document.getElementById('are-node-data').textContent);
const graphEdges = JSON.parse(document.getElementById('are-edge-data').textContent);
const fullPositions = JSON.parse(document.getElementById('are-full-positions').textContent);

const NODE_WIDTH = 230;
const NODE_HEIGHT = 64;
let currentNodeId = {focus_json};
let fullGraph = false;
let scale = 1;
let panX = 0;
let panY = 0;
let dragging = false;
let startX = 0;
let startY = 0;

const esc = value => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;');

function applyTransform() {{
  viewport.setAttribute('transform', `translate(${{panX}} ${{panY}}) scale(${{scale}})`);
}}

function resetView() {{
  scale = 1;
  panX = 0;
  panY = 0;
  applyTransform();
}}

function setNodePosition(nodeId, position, visible) {{
  const element = document.querySelector(`.node[data-node-id="${{CSS.escape(nodeId)}}"]`);
  if (!element) return;
  element.style.display = visible ? 'block' : 'none';
  if (visible && position) {{
    element.setAttribute('transform', `translate(${{position[0]}},${{position[1]}})`);
  }}
}}

function curveFor(sourcePosition, targetPosition) {{
  const x1 = sourcePosition[0] + NODE_WIDTH;
  const y1 = sourcePosition[1] + NODE_HEIGHT / 2;
  const x2 = targetPosition[0];
  const y2 = targetPosition[1] + NODE_HEIGHT / 2;
  const bend = Math.max(40, Math.abs(x2 - x1) / 2);
  return {{
    path: `M${{x1}},${{y1}} C${{x1 + bend}},${{y1}} ${{x2 - bend}},${{y2}} ${{x2}},${{y2}}`,
    labelX: (x1 + x2) / 2,
    labelY: (y1 + y2) / 2 - 5
  }};
}}

function renderEdge(index, visible, positions) {{
  const group = document.querySelector(`.edge-group[data-edge-index="${{index}}"]`);
  if (!group) return;
  group.style.display = visible ? 'block' : 'none';
  if (!visible) return;

  const edge = graphEdges[index];
  const sourcePosition = positions[edge.source];
  const targetPosition = positions[edge.target];
  if (!sourcePosition || !targetPosition) {{
    group.style.display = 'none';
    return;
  }}
  const geometry = curveFor(sourcePosition, targetPosition);
  group.querySelector('.edge').setAttribute('d', geometry.path);
  const label = group.querySelector('.edge-label');
  label.setAttribute('x', geometry.labelX);
  label.setAttribute('y', geometry.labelY);
  label.textContent = edge.relation;
  group.classList.toggle(
    'active',
    edge.source === currentNodeId || edge.target === currentNodeId
  );
}}

function focusedLayout() {{
  const outgoing = graphEdges.filter(edge => edge.source === currentNodeId && graphNodes[edge.target]);
  const childIds = [...new Set(outgoing.map(edge => edge.target))];
  const positions = {{}};
  const maxRows = 9;
  const rowGap = 92;
  const columnGap = 300;
  const startY = 90;
  const childColumns = Math.max(1, Math.ceil(childIds.length / maxRows));
  const rowsInFirstColumn = Math.min(maxRows, Math.max(1, childIds.length));
  const currentY = childIds.length
    ? startY + ((rowsInFirstColumn - 1) * rowGap) / 2
    : 170;

  positions[currentNodeId] = [70, currentY];
  childIds.forEach((nodeId, index) => {{
    const column = Math.floor(index / maxRows);
    const row = index % maxRows;
    positions[nodeId] = [390 + column * columnGap, startY + row * rowGap];
  }});

  const width = Math.max(900, 390 + childColumns * columnGap + 120);
  const height = Math.max(650, startY + Math.min(maxRows, Math.max(1, childIds.length)) * rowGap + 100);
  return {{ positions, childIds, outgoing, width, height }};
}}

function renderGraph() {{
  if (!graphNodes[currentNodeId]) return;

  const allNodeIds = Object.keys(graphNodes);
  if (fullGraph) {{
    allNodeIds.forEach(nodeId => setNodePosition(nodeId, fullPositions[nodeId], true));
    graphEdges.forEach((_edge, index) => renderEdge(index, true, fullPositions));
    svg.setAttribute('viewBox', `0 0 {full_width} {full_height}`);
    summary.textContent = `Full neighborhood: ${{allNodeIds.length}} nodes · ${{graphEdges.length}} relationships`;
  }} else {{
    const focused = focusedLayout();
    const visibleIds = new Set([currentNodeId, ...focused.childIds]);
    allNodeIds.forEach(nodeId => setNodePosition(nodeId, focused.positions[nodeId], visibleIds.has(nodeId)));
    graphEdges.forEach((edge, index) => {{
      const visible = edge.source === currentNodeId && visibleIds.has(edge.target);
      renderEdge(index, visible, focused.positions);
    }});
    svg.setAttribute('viewBox', `0 0 ${{focused.width}} ${{focused.height}}`);
    summary.textContent = `Focused drill: current node + ${{focused.childIds.length}} direct outgoing`;
  }}

  const incoming = graphEdges.filter(edge => edge.target === currentNodeId);
  const outgoing = graphEdges.filter(edge => edge.source === currentNodeId);
  const relatedIds = new Set([
    ...incoming.map(edge => edge.source),
    ...outgoing.map(edge => edge.target),
  ]);

  document.querySelectorAll('.node').forEach(element => {{
    const nodeId = element.dataset.nodeId;
    element.classList.toggle('selected', nodeId === currentNodeId);
    element.classList.toggle('related', nodeId !== currentNodeId && relatedIds.has(nodeId));
  }});
}}

function relationshipCard(edge, incoming) {{
  const targetId = incoming ? edge.source : edge.target;
  const node = graphNodes[targetId];
  if (!node) return '';
  return `<button class="relationship-card" data-target="${{esc(targetId)}}">
    <div class="relation">${{esc(edge.relation)}}</div>
    <div class="rtype">${{esc(node.type)}}</div>
    <div class="rname">${{esc(node.name)}}</div>
  </button>`;
}}

function renderDetails() {{
  const node = graphNodes[currentNodeId];
  if (!node) return;
  const incoming = graphEdges.filter(edge => edge.target === currentNodeId);
  const outgoing = graphEdges.filter(edge => edge.source === currentNodeId);
  const metadata = Object.keys(node.metadata || {{}}).length
    ? JSON.stringify(node.metadata, null, 2)
    : 'No additional metadata.';

  details.innerHTML = `
    <h2>${{esc(node.name)}}</h2>
    <div class="node-type">${{esc(node.type)}}</div>
    <p class="mode-help">${{fullGraph
      ? 'Full graph is ON. All cards in this visual neighborhood are shown.'
      : 'Full graph is OFF. The canvas shows only this node and its direct outgoing cards.'}}</p>
    <dl>
      <dt>File</dt><dd>${{esc(node.file)}}</dd>
      <dt>Line</dt><dd>${{esc(node.line)}}</dd>
      <dt>Relationships</dt><dd>Incoming: ${{incoming.length}} · Outgoing: ${{outgoing.length}}</dd>
      <dt>Metadata</dt><dd>${{esc(metadata)}}</dd>
    </dl>
    <button disabled title="Reserved for a future edit workflow">Edit File</button>
    <div class="section-title">Incoming Relationships (${{incoming.length}})</div>
    <div>${{incoming.length
      ? incoming.map(edge => relationshipCard(edge, true)).join('')
      : '<div class="empty">No incoming relationships in this visual neighborhood.</div>'}}</div>
    <div class="section-title">Outgoing Relationships (${{outgoing.length}})</div>
    <div>${{outgoing.length
      ? outgoing.map(edge => relationshipCard(edge, false)).join('')
      : '<div class="empty">No outgoing relationships in this visual neighborhood.</div>'}}</div>
  `;

  details.querySelectorAll('.relationship-card').forEach(card => {{
    card.addEventListener('click', () => selectNode(card.dataset.target));
  }});
}}

function selectNode(nodeId) {{
  if (!graphNodes[nodeId]) return;
  currentNodeId = nodeId;
  if (!fullGraph) resetView();
  renderGraph();
  renderDetails();
}}

modeButton.addEventListener('click', () => {{
  fullGraph = !fullGraph;
  modeButton.textContent = `Full graph: ${{fullGraph ? 'ON' : 'OFF'}}`;
  resetView();
  renderGraph();
  renderDetails();
}});

svg.addEventListener('mousedown', event => {{
  if (event.target.closest('.node')) return;
  dragging = true;
  startX = event.clientX - panX;
  startY = event.clientY - panY;
}});
window.addEventListener('mousemove', event => {{
  if (!dragging) return;
  panX = event.clientX - startX;
  panY = event.clientY - startY;
  applyTransform();
}});
window.addEventListener('mouseup', () => {{
  dragging = false;
}});
svg.addEventListener('wheel', event => {{
  event.preventDefault();
  scale = Math.max(.25, Math.min(4, scale * (event.deltaY < 0 ? 1.1 : .9)));
  applyTransform();
}}, {{ passive:false }});

document.getElementById('zin').addEventListener('click', () => {{
  scale = Math.min(4, scale * 1.25);
  applyTransform();
}});
document.getElementById('zout').addEventListener('click', () => {{
  scale = Math.max(.25, scale * .8);
  applyTransform();
}});
document.getElementById('reset').addEventListener('click', resetView);

document.querySelectorAll('.node').forEach(element => {{
  element.addEventListener('click', () => selectNode(element.dataset.nodeId));
}});

selectNode(currentNodeId);
</script>
</body>
</html>"""


def _full_layout(
    nodes: list[GraphNode],
) -> tuple[dict[str, list[int]], int, int]:
    grouped: dict[int, list[GraphNode]] = {}
    for node in nodes:
        grouped.setdefault(_LAYER.get(node.type, 6), []).append(node)

    positions: dict[str, list[int]] = {}
    column_step = 315
    logical_layer_gap = 125
    y_gap = 92
    margin_x = 60
    margin_y = 80
    max_rows_per_column = 18
    current_x = margin_x
    max_rows_used = 1

    for layer in sorted(grouped):
        layer_nodes = grouped[layer]
        column_count = max(
            1,
            (len(layer_nodes) + max_rows_per_column - 1) // max_rows_per_column,
        )
        rows_used = min(max_rows_per_column, max(1, len(layer_nodes)))
        max_rows_used = max(max_rows_used, rows_used)

        for index, node in enumerate(layer_nodes):
            column_index = index // max_rows_per_column
            row_index = index % max_rows_per_column
            positions[node.id] = [
                current_x + column_index * column_step,
                margin_y + row_index * y_gap,
            ]
        current_x += column_count * column_step + logical_layer_gap

    graph_width = max(current_x + 80, 900)
    graph_height = max(
        margin_y + (max_rows_used - 1) * y_gap + 64 + 120,
        650,
    )
    return positions, graph_width, graph_height


def _safe_json(value: object) -> str:
    return json.dumps(value, default=str).replace("</", "<\\/")


def _empty_graph_html(title: str) -> str:
    safe_title = html.escape(title)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{safe_title}</title></head>"
        "<body><p>No relationship graph is available.</p></body></html>"
    )


def _truncate(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"
