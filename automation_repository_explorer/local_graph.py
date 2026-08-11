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
    """Build a dependency-free HTML/SVG graph that works from a local ``file://`` URL."""

    sorted_nodes = sorted(nodes, key=lambda node: (_LAYER.get(node.type, 6), node.name, node.id))
    grouped: dict[int, list[GraphNode]] = {}
    for node in sorted_nodes:
        grouped.setdefault(_LAYER.get(node.type, 6), []).append(node)

    positions: dict[str, tuple[int, int]] = {}
    width = 230
    height = 64
    x_gap = 285
    y_gap = 95
    margin_x = 60
    margin_y = 70

    for layer, layer_nodes in grouped.items():
        for index, node in enumerate(layer_nodes):
            positions[node.id] = (margin_x + layer * x_gap, margin_y + index * y_gap)

    graph_width = max((x for x, _ in positions.values()), default=0) + width + 100
    graph_height = max((y for _, y in positions.values()), default=0) + height + 100
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
            f'<path class="edge" d="M{x1},{y1} C{x1 + bend},{y1} {x2 - bend},{y2} {x2},{y2}" />'
        )
        edge_svg.append(
            f'<text class="edge-label" x="{(x1 + x2) // 2}" y="{(y1 + y2) // 2 - 5}">{label}</text>'
        )

    node_svg: list[str] = []
    for node in sorted_nodes:
        x, y = positions[node.id]
        label = _truncate(node.name, 32)
        node_type = node.type.value
        metadata = {
            "type": node_type,
            "name": node.name,
            "file": str(node.file_path) if node.file_path else "",
            "line": node.line or "",
            "metadata": node.metadata,
        }
        metadata_json = html.escape(json.dumps(metadata, default=str), quote=True)
        node_svg.append(
            f'<g class="node" transform="translate({x},{y})" data-details="{metadata_json}">'
            f'<rect width="{width}" height="{height}" rx="8" />'
            f'<text class="type" x="10" y="21">{html.escape(node_type)}</text>'
            f'<text class="name" x="10" y="44">{html.escape(label)}</text>'
            "</g>"
        )

    safe_title = html.escape(title)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{safe_title}</title>
<style>
html, body {{ margin:0; height:100%; font-family:Segoe UI, Arial, sans-serif; background:#0f172a; color:#e5e7eb; }}
.layout {{ display:grid; grid-template-columns:minmax(0,1fr) 340px; height:100vh; }}
.canvas-wrap {{ position:relative; overflow:hidden; background:#020617; }}
.toolbar {{ position:absolute; top:10px; left:10px; z-index:5; display:flex; gap:6px; }}
button {{ background:#1e293b; color:#e5e7eb; border:1px solid #475569; border-radius:5px; padding:6px 10px; cursor:pointer; }}
svg {{ width:100%; height:100%; cursor:grab; }}
.node rect {{ fill:#1d4ed8; stroke:#93c5fd; stroke-width:1.2; cursor:pointer; }}
.node:hover rect {{ stroke:#f97316; stroke-width:3; }}
.node text {{ fill:white; pointer-events:none; }}
.node .type {{ font-weight:700; font-size:12px; }}
.node .name {{ font-size:11px; }}
.edge {{ fill:none; stroke:#64748b; stroke-width:1.4; marker-end:url(#arrow); }}
.edge-label {{ fill:#94a3b8; font-size:9px; paint-order:stroke; stroke:#020617; stroke-width:3px; }}
.details {{ padding:16px; overflow:auto; border-left:1px solid #334155; background:#111827; }}
.details h2 {{ margin-top:0; font-size:17px; }}
.details dt {{ color:#93c5fd; font-weight:600; margin-top:10px; }}
.details dd {{ margin-left:0; word-break:break-word; white-space:pre-wrap; }}
</style>
</head>
<body>
<div class="layout">
  <div class="canvas-wrap">
    <div class="toolbar"><button id="zin">Zoom +</button><button id="zout">Zoom -</button><button id="reset">Reset</button></div>
    <svg id="graph" viewBox="0 0 {graph_width} {graph_height}">
      <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#64748b" /></marker></defs>
      <g id="viewport">{''.join(edge_svg)}{''.join(node_svg)}</g>
    </svg>
  </div>
  <aside class="details" id="details"><h2>{safe_title}</h2><p>Click a node to inspect its local repository details.</p></aside>
</div>
<script>
const svg=document.getElementById('graph'); const viewport=document.getElementById('viewport'); const details=document.getElementById('details');
let scale=1, panX=0, panY=0, dragging=false, startX=0, startY=0;
function apply(){{ viewport.setAttribute('transform',`translate(${{panX}} ${{panY}}) scale(${{scale}})`); }}
svg.addEventListener('mousedown',e=>{{ if(e.target.closest('.node')) return; dragging=true; startX=e.clientX-panX; startY=e.clientY-panY; }});
window.addEventListener('mousemove',e=>{{ if(!dragging) return; panX=e.clientX-startX; panY=e.clientY-startY; apply(); }});
window.addEventListener('mouseup',()=>dragging=false);
svg.addEventListener('wheel',e=>{{ e.preventDefault(); scale=Math.max(.25,Math.min(3,scale*(e.deltaY<0?1.1:.9))); apply(); }},{{passive:false}});
document.getElementById('zin').onclick=()=>{{scale=Math.min(3,scale*1.2);apply();}};
document.getElementById('zout').onclick=()=>{{scale=Math.max(.25,scale*.8);apply();}};
document.getElementById('reset').onclick=()=>{{scale=1;panX=0;panY=0;apply();}};
document.querySelectorAll('.node').forEach(node=>node.addEventListener('click',()=>{{
  const d=JSON.parse(node.dataset.details);
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  details.innerHTML=`<h2>${{esc(d.type)}}</h2><dl><dt>Name</dt><dd>${{esc(d.name)}}</dd><dt>File</dt><dd>${{esc(d.file)}}</dd><dt>Line</dt><dd>${{esc(d.line)}}</dd><dt>Metadata</dt><dd>${{esc(JSON.stringify(d.metadata,null,2))}}</dd></dl>`;
}}));
</script>
</body>
</html>"""


def _truncate(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"
