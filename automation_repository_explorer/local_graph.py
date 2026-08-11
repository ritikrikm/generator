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

    The first node is the initial focus node. Clicking any card makes it the current node;
    its immediate incoming/outgoing relationships are then shown in the right-side explorer.
    Large layers wrap across columns to remain readable on large repositories.
    """

    sorted_nodes = sorted(nodes, key=lambda node: (_LAYER.get(node.type, 6), node.name, node.id))
    grouped: dict[int, list[GraphNode]] = {}
    for node in sorted_nodes:
        grouped.setdefault(_LAYER.get(node.type, 6), []).append(node)

    selected_node_id = nodes[0].id if nodes else None

    positions: dict[str, tuple[int, int]] = {}
    width = 230
    height = 64
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
        column_count = max(1, (len(layer_nodes) + max_rows_per_column - 1) // max_rows_per_column)
        rows_used = min(max_rows_per_column, max(1, len(layer_nodes)))
        max_rows_used = max(max_rows_used, rows_used)

        for index, node in enumerate(layer_nodes):
            column_index = index // max_rows_per_column
            row_index = index % max_rows_per_column
            positions[node.id] = (
                current_x + column_index * column_step,
                margin_y + row_index * y_gap,
            )
        current_x += column_count * column_step + logical_layer_gap

    graph_width = max(current_x + 80, 900)
    graph_height = max(margin_y + (max_rows_used - 1) * y_gap + height + 120, 650)
    node_ids = set(positions)

    edge_svg: list[str] = []
    for edge in edges:
        if edge.source_id not in node_ids or edge.target_id not in node_ids:
            continue
        sx, sy = positions[edge.source_id]
        tx, ty = positions[edge.target_id]
        x1 = sx + width
        y1 = sy + height // 2
        x2 = tx
        y2 = ty + height // 2
        bend = max(40, abs(x2 - x1) // 2)
        label = html.escape(edge.relation.value)
        edge_svg.append(
            f'<path class="edge" data-source="{html.escape(edge.source_id, quote=True)}" '
            f'data-target="{html.escape(edge.target_id, quote=True)}" '
            f'd="M{x1},{y1} C{x1 + bend},{y1} {x2 - bend},{y2} {x2},{y2}" />'
        )
        edge_svg.append(
            f'<text class="edge-label" x="{(x1 + x2) // 2}" y="{(y1 + y2) // 2 - 5}">{label}</text>'
        )

    node_svg: list[str] = []
    for node in sorted_nodes:
        x, y = positions[node.id]
        label = _truncate(node.name, 32)
        node_type = node.type.value
        selected_class = " selected" if node.id == selected_node_id else ""
        node_svg.append(
            f'<g class="node{selected_class}" transform="translate({x},{y})" '
            f'data-node-id="{html.escape(node.id, quote=True)}">'
            f'<rect width="{width}" height="{height}" rx="8" />'
            f'<text class="type" x="10" y="21">{html.escape(node_type)}</text>'
            f'<text class="name" x="10" y="44">{html.escape(label)}</text>'
            "</g>"
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
        for node in nodes
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

    node_json = json.dumps(node_data, default=str).replace("</", "<\\/")
    edge_json = json.dumps(edge_data, default=str).replace("</", "<\\/")
    selected_json = json.dumps(selected_node_id)
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
.toolbar {{ position:absolute; top:10px; left:10px; z-index:5; display:flex; gap:6px; align-items:center; }}
.graph-summary {{ margin-left:6px; padding:5px 8px; border-radius:5px; background:rgba(15,23,42,.88); color:#cbd5e1; font-size:12px; border:1px solid #334155; }}
button {{ background:#1e293b; color:#e5e7eb; border:1px solid #475569; border-radius:5px; padding:6px 10px; cursor:pointer; }}
button:hover {{ border-color:#93c5fd; }}
svg {{ width:100%; height:100%; cursor:grab; }}
.node rect {{ fill:#1d4ed8; stroke:#93c5fd; stroke-width:1.2; cursor:pointer; }}
.node.selected rect {{ fill:#c2410c; stroke:#fed7aa; stroke-width:3; }}
.node.related rect {{ stroke:#22c55e; stroke-width:2.5; }}
.node:hover rect {{ stroke:#f97316; stroke-width:3; }}
.node text {{ fill:white; pointer-events:none; }}
.node .type {{ font-weight:700; font-size:12px; }}
.node .name {{ font-size:11px; }}
.edge {{ fill:none; stroke:#64748b; stroke-width:1.4; marker-end:url(#arrow); }}
.edge.active {{ stroke:#22c55e; stroke-width:2.4; }}
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
.edit-file {{ margin-top:14px; }}
</style>
</head>
<body>
<div class="layout">
  <div class="canvas-wrap">
    <div class="toolbar">
      <button id="zin">Zoom +</button>
      <button id="zout">Zoom -</button>
      <button id="reset">Reset</button>
      <span class="graph-summary">Focused view: {len(nodes)} nodes · {len(edges)} relationships</span>
    </div>
    <svg id="graph" viewBox="0 0 {graph_width} {graph_height}">
      <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#64748b" /></marker></defs>
      <g id="viewport">{''.join(edge_svg)}{''.join(node_svg)}</g>
    </svg>
  </div>
  <aside class="details" id="details"></aside>
</div>
<script id="are-node-data" type="application/json">{node_json}</script>
<script id="are-edge-data" type="application/json">{edge_json}</script>
<script>
const svg=document.getElementById('graph');
const viewport=document.getElementById('viewport');
const details=document.getElementById('details');
const graphNodes=JSON.parse(document.getElementById('are-node-data').textContent);
const graphEdges=JSON.parse(document.getElementById('are-edge-data').textContent);
let currentNodeId={selected_json};
let scale=1, panX=0, panY=0, dragging=false, startX=0, startY=0;

const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function apply(){{ viewport.setAttribute('transform',`translate(${{panX}} ${{panY}}) scale(${{scale}})`); }}
function relationshipCard(edge,incoming){{
  const targetId=incoming?edge.source:edge.target;
  const node=graphNodes[targetId];
  if(!node) return '';
  return `<button class="relationship-card" data-target="${{esc(targetId)}}"><div class="relation">${{esc(edge.relation)}}</div><div class="rtype">${{esc(node.type)}}</div><div class="rname">${{esc(node.name)}}</div></button>`;
}}
function selectNode(nodeId){{
  const d=graphNodes[nodeId];
  if(!d) return;
  currentNodeId=nodeId;
  const incoming=graphEdges.filter(e=>e.target===nodeId);
  const outgoing=graphEdges.filter(e=>e.source===nodeId);
  const relatedIds=new Set([...incoming.map(e=>e.source),...outgoing.map(e=>e.target)]);

  document.querySelectorAll('.node').forEach(el=>{{
    const id=el.dataset.nodeId;
    el.classList.toggle('selected',id===nodeId);
    el.classList.toggle('related',id!==nodeId && relatedIds.has(id));
  }});
  document.querySelectorAll('.edge').forEach(el=>{{
    el.classList.toggle('active',el.dataset.source===nodeId || el.dataset.target===nodeId);
  }});

  const metadata=Object.keys(d.metadata||{{}}).length?JSON.stringify(d.metadata,null,2):'No additional metadata.';
  details.innerHTML=`
    <h2>${{esc(d.name)}}</h2>
    <div class="node-type">${{esc(d.type)}}</div>
    <dl>
      <dt>File</dt><dd>${{esc(d.file)}}</dd>
      <dt>Line</dt><dd>${{esc(d.line)}}</dd>
      <dt>Relationships</dt><dd>Incoming: ${{incoming.length}} · Outgoing: ${{outgoing.length}}</dd>
      <dt>Metadata</dt><dd>${{esc(metadata)}}</dd>
    </dl>
    <button class="edit-file">Edit File</button>
    <div class="section-title">Incoming Relationships (${{incoming.length}})</div>
    <div>${{incoming.length?incoming.map(e=>relationshipCard(e,true)).join(''):'<div class="empty">No incoming relationships in this focused view.</div>'}}</div>
    <div class="section-title">Outgoing Relationships (${{outgoing.length}})</div>
    <div>${{outgoing.length?outgoing.map(e=>relationshipCard(e,false)).join(''):'<div class="empty">No outgoing relationships in this focused view.</div>'}}</div>`;

  details.querySelectorAll('.relationship-card').forEach(card=>{{
    card.addEventListener('click',()=>selectNode(card.dataset.target));
  }});
  // Edit File is intentionally visual-only for now.
}}

svg.addEventListener('mousedown',e=>{{ if(e.target.closest('.node')) return; dragging=true; startX=e.clientX-panX; startY=e.clientY-panY; }});
window.addEventListener('mousemove',e=>{{ if(!dragging) return; panX=e.clientX-startX; panY=e.clientY-startY; apply(); }});
window.addEventListener('mouseup',()=>dragging=false);
svg.addEventListener('wheel',e=>{{ e.preventDefault(); scale=Math.max(.25,Math.min(4,scale*(e.deltaY<0?1.1:.9))); apply(); }},{{passive:false}});
document.getElementById('zin').onclick=()=>{{scale=Math.min(4,scale*1.25);apply();}};
document.getElementById('zout').onclick=()=>{{scale=Math.max(.25,scale*.8);apply();}};
document.getElementById('reset').onclick=()=>{{scale=1;panX=0;panY=0;apply();}};
document.querySelectorAll('.node').forEach(node=>node.addEventListener('click',()=>selectNode(node.dataset.nodeId)));
if(currentNodeId) selectNode(currentNodeId);
</script>
</body>
</html>"""


def _truncate(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"
