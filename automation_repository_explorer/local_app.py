"""Local desktop application for Automation Repository Explorer.

This is the default ARE UI for company laptops. It runs entirely on the local machine,
uses only Python's standard-library Tkinter UI, and never starts a web server or uploads
repository content anywhere.
"""

from __future__ import annotations

import tempfile
import threading
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:  # pragma: no cover - depends on local Python installation
    raise SystemExit(
        "ARE local UI requires Tkinter. Install a standard Python build that includes "
        "Tk/Tcl support, then run ARE again."
    ) from exc

from automation_repository_explorer.models.graph import NodeType
from automation_repository_explorer.search.search_engine import SearchMode, SearchResult
from automation_repository_explorer.services.explorer_service import ExplorationContext, ExplorerService
from automation_repository_explorer.ui.flow_graph import relationship_neighborhood
from automation_repository_explorer.ui.interactive_graph import build_interactive_graph_html


class ARELocalApp:
    """Tkinter desktop UI backed by the existing ARE analysis services."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.service = ExplorerService()
        self.context: ExplorationContext | None = None
        self.search_results: tuple[SearchResult, ...] = tuple()
        self.scan_thread: threading.Thread | None = None

        self.repository_var = tk.StringVar()
        self.progress_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="Select a Java/Selenium/Cucumber repository to scan.")
        self.search_var = tk.StringVar()
        self.search_mode_var = tk.StringVar(value=SearchMode.CASE_INSENSITIVE.value)
        self.node_type_var = tk.StringVar(value="All")

        self.root.title("Automation Repository Explorer")
        self.root.geometry("1280x820")
        self.root.minsize(980, 650)
        self._build_ui()

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, padding=12)
        root_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root_frame)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Automation Repository Explorer", font=("Segoe UI", 18, "bold")).pack(
            anchor=tk.W
        )
        ttk.Label(
            header,
            text="Local static analysis for Java + Selenium + Cucumber repositories",
        ).pack(anchor=tk.W, pady=(2, 10))

        repository_frame = ttk.LabelFrame(root_frame, text="Repository", padding=10)
        repository_frame.pack(fill=tk.X)
        ttk.Entry(repository_frame, textvariable=self.repository_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(repository_frame, text="Browse", command=self._browse_repository).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        self.scan_button = ttk.Button(
            repository_frame,
            text="Scan repository",
            command=self._start_scan,
        )
        self.scan_button.pack(side=tk.LEFT, padx=(8, 0))

        progress_frame = ttk.Frame(root_frame)
        progress_frame.pack(fill=tk.X, pady=(10, 8))
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.pack(fill=tk.X)
        ttk.Label(progress_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=(4, 0))

        self.notebook = ttk.Notebook(root_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.summary_tab = ttk.Frame(self.notebook, padding=10)
        self.files_tab = ttk.Frame(self.notebook, padding=10)
        self.search_tab = ttk.Frame(self.notebook, padding=10)
        self.issues_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.summary_tab, text="Summary")
        self.notebook.add(self.files_tab, text="Files")
        self.notebook.add(self.search_tab, text="Search & Relationships")
        self.notebook.add(self.issues_tab, text="Scan Issues")

        self._build_summary_tab()
        self._build_files_tab()
        self._build_search_tab()
        self._build_issues_tab()

    def _build_summary_tab(self) -> None:
        columns = ("Metric", "Value")
        self.summary_tree = ttk.Treeview(
            self.summary_tab,
            columns=columns,
            show="headings",
            height=14,
        )
        self.summary_tree.heading("Metric", text="Metric")
        self.summary_tree.heading("Value", text="Value")
        self.summary_tree.column("Metric", width=300, anchor=tk.W)
        self.summary_tree.column("Value", width=160, anchor=tk.E)
        self.summary_tree.pack(fill=tk.BOTH, expand=True)

    def _build_files_tab(self) -> None:
        columns = ("Type", "Path", "Size")
        self.files_tree = ttk.Treeview(
            self.files_tab,
            columns=columns,
            show="headings",
        )
        for name in columns:
            self.files_tree.heading(name, text=name)
        self.files_tree.column("Type", width=90, anchor=tk.W)
        self.files_tree.column("Path", width=800, anchor=tk.W)
        self.files_tree.column("Size", width=120, anchor=tk.E)

        scrollbar = ttk.Scrollbar(self.files_tab, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=scrollbar.set)
        self.files_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_search_tab(self) -> None:
        controls = ttk.Frame(self.search_tab)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Search").pack(side=tk.LEFT)
        search_entry = ttk.Entry(controls, textvariable=self.search_var, width=45)
        search_entry.pack(side=tk.LEFT, padx=(6, 10), fill=tk.X, expand=True)
        search_entry.bind("<Return>", lambda _event: self._run_search())

        ttk.Label(controls, text="Mode").pack(side=tk.LEFT)
        ttk.Combobox(
            controls,
            textvariable=self.search_mode_var,
            values=[mode.value for mode in SearchMode],
            state="readonly",
            width=18,
        ).pack(side=tk.LEFT, padx=(6, 10))

        ttk.Label(controls, text="Node type").pack(side=tk.LEFT)
        ttk.Combobox(
            controls,
            textvariable=self.node_type_var,
            values=["All", *[node_type.value for node_type in NodeType]],
            state="readonly",
            width=18,
        ).pack(side=tk.LEFT, padx=(6, 10))

        ttk.Button(controls, text="Search", command=self._run_search).pack(side=tk.LEFT)

        result_frame = ttk.Frame(self.search_tab)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 8))

        columns = ("Score", "Type", "Name", "File", "Line")
        self.search_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        for name in columns:
            self.search_tree.heading(name, text=name)
        self.search_tree.column("Score", width=70, anchor=tk.E)
        self.search_tree.column("Type", width=150, anchor=tk.W)
        self.search_tree.column("Name", width=360, anchor=tk.W)
        self.search_tree.column("File", width=500, anchor=tk.W)
        self.search_tree.column("Line", width=70, anchor=tk.E)

        result_scrollbar = ttk.Scrollbar(
            result_frame,
            orient=tk.VERTICAL,
            command=self.search_tree.yview,
        )
        self.search_tree.configure(yscrollcommand=result_scrollbar.set)
        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        result_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.search_tree.bind("<<TreeviewSelect>>", self._show_selected_result)

        action_frame = ttk.Frame(self.search_tab)
        action_frame.pack(fill=tk.X)
        ttk.Button(
            action_frame,
            text="Open relationship graph",
            command=self._open_selected_graph,
        ).pack(side=tk.LEFT)
        ttk.Label(
            action_frame,
            text="The relationship graph opens as a local HTML file in your browser. No server is started.",
        ).pack(side=tk.LEFT, padx=(10, 0))

        self.details_text = tk.Text(self.search_tab, height=9, wrap=tk.WORD)
        self.details_text.pack(fill=tk.X, pady=(8, 0))
        self.details_text.configure(state=tk.DISABLED)

    def _build_issues_tab(self) -> None:
        ttk.Label(
            self.issues_tab,
            text=(
                "Supported files that ARE could not fully parse are listed here. "
                "The rest of the repository is still explored."
            ),
        ).pack(anchor=tk.W, pady=(0, 8))

        columns = ("Parser", "File", "Reason")
        self.issues_tree = ttk.Treeview(
            self.issues_tab,
            columns=columns,
            show="headings",
        )
        for name in columns:
            self.issues_tree.heading(name, text=name)
        self.issues_tree.column("Parser", width=170, anchor=tk.W)
        self.issues_tree.column("File", width=500, anchor=tk.W)
        self.issues_tree.column("Reason", width=550, anchor=tk.W)

        scrollbar = ttk.Scrollbar(self.issues_tab, orient=tk.VERTICAL, command=self.issues_tree.yview)
        self.issues_tree.configure(yscrollcommand=scrollbar.set)
        self.issues_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _browse_repository(self) -> None:
        selected = filedialog.askdirectory(title="Select repository")
        if selected:
            self.repository_var.set(selected)

    def _start_scan(self) -> None:
        repository_text = self.repository_var.get().strip()
        if not repository_text:
            messagebox.showwarning("ARE", "Select a repository folder first.")
            return

        repository_path = Path(repository_text).expanduser().resolve()
        if not repository_path.exists() or not repository_path.is_dir():
            messagebox.showerror("ARE", f"Repository folder does not exist:\n{repository_path}")
            return

        if self.scan_thread is not None and self.scan_thread.is_alive():
            return

        self.progress_var.set(1)
        self.status_var.set("1% — Starting repository scan...")
        self.scan_button.configure(state=tk.DISABLED)
        self._clear_scan_views()

        self.scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(repository_path,),
            daemon=True,
        )
        self.scan_thread.start()

    def _scan_worker(self, repository_path: Path) -> None:
        def progress(percent: int, message: str) -> None:
            self.root.after(0, self._update_progress, percent, message)

        try:
            context = self.service.explore(repository_path, progress_callback=progress)
        except Exception as exc:  # noqa: BLE001 - UI must surface scan failures cleanly
            self.root.after(0, self._scan_failed, str(exc))
            return

        self.root.after(0, self._scan_finished, context)

    def _update_progress(self, percent: int, message: str) -> None:
        safe_percent = max(0, min(int(percent), 100))
        self.progress_var.set(safe_percent)
        self.status_var.set(f"{safe_percent}% — {message}")

    def _scan_failed(self, message: str) -> None:
        self.scan_button.configure(state=tk.NORMAL)
        self.status_var.set("Scan failed.")
        messagebox.showerror("ARE scan failed", message)

    def _scan_finished(self, context: ExplorationContext) -> None:
        self.context = context
        self.scan_button.configure(state=tk.NORMAL)
        self.progress_var.set(100)
        if context.index.parse_issues:
            self.status_var.set(
                f"100% — Scan complete with {len(context.index.parse_issues)} file(s) needing attention."
            )
        else:
            self.status_var.set("100% — Repository scan complete.")

        self._populate_summary()
        self._populate_files()
        self._populate_issues()

    def _clear_scan_views(self) -> None:
        self.context = None
        self.search_results = tuple()
        for tree in (self.summary_tree, self.files_tree, self.search_tree, self.issues_tree):
            for item in tree.get_children():
                tree.delete(item)
        self._set_details("")

    def _populate_summary(self) -> None:
        assert self.context is not None
        summary = self.context.summary
        rows = (
            ("Supported files discovered", summary.files),
            ("Feature files", summary.features),
            ("Scenarios", summary.scenarios),
            ("Steps", summary.steps),
            ("Java classes", summary.java_classes),
            ("Java methods", summary.java_methods),
            ("Indexed properties/resources", summary.properties),
            ("Graph nodes", summary.graph_nodes),
            ("Graph edges", summary.graph_edges),
            ("Parse issues", summary.parse_issues),
        )
        for metric, value in rows:
            self.summary_tree.insert("", tk.END, values=(metric, value))

    def _populate_files(self) -> None:
        assert self.context is not None
        for repository_file in self.context.index.files:
            try:
                relative = repository_file.path.relative_to(self.context.index.root)
            except ValueError:
                relative = repository_file.path
            self.files_tree.insert(
                "",
                tk.END,
                values=(repository_file.extension, str(relative), repository_file.size_bytes),
            )

    def _populate_issues(self) -> None:
        assert self.context is not None
        for issue in self.context.index.parse_issues:
            try:
                relative = issue.file_path.relative_to(self.context.index.root)
            except ValueError:
                relative = issue.file_path
            self.issues_tree.insert(
                "",
                tk.END,
                values=(issue.parser_name, str(relative), issue.message),
            )

    def _run_search(self) -> None:
        if self.context is None:
            messagebox.showinfo("ARE", "Scan a repository first.")
            return

        query = self.search_var.get().strip()
        if not query:
            return

        try:
            mode = SearchMode(self.search_mode_var.get())
        except ValueError:
            mode = SearchMode.CASE_INSENSITIVE

        node_types: set[NodeType] | None = None
        selected_type = self.node_type_var.get()
        if selected_type != "All":
            node_types = {node_type for node_type in NodeType if node_type.value == selected_type}

        self.search_results = self.service.search(
            self.context.graph,
            query,
            mode=mode,
            node_types=node_types,
            limit=500,
        )

        for item in self.search_tree.get_children():
            self.search_tree.delete(item)

        for index, result in enumerate(self.search_results):
            node = result.node
            file_name = self._relative_path(node.file_path) if node.file_path else ""
            self.search_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    f"{result.score:.1f}",
                    node.type.value,
                    node.name,
                    file_name,
                    node.line or "",
                ),
            )

        self.status_var.set(f"Search returned {len(self.search_results)} result(s).")

    def _show_selected_result(self, _event: object | None = None) -> None:
        result = self._selected_search_result()
        if result is None:
            self._set_details("")
            return

        node = result.node
        lines = [
            f"Type: {node.type.value}",
            f"Name: {node.name}",
            f"Score: {result.score:.1f}",
            f"Matched: {result.matched_text}",
        ]
        if node.file_path is not None:
            lines.append(f"File: {self._relative_path(node.file_path)}")
        if node.line is not None:
            lines.append(f"Line: {node.line}")
        if node.metadata:
            lines.append(f"Metadata: {node.metadata}")
        self._set_details("\n".join(lines))

    def _open_selected_graph(self) -> None:
        if self.context is None:
            messagebox.showinfo("ARE", "Scan a repository first.")
            return

        result = self._selected_search_result()
        if result is None:
            messagebox.showinfo("ARE", "Select a search result first.")
            return

        nodes, edges = relationship_neighborhood(
            self.context,
            result.node.id,
            max_depth=5,
            include_examples=False,
        )
        if not nodes:
            messagebox.showinfo("ARE", "No relationship graph is available for this result.")
            return

        html = build_interactive_graph_html(nodes, edges, height=760)
        safe_name = str(abs(hash(result.node.id)))
        output_path = Path(tempfile.gettempdir()) / f"are_relationship_{safe_name}.html"
        output_path.write_text(html, encoding="utf-8")
        webbrowser.open(output_path.resolve().as_uri())

    def _selected_search_result(self) -> SearchResult | None:
        selected = self.search_tree.selection()
        if not selected:
            return None
        try:
            index = int(selected[0])
        except (TypeError, ValueError):
            return None
        if index < 0 or index >= len(self.search_results):
            return None
        return self.search_results[index]

    def _relative_path(self, path: Path) -> str:
        if self.context is None:
            return str(path)
        try:
            return str(path.relative_to(self.context.index.root))
        except ValueError:
            return str(path)

    def _set_details(self, value: str) -> None:
        self.details_text.configure(state=tk.NORMAL)
        self.details_text.delete("1.0", tk.END)
        if value:
            self.details_text.insert("1.0", value)
        self.details_text.configure(state=tk.DISABLED)


def main() -> None:
    """Launch ARE as a local desktop application."""

    root = tk.Tk()
    ARELocalApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
