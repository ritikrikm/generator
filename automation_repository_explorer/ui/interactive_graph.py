"""Interactive graph HTML builder.

The HTML generation is framework-independent. A legacy Streamlit rendering helper is kept
optional so the local desktop application can use this module without Streamlit installed.
"""

from __future__ import annotations

import json
from collections import defaultdict

try:
    import streamlit.components.v1 as components
except ImportError:  # Local desktop mode does not require Streamlit.
    components = None  # type: ignore[assignment]

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


def render_interactive_graph(nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...], *, height: int = 650) -> None:
    """Legacy optional Streamlit renderer."""
    if not nodes:
        return
    if components is None:
        raise RuntimeError("Streamlit is not installed. Use ARE local desktop mode instead.")
    components.html(build_interactive_graph_html(nodes, edges, height=height), height=height, scrolling=False)


def build_interactive_graph_html(nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...], *, height: int = 650) -> str:
    """Build standalone HTML for an offline interactive SVG graph."""
    node_ids = {node.id for node in nodes}
    graph_nodes = _layout_nodes(nodes, edges)
    graph_edges = [
        {"id": f"edge-{index}", "source": edge.source_id, "target": edge.target_id, "label": edge.relation.value}
        for index, edge in enumerate(edges)
        if edge.source_id in node_ids and edge.target_id in node_ids
    ]
    graph_columns = _column_labels(graph_nodes)
    graph_width = max(1100, max((node["x"] for node in graph_nodes), default=0) + NODE_WIDTH + 140)
    graph_height = max(height - 20, max((node["y"] for node in graph_nodes), default=0) + NODE_HEIGHT + 80)
    graph_id = f"are-svg-network-{abs(hash(tuple(sorted(node_ids))))}"
    return _html_document(graph_id, graph_nodes, graph_edges, graph_columns, graph_width, graph_height, height)


def _html_document(graph_id: str, graph_nodes: list[dict[str, object]], graph_edges: list[dict[str, object]], graph_columns: list[dict[str, object]], graph_width: int, graph_height: int, height: int) -> str:
    """Return self-contained local HTML with no external network dependencies."""
    payload = json.dumps({"nodes": graph_nodes, "edges": graph_edges, "columns": graph_columns})
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><title>ARE Relationship Graph</title>
<style>
body{{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0}}
.layout{{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:10px;height:{height}px;padding:8px;box-sizing:border-box}}
.canvas{{width:100%;height:100%;background:#020617;border:1px solid #334155;border-radius:8px}}
.details{{background:#111827;border:1px solid #334155;border-radius:8px;padding:12px;overflow:auto}}
.node rect{{stroke:#e2e8f0;stroke-width:1;rx:8}} .node text{{fill:#fff;font-size:12px;pointer-events:none}}
.edge{{fill:none;stroke:#94a3b8;stroke-width:1.5}} .label{{fill:#cbd5e1;font-size:10px}}
</style></head><body><div class="layout"><svg id="{graph_id}" class="canvas" viewBox="0 0 {graph_width} {graph_height}"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#94a3b8"/></marker></defs><g id="vp"></g></svg><aside class="details"><h3>Node Details</h3><div id="details">Click a node.</div></aside></div>
<script>
const data={payload}; const vp=document.getElementById('vp'); const details=document.getElementById('details'); const map=new Map(data.nodes.map(n=>[n.id,n]));
data.edges.forEach(e=>{{const s=map.get(e.source),t=map.get(e.target);if(!s||!t)return;const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('class','edge');const x1=s.x+s.width,y1=s.y+s.height/2,x2=t.x,y2=t.y+t.height/2,b=Math.max(40,Math.abs(x2-x1)/2);p.setAttribute('d',`M ${{x1}} ${{y1}} C ${{x1+b}} ${{y1}}, ${{x2-b}} ${{y2}}, ${{x2}} ${{y2}}`);p.setAttribute('marker-end','url(#arrow)');vp.appendChild(p);}});
data.nodes.forEach(n=>{{const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('class','node');g.setAttribute('transform',`translate(${{n.x}},${{n.y}})`);const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.setAttribute('width',n.width);r.setAttribute('height',n.height);r.setAttribute('fill',n.color);g.appendChild(r);const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.setAttribute('x',10);t.setAttribute('y',22);t.textContent=n.type;g.appendChild(t);const t2=document.createElementNS('http://www.w3.org/2000/svg','text');t2.setAttribute('x',10);t2.setAttribute('y',42);t2.textContent=n.label;g.appendChild(t2);g.onclick=()=>details.textContent=`${{n.type}}\n${{n.fullName||n.label}}\n${{n.file||''}}:${{n.line||''}}`;vp.appendChild(g);}});
</script></body></html>'''


def _layout_nodes(nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]) -> list[dict[str, object]]:
    grouped: dict[int, list[GraphNode]] = defaultdict(list)
    for node in nodes:
        grouped[NODE_TYPE_LAYER.get(node.type, 5)].append(node)
    rendered: list[dict[str, object]] = []
    for layer in sorted(grouped):
        for row, node in enumerate(sorted(grouped[layer], key=lambda item: (item.name, item.id))):
            rendered.append({"id": node.id, "type": node.type.value, "label": _short(node.name, 28), "fullName": node.name, "file": str(node.file_path or ""), "line": node.line or "", "value": str(node.metadata.get("value", "")), "x": 50 + layer * 280, "y": 55 + row * 90, "width": NODE_WIDTH, "height": NODE_HEIGHT, "color": NODE_COLORS.get(node.type, "#475569")})
    return rendered


def _column_labels(graph_nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    by_x: dict[int, str] = {}
    for node in graph_nodes:
        by_x.setdefault(int(node["x"]), str(node["type"]))
    return [{"x": x, "label": label} for x, label in sorted(by_x.items())]


def _short(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"
