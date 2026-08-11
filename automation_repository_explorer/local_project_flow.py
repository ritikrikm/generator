"""Standalone local HTML renderer for the complete ARE project flow."""

from __future__ import annotations

import html
import json

from automation_repository_explorer.project_flow import ProjectFlowModel


def build_local_project_flow_html(
    model: ProjectFlowModel,
    *,
    title: str = "ARE Complete Project Flow",
) -> str:
    """Render a progressive click-to-reveal project navigator.

    Only the current card and its direct children are drawn. Direct children preserve the
    relationship order produced by the repository model. Each visible child is explicitly
    numbered and laid out left-to-right, top-to-bottom so Feature scenarios and Scenario
    steps remain visually sequential instead of appearing alphabetically/randomly arranged.
    """

    nodes = {
        node.id: {
            "id": node.id,
            "kind": node.kind,
            "name": node.name,
            "file": str(node.file_path) if node.file_path else "",
            "line": node.line or "",
            "metadata": node.metadata,
            "graphNodeId": node.graph_node_id or "",
        }
        for node in model.nodes
    }
    edges = [
        {
            "source": edge.source_id,
            "target": edge.target_id,
            "label": edge.label,
        }
        for edge in model.edges
        if edge.source_id in nodes and edge.target_id in nodes
    ]

    node_json = _safe_json(nodes)
    edge_json = _safe_json(edges)
    root_json = json.dumps(model.root_id)
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
.summary {{ margin-left:6px; padding:5px 8px; border-radius:5px; background:rgba(15,23,42,.92); color:#cbd5e1; font-size:12px; border:1px solid #334155; }}
button {{ background:#1e293b; color:#e5e7eb; border:1px solid #475569; border-radius:5px; padding:6px 10px; cursor:pointer; }}
button:hover:not(:disabled) {{ border-color:#93c5fd; }}
button:disabled {{ opacity:.55; cursor:not-allowed; }}
svg {{ width:100%; height:100%; cursor:grab; }}
.node rect {{ fill:#1d4ed8; stroke:#93c5fd; stroke-width:1.2; cursor:pointer; }}
.node.current rect {{ fill:#c2410c; stroke:#fed7aa; stroke-width:3; }}
.node:hover rect {{ stroke:#f97316; stroke-width:3; }}
.node text {{ fill:white; pointer-events:none; }}
.node .kind {{ font-weight:700; font-size:12px; }}
.node .name {{ font-size:11px; }}
.edge {{ fill:none; stroke:#64748b; stroke-width:1.5; marker-end:url(#arrow); }}
.edge-label {{ fill:#94a3b8; font-size:9px; paint-order:stroke; stroke:#020617; stroke-width:3px; }}
.details {{ padding:16px; overflow:auto; border-left:1px solid #334155; background:#111827; }}
.details h2 {{ margin:0 0 4px; font-size:18px; word-break:break-word; }}
.kind-label {{ color:#93c5fd; font-weight:700; margin-bottom:14px; }}
.details dt {{ color:#93c5fd; font-weight:600; margin-top:9px; }}
.details dd {{ margin-left:0; word-break:break-word; white-space:pre-wrap; }}
.help {{ color:#94a3b8; font-size:12px; margin:0 0 12px; }}
.child-list-title {{ margin:18px 0 8px; font-size:14px; font-weight:700; }}
.child-card {{ display:block; width:100%; text-align:left; padding:9px; margin:6px 0; background:#1e293b; border:1px solid #334155; border-radius:7px; color:#e5e7eb; cursor:pointer; }}
.child-card:hover {{ border-color:#22c55e; background:#263449; }}
.child-card .sequence {{ color:#fbbf24; font-size:12px; font-weight:700; }}
.child-card .relation {{ color:#86efac; font-size:11px; font-weight:700; }}
.child-card .ctype {{ color:#93c5fd; font-size:11px; }}
.child-card .cname {{ margin-top:3px; font-size:12px; word-break:break-word; }}
.empty {{ color:#94a3b8; font-size:12px; }}
.breadcrumb {{ margin:8px 0 14px; color:#cbd5e1; font-size:12px; word-break:break-word; }}
</style>
</head>
<body>
<div class="layout">
  <div class="canvas-wrap">
    <div class="toolbar">
      <button id="home">Project Home</button>
      <button id="back" disabled>← Back</button>
      <button id="prev-page" disabled>← Previous cards</button>
      <button id="next-page" disabled>Next cards →</button>
      <button id="zin">Zoom +</button>
      <button id="zout">Zoom -</button>
      <button id="reset">Reset view</button>
      <span class="summary" id="summary"></span>
    </div>
    <svg id="graph" viewBox="0 0 1000 650">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0 L10 5 L0 10 z" fill="#64748b" />
        </marker>
      </defs>
      <g id="viewport"></g>
    </svg>
  </div>
  <aside class="details" id="details"></aside>
</div>
<script id="project-flow-nodes" type="application/json">{node_json}</script>
<script id="project-flow-edges" type="application/json">{edge_json}</script>
<script>
const graphNodes = JSON.parse(document.getElementById('project-flow-nodes').textContent);
const graphEdges = JSON.parse(document.getElementById('project-flow-edges').textContent);
const rootId = {root_json};
const svg = document.getElementById('graph');
const viewport = document.getElementById('viewport');
const details = document.getElementById('details');
const summary = document.getElementById('summary');
const backButton = document.getElementById('back');
const prevPageButton = document.getElementById('prev-page');
const nextPageButton = document.getElementById('next-page');
const NODE_WIDTH = 240;
const NODE_HEIGHT = 66;
const PAGE_SIZE = 24;
const GRID_COLUMNS = 3;
let currentNodeId = rootId;
let currentPage = 0;
let history = [];
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

function childrenOf(nodeId) {{
  // Do not sort here. Model edge order is meaningful for scenarios/steps/method flow.
  return graphEdges
    .filter(edge => edge.source === nodeId && graphNodes[edge.target])
    .map(edge => ({{ edge, node: graphNodes[edge.target] }}));
}}

function applyTransform() {{
  viewport.setAttribute('transform', `translate(${{panX}} ${{panY}}) scale(${{scale}})`);
}}

function resetView() {{
  scale = 1;
  panX = 0;
  panY = 0;
  applyTransform();
}}

function truncate(value, limit=34) {{
  const clean = String(value || '').replace(/\\s+/g, ' ').trim();
  return clean.length <= limit ? clean : clean.slice(0, limit - 1) + '…';
}}

function nodeMarkup(node, x, y, current=false, sequenceNumber=null) {{
  const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  group.setAttribute('class', `node${{current ? ' current' : ''}}`);
  group.setAttribute('transform', `translate(${{x}},${{y}})`);
  group.dataset.nodeId = node.id;

  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  rect.setAttribute('width', NODE_WIDTH);
  rect.setAttribute('height', NODE_HEIGHT);
  rect.setAttribute('rx', '8');
  group.appendChild(rect);

  const kind = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  kind.setAttribute('class', 'kind');
  kind.setAttribute('x', '10');
  kind.setAttribute('y', '22');
  kind.textContent = sequenceNumber === null ? node.kind : `${{sequenceNumber}}. ${{node.kind}}`;
  group.appendChild(kind);

  const name = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  name.setAttribute('class', 'name');
  name.setAttribute('x', '10');
  name.setAttribute('y', '46');
  name.textContent = truncate(node.name);
  group.appendChild(name);

  group.addEventListener('click', () => navigate(node.id));
  viewport.appendChild(group);
}}

function edgeMarkup(source, target, label) {{
  const x1 = source[0] + NODE_WIDTH;
  const y1 = source[1] + NODE_HEIGHT / 2;
  const x2 = target[0];
  const y2 = target[1] + NODE_HEIGHT / 2;
  const bend = Math.max(45, Math.abs(x2 - x1) / 2);

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('class', 'edge');
  path.setAttribute('d', `M${{x1}},${{y1}} C${{x1 + bend}},${{y1}} ${{x2 - bend}},${{y2}} ${{x2}},${{y2}}`);
  viewport.insertBefore(path, viewport.firstChild);

  const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  text.setAttribute('class', 'edge-label');
  text.setAttribute('x', String((x1 + x2) / 2));
  text.setAttribute('y', String((y1 + y2) / 2 - 6));
  text.textContent = label;
  viewport.appendChild(text);
}}

function childPage() {{
  const children = childrenOf(currentNodeId);
  const pageCount = Math.max(1, Math.ceil(children.length / PAGE_SIZE));
  currentPage = Math.min(currentPage, pageCount - 1);
  const start = currentPage * PAGE_SIZE;
  return {{
    children,
    visible: children.slice(start, start + PAGE_SIZE),
    start,
    pageCount
  }};
}}

function renderGraph() {{
  viewport.replaceChildren();
  const current = graphNodes[currentNodeId];
  if (!current) return;
  const page = childPage();
  const children = page.visible;
  const rowGap = 92;
  const columnGap = 320;
  const startY = 86;
  const columns = Math.min(GRID_COLUMNS, Math.max(1, children.length));
  const rows = Math.max(1, Math.ceil(children.length / columns));
  const currentY = children.length ? startY + ((rows - 1) * rowGap) / 2 : 190;
  const currentPos = [70, currentY];
  const positions = {{ [currentNodeId]: currentPos }};

  // Row-major layout keeps visual reading order 1,2,3 / 4,5,6 / 7,8,9.
  children.forEach((item, index) => {{
    const column = index % columns;
    const row = Math.floor(index / columns);
    positions[item.node.id] = [420 + column * columnGap, startY + row * rowGap];
  }});

  children.forEach(item => edgeMarkup(currentPos, positions[item.node.id], item.edge.label));
  nodeMarkup(current, currentPos[0], currentPos[1], true);
  children.forEach((item, index) => {{
    nodeMarkup(
      item.node,
      positions[item.node.id][0],
      positions[item.node.id][1],
      false,
      page.start + index + 1
    );
  }});

  const graphWidth = Math.max(1000, 420 + columns * columnGap + 140);
  const graphHeight = Math.max(650, startY + rows * rowGap + 120);
  svg.setAttribute('viewBox', `0 0 ${{graphWidth}} ${{graphHeight}}`);

  const shownFrom = page.children.length ? page.start + 1 : 0;
  const shownTo = page.start + children.length;
  summary.textContent = `${{current.kind}} → showing ${{shownFrom}}-${{shownTo}} of ${{page.children.length}} direct children in source order`;
  prevPageButton.disabled = currentPage === 0;
  nextPageButton.disabled = currentPage >= page.pageCount - 1;
}}

function breadcrumbText() {{
  const ids = [...history, currentNodeId];
  return ids.map(id => graphNodes[id]?.name || '').filter(Boolean).join('  ›  ');
}}

function childCard(item, sequenceNumber) {{
  return `<button class="child-card" data-target="${{esc(item.node.id)}}">
    <div class="sequence">${{sequenceNumber}}.</div>
    <div class="relation">${{esc(item.edge.label)}}</div>
    <div class="ctype">${{esc(item.node.kind)}}</div>
    <div class="cname">${{esc(item.node.name)}}</div>
  </button>`;
}}

function renderDetails() {{
  const current = graphNodes[currentNodeId];
  if (!current) return;
  const page = childPage();
  const children = page.children;
  const visibleChildren = page.visible;
  const metadata = Object.keys(current.metadata || {{}}).length
    ? JSON.stringify(current.metadata, null, 2)
    : 'No additional metadata.';
  const shownFrom = children.length ? page.start + 1 : 0;
  const shownTo = page.start + visibleChildren.length;

  details.innerHTML = `
    <h2>${{esc(current.name)}}</h2>
    <div class="kind-label">${{esc(current.kind)}}</div>
    <p class="help">Cards are shown in repository/source relationship order. Follow 1 → 2 → 3 → 4 and click any card to reveal its next level.</p>
    <div class="breadcrumb">${{esc(breadcrumbText())}}</div>
    <dl>
      <dt>File</dt><dd>${{esc(current.file)}}</dd>
      <dt>Line</dt><dd>${{esc(current.line)}}</dd>
      <dt>Direct children</dt><dd>${{children.length}}</dd>
      <dt>Metadata</dt><dd>${{esc(metadata)}}</dd>
    </dl>
    <button disabled>Edit File</button>
    <div class="child-list-title">Next level (${{shownFrom}}-${{shownTo}} of ${{children.length}})</div>
    <div>${{visibleChildren.length
      ? visibleChildren.map((item, index) => childCard(item, page.start + index + 1)).join('')
      : '<div class="empty">No further outgoing project-flow relationships.</div>'}}</div>`;

  details.querySelectorAll('.child-card').forEach(card => {{
    card.addEventListener('click', () => navigate(card.dataset.target));
  }});
}}

function render() {{
  backButton.disabled = history.length === 0;
  renderGraph();
  renderDetails();
  resetView();
}}

function navigate(nodeId) {{
  if (!graphNodes[nodeId] || nodeId === currentNodeId) return;
  history.push(currentNodeId);
  currentNodeId = nodeId;
  currentPage = 0;
  render();
}}

function goBack() {{
  if (!history.length) return;
  currentNodeId = history.pop();
  currentPage = 0;
  render();
}}

function goHome() {{
  history = [];
  currentNodeId = rootId;
  currentPage = 0;
  render();
}}

function previousPage() {{
  if (currentPage === 0) return;
  currentPage -= 1;
  render();
}}

function nextPage() {{
  const pageCount = Math.max(1, Math.ceil(childrenOf(currentNodeId).length / PAGE_SIZE));
  if (currentPage >= pageCount - 1) return;
  currentPage += 1;
  render();
}}

document.getElementById('home').addEventListener('click', goHome);
document.getElementById('back').addEventListener('click', goBack);
document.getElementById('prev-page').addEventListener('click', previousPage);
document.getElementById('next-page').addEventListener('click', nextPage);
document.getElementById('zin').addEventListener('click', () => {{ scale = Math.min(4, scale * 1.25); applyTransform(); }});
document.getElementById('zout').addEventListener('click', () => {{ scale = Math.max(.25, scale * .8); applyTransform(); }});
document.getElementById('reset').addEventListener('click', resetView);
svg.addEventListener('wheel', event => {{
  event.preventDefault();
  scale = Math.max(.25, Math.min(4, scale * (event.deltaY < 0 ? 1.1 : .9)));
  applyTransform();
}}, {{ passive:false }});
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
window.addEventListener('mouseup', () => {{ dragging = false; }});
render();
</script>
</body>
</html>"""


def _safe_json(value: object) -> str:
    return json.dumps(value, default=str, ensure_ascii=False).replace("</", "<\\/")
