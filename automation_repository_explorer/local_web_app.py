"""Standard-library local web UI for Automation Repository Explorer."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlparse
import webbrowser

from automation_repository_explorer.core.exceptions import AREError
from automation_repository_explorer.models.graph import GraphNode, NodeType
from automation_repository_explorer.search.search_engine import SearchMode, SearchResult
from automation_repository_explorer.services.explorer_service import (
    ExplorationContext,
    ExplorerService,
)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LocalWebState:
    """In-memory state for one local ARE session."""

    service: ExplorerService
    context: ExplorationContext | None = None
    repository_path: Path | None = None
    error: str | None = None


class LocalARERequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the local-only ARE UI."""

    state: ClassVar[LocalWebState]

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        """Route GET requests."""

        route = urlparse(self.path)
        if route.path == "/":
            self._send_html(self._render_home())
            return
        if route.path == "/search":
            params = parse_qs(route.query)
            self._send_html(self._render_search(params))
            return
        if route.path == "/node":
            params = parse_qs(route.query)
            self._send_html(self._render_node(params))
            return
        if route.path == "/clear":
            self.state.context = None
            self.state.repository_path = None
            self.state.error = None
            self._redirect("/")
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Page not found")

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        """Route POST requests."""

        route = urlparse(self.path)
        if route.path == "/scan":
            self._handle_scan()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Page not found")

    def log_message(self, format: str, *args: object) -> None:
        """Use normal logging instead of printing noisy HTTP logs."""

        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _handle_scan(self) -> None:
        form = self._read_form()
        raw_path = form.get("repository_path", [""])[0].strip()
        if not raw_path:
            self.state.error = "Enter a local automation repository folder path."
            self._redirect("/")
            return

        repository_path = Path(raw_path).expanduser().resolve()
        try:
            context = self.state.service.explore(repository_path)
        except AREError as exc:
            self.state.error = str(exc)
        except OSError as exc:
            self.state.error = f"Unable to access repository path: {exc}"
        else:
            self.state.context = context
            self.state.repository_path = repository_path
            self.state.error = None
        self._redirect("/")

    def _read_form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        return parse_qs(body)

    def _render_home(self) -> str:
        context = self.state.context
        summary_html = ""
        if context is not None:
            summary = context.summary
            summary_html = f"""
            <section class="panel">
              <h2>Repository Summary</h2>
              <div class="grid">
                {self._metric("Files", summary.files)}
                {self._metric("Features", summary.features)}
                {self._metric("Scenarios", summary.scenarios)}
                {self._metric("Steps", summary.steps)}
                {self._metric("Java Classes", summary.java_classes)}
                {self._metric("Java Methods", summary.java_methods)}
                {self._metric("Property Keys", summary.properties)}
                {self._metric("Graph Edges", summary.graph_edges)}
              </div>
            </section>
            <section class="panel">
              <h2>Next</h2>
              <p>Search for a feature, step, Java method, property key, XPath, or example value.</p>
              <form method="get" action="/search" class="inline-form">
                <input name="q" placeholder="Search repository" />
                <select name="type">
                  <option value="">All types</option>
                  {self._node_type_options("")}
                </select>
                <button type="submit">Search</button>
              </form>
            </section>
            """

        repository_value = self._escape(str(self.state.repository_path or ""))
        return self._page(
            "Home",
            f"""
            <section class="panel">
              <h2>Scan Local Repository</h2>
              <p>
                Paste a folder path that exists on this machine. ARE is read-only and does not
                upload, deploy, copy, or modify your automation repository.
              </p>
              {self._error_banner()}
              <form method="post" action="/scan">
                <label for="repository_path">Repository folder path</label>
                <input id="repository_path" name="repository_path" value="{repository_value}"
                       placeholder="C:\\Users\\you\\IdeaProjects\\automation-repo" />
                <button type="submit">Scan repository</button>
                <a class="secondary" href="/clear">Clear</a>
              </form>
            </section>
            {summary_html}
            """,
        )

    def _render_search(self, params: dict[str, list[str]]) -> str:
        context = self.state.context
        if context is None:
            return self._page(
                "Search",
                """
                <section class="panel">
                  <h2>Search</h2>
                  <p>Scan a local repository first.</p>
                  <a href="/">Go to Home</a>
                </section>
                """,
            )

        query = params.get("q", [""])[0].strip()
        selected_type = params.get("type", [""])[0]
        mode_value = params.get("mode", [SearchMode.CASE_INSENSITIVE.value])[0]
        try:
            mode = SearchMode(mode_value)
        except ValueError:
            mode = SearchMode.CASE_INSENSITIVE

        node_types = None
        if selected_type:
            node_types = {NodeType(selected_type)}

        results: tuple[SearchResult, ...] = tuple()
        if query:
            results = self.state.service.search(
                context.graph,
                query=query,
                mode=mode,
                node_types=node_types,
            )

        rows = "\n".join(self._search_row(result) for result in results)
        if query and not rows:
            rows = "<tr><td colspan='5'>No matching repository artifact found.</td></tr>"

        return self._page(
            "Search",
            f"""
            <section class="panel">
              <h2>Search</h2>
              <form method="get" action="/search" class="search-form">
                <input name="q" value="{self._escape(query)}" placeholder="Search anything" />
                <select name="type">
                  <option value="">All types</option>
                  {self._node_type_options(selected_type)}
                </select>
                <select name="mode">
                  {self._search_mode_options(mode)}
                </select>
                <button type="submit">Search</button>
              </form>
            </section>
            <section class="panel">
              <h2>Results</h2>
              <p>{len(results)} result(s)</p>
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Name</th>
                    <th>Matched Text</th>
                    <th>File</th>
                    <th>Line</th>
                  </tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </section>
            """,
        )

    def _render_node(self, params: dict[str, list[str]]) -> str:
        context = self.state.context
        if context is None:
            return self._page("Details", "<section class='panel'><p>Scan a repository first.</p></section>")

        node_id = params.get("id", [""])[0]
        details = self.state.service.node_details(context.graph, node_id)
        node = details.get("node")
        if not isinstance(node, GraphNode):
            return self._page("Details", "<section class='panel'><p>Node not found.</p></section>")

        parents = details.get("parents", tuple())
        children = details.get("children", tuple())
        parent_rows = self._node_rows(parents if isinstance(parents, tuple) else tuple())
        child_rows = self._node_rows(children if isinstance(children, tuple) else tuple())
        metadata_rows = "\n".join(
            f"<tr><td>{self._escape(str(key))}</td><td>{self._escape(str(value))}</td></tr>"
            for key, value in node.metadata.items()
        )

        return self._page(
            "Details",
            f"""
            <section class="panel">
              <h2>{self._escape(node.name)}</h2>
              <p><strong>Type:</strong> {self._escape(node.type.value)}</p>
              <p><strong>File:</strong> {self._escape(str(node.file_path or ""))}</p>
              <p><strong>Line:</strong> {self._escape(str(node.line or ""))}</p>
            </section>
            <section class="panel">
              <h2>Incoming Relationships</h2>
              <table><tbody>{parent_rows or "<tr><td>None</td></tr>"}</tbody></table>
            </section>
            <section class="panel">
              <h2>Outgoing Relationships</h2>
              <table><tbody>{child_rows or "<tr><td>None</td></tr>"}</tbody></table>
            </section>
            <section class="panel">
              <h2>Metadata</h2>
              <table><tbody>{metadata_rows or "<tr><td>None</td></tr>"}</tbody></table>
            </section>
            """,
        )

    def _search_row(self, result: SearchResult) -> str:
        node = result.node
        file_path = self._escape(str(node.file_path or ""))
        line = self._escape(str(node.line or ""))
        return f"""
        <tr>
          <td>{self._escape(node.type.value)}</td>
          <td><a href="/node?id={self._escape(node.id)}">{self._escape(node.name)}</a></td>
          <td>{self._escape(result.matched_text)}</td>
          <td class="path">{file_path}</td>
          <td>{line}</td>
        </tr>
        """

    def _node_rows(self, nodes: tuple[GraphNode, ...]) -> str:
        return "\n".join(
            f"""
            <tr>
              <td>{self._escape(node.type.value)}</td>
              <td><a href="/node?id={self._escape(node.id)}">{self._escape(node.name)}</a></td>
              <td class="path">{self._escape(str(node.file_path or ""))}</td>
              <td>{self._escape(str(node.line or ""))}</td>
            </tr>
            """
            for node in nodes
        )

    def _node_type_options(self, selected: str) -> str:
        return "\n".join(
            f'<option value="{self._escape(node_type.value)}" {self._selected(node_type.value, selected)}>'
            f"{self._escape(node_type.value)}</option>"
            for node_type in NodeType
        )

    def _search_mode_options(self, selected: SearchMode) -> str:
        return "\n".join(
            f'<option value="{self._escape(mode.value)}" {self._selected(mode.value, selected.value)}>'
            f"{self._escape(mode.value.replace('_', ' ').title())}</option>"
            for mode in SearchMode
        )

    def _error_banner(self) -> str:
        if not self.state.error:
            return ""
        return f'<div class="error">{self._escape(self.state.error)}</div>'

    @staticmethod
    def _metric(label: str, value: int) -> str:
        return f'<div class="metric"><span>{html.escape(label)}</span><strong>{value}</strong></div>'

    @staticmethod
    def _selected(value: str, selected: str) -> str:
        return "selected" if value == selected else ""

    def _page(self, title: str, body: str) -> str:
        return f"""<!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>ARE - {self._escape(title)}</title>
            <style>
              body {{ font-family: Arial, sans-serif; margin: 0; background: #f6f7f9; color: #172033; }}
              header {{ background: #111827; color: white; padding: 20px 28px; }}
              header h1 {{ margin: 0; font-size: 24px; }}
              header p {{ margin: 6px 0 0; color: #cbd5e1; }}
              nav {{ background: white; border-bottom: 1px solid #d8dee8; padding: 10px 28px; }}
              nav a {{ margin-right: 18px; color: #174ea6; text-decoration: none; font-weight: 600; }}
              main {{ padding: 24px 28px 40px; }}
              .panel {{ background: white; border: 1px solid #d8dee8; border-radius: 8px; padding: 18px; margin-bottom: 18px; }}
              label {{ display: block; margin-bottom: 8px; font-weight: 700; }}
              input, select {{ box-sizing: border-box; width: 100%; padding: 10px; border: 1px solid #b9c1d0; border-radius: 6px; margin-bottom: 12px; }}
              button, .secondary {{ display: inline-block; border: 0; border-radius: 6px; background: #174ea6; color: white; padding: 10px 14px; text-decoration: none; cursor: pointer; }}
              .secondary {{ background: #5b6472; margin-left: 8px; }}
              .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
              .metric {{ border: 1px solid #d8dee8; border-radius: 8px; padding: 14px; background: #fbfcfe; }}
              .metric span {{ display: block; color: #5b6472; font-size: 13px; }}
              .metric strong {{ display: block; font-size: 26px; margin-top: 4px; }}
              .error {{ background: #fde2e1; border: 1px solid #e09b98; color: #7f1d1d; padding: 12px; border-radius: 6px; margin-bottom: 14px; }}
              table {{ width: 100%; border-collapse: collapse; }}
              th, td {{ text-align: left; border-bottom: 1px solid #e4e8ef; padding: 9px; vertical-align: top; }}
              th {{ background: #f3f5f9; }}
              .path {{ font-family: Consolas, Menlo, monospace; font-size: 12px; word-break: break-all; }}
              .search-form {{ display: grid; grid-template-columns: 1fr 220px 180px 120px; gap: 10px; align-items: start; }}
              @media (max-width: 900px) {{ .search-form {{ grid-template-columns: 1fr; }} }}
            </style>
          </head>
          <body>
            <header>
              <h1>Automation Repository Explorer</h1>
              <p>Local-only static analysis. No upload. No deployment. No third-party UI framework.</p>
            </header>
            <nav>
              <a href="/">Home</a>
              <a href="/search">Search</a>
              <a href="/clear">Clear</a>
            </nav>
            <main>{body}</main>
          </body>
        </html>"""

    def _send_html(self, content: str) -> None:
        payload = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    @staticmethod
    def _escape(value: str) -> str:
        return html.escape(value, quote=True)


def run_local_server(host: str = "127.0.0.1", port: int = 8501, open_browser: bool = True) -> None:
    """Start the local standard-library ARE web server."""

    LocalARERequestHandler.state = LocalWebState(service=ExplorerService())
    server = ThreadingHTTPServer((host, port), LocalARERequestHandler)
    url = f"http://{host}:{port}"
    print(f"ARE local UI: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()
