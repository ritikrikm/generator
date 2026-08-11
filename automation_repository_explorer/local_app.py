"""Local desktop application for Automation Repository Explorer.

ARE runs entirely on the local machine using Python's standard-library Tkinter UI.
Repository content is never uploaded and no local web server is started.
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

from automation_repository_explorer.local_graph import build_local_graph_html
from automation_repository_explorer.models.graph import GraphEdge, GraphNode, NodeType
from automation_repository_explorer.search.search_engine import SearchMode, SearchResult
from automation_repository_explorer.services.explorer_service import ExplorationContext, ExplorerService
from automation_repository_explorer.ui.flow_graph import relationship_neighborhood


class ARELocalApp:
    """Tkinter desktop UI backed by the existing ARE analysis services."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.service = ExplorerService()
        self.context: ExplorationContext | None = None
        self.search_results: tuple[SearchResult, ...] = tuple()
        self.scan_thread: threading.Thread | None = None

        # Interactive relationship-explorer state.
        self.current_node_id: str | None = None
        self.back_history: list[str] = []
        self.forward_history: list[str] = []
        self.incoming_targets: dict[str, str] = {}
        self.outgoing_targets: dict[str, str] = {}
        self.current_score: float | None = None
        self.current_matched_text: str | None = None

        self.repository_var = tk.StringVar()
        self.progress_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="Select a Java/Selenium/Cucumber repository to scan.")
        self.search_var = tk.StringVar()
        self.search_mode_var = tk.StringVar(value=SearchMode.CASE_INSENSITIVE.value)
        self.node_type_var = tk.StringVar(value="All")

        self.current_name_var = tk.StringVar(value="No node selected")
        self.current_type_var = tk.StringVar(value="")
        self.current_file_var = tk.StringVar(value="")
        self.current_line_var = tk.StringVar(value="")
        self.current_counts_var = tk.StringVar(value="Incoming: 0   Outgoing: 0")

        self.root.title("Automation Repository Explorer")
        self.root.geometry("1480x940")
        self.root.minsize(1100, 720)
        self._build_ui()

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, padding=12)
        root_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root_frame)
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="Automation Repository Explorer",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor=tk.W)
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
        self.summary_tree = ttk.Treeview(
            self.summary_tab,
            columns=("Metric", "Value"),
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
        self.files_tree = ttk.Treeview(self.files_tab, columns=columns, show="headings")
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

        content_pane = tk.PanedWindow(
            self.search_tab,
            orient=tk.VERTICAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            borderwidth=0,
        )
        content_pane.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        result_frame = ttk.LabelFrame(content_pane, text="Search Results", padding=6)
        content_pane.add(result_frame, minsize=170, stretch="always")

        columns = ("Score", "Type", "Name", "File", "Line")
        self.search_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=8,
        )
        for name in columns:
            self.search_tree.heading(name, text=name)
        self.search_tree.column("Score", width=70, anchor=tk.E)
        self.search_tree.column("Type", width=150, anchor=tk.W)
        self.search_tree.column("Name", width=360, anchor=tk.W)
        self.search_tree.column("File", width=500, anchor=tk.W)
        self.search_tree.column("Line", width=70, anchor=tk.E)

        result_scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.search_tree.yview)
        self.search_tree.configure(yscrollcommand=result_scrollbar.set)
        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        result_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.search_tree.bind("<<TreeviewSelect>>", self._show_selected_result)

        explorer_frame = ttk.LabelFrame(content_pane, text="Interactive Relationship Explorer", padding=6)
        content_pane.add(explorer_frame, minsize=360, stretch="always")

        action_frame = ttk.Frame(explorer_frame)
        action_frame.pack(fill=tk.X, pady=(0, 6))

        self.back_button = ttk.Button(action_frame, text="← Back", command=self._go_back, state=tk.DISABLED)
        self.back_button.pack(side=tk.LEFT)
        self.forward_button = ttk.Button(
            action_frame,
            text="Forward →",
            command=self._go_forward,
            state=tk.DISABLED,
        )
        self.forward_button.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(
            action_frame,
            text="Open relationship graph",
            command=self._open_current_graph,
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(
            action_frame,
            text="Click any Incoming or Outgoing relationship row to continue exploring that node.",
        ).pack(side=tk.LEFT, padx=(12, 0))

        relationship_pane = tk.PanedWindow(
            explorer_frame,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            borderwidth=0,
        )
        relationship_pane.pack(fill=tk.BOTH, expand=True)

        relationship_left = ttk.Frame(relationship_pane)
        relationship_pane.add(relationship_left, minsize=650, stretch="always")

        self.relationship_notebook = ttk.Notebook(relationship_left)
        self.relationship_notebook.pack(fill=tk.BOTH, expand=True)

        incoming_tab = ttk.Frame(self.relationship_notebook, padding=6)
        outgoing_tab = ttk.Frame(self.relationship_notebook, padding=6)
        self.relationship_notebook.add(incoming_tab, text="Incoming Relationships (0)")
        self.relationship_notebook.add(outgoing_tab, text="Outgoing Relationships (0)")

        self.incoming_tree = self._build_relationship_tree(incoming_tab)
        self.outgoing_tree = self._build_relationship_tree(outgoing_tab)
        self.incoming_tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._follow_relationship(self.incoming_tree, incoming=True),
        )
        self.outgoing_tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._follow_relationship(self.outgoing_tree, incoming=False),
        )

        details_frame = ttk.LabelFrame(relationship_pane, text="Current Node", padding=12)
        relationship_pane.add(details_frame, minsize=320, width=390, stretch="never")
        self._build_current_node_panel(details_frame)

    def _build_relationship_tree(self, parent: ttk.Frame) -> ttk.Treeview:
        columns = ("Relation", "Type", "Node", "File", "Line", "Evidence")
        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=12,
        )
        for name in columns:
            tree.heading(name, text=name)

        tree.column("Relation", width=190, anchor=tk.W)
        tree.column("Type", width=150, anchor=tk.W)
        tree.column("Node", width=330, anchor=tk.W)
        tree.column("File", width=370, anchor=tk.W)
        tree.column("Line", width=65, anchor=tk.E)
        tree.column("Evidence", width=260, anchor=tk.W)

        y_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        x_scrollbar = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        return tree

    def _build_current_node_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, textvariable=self.current_name_var, font=("Segoe UI", 13, "bold"), wraplength=340).pack(
            anchor=tk.W, fill=tk.X
        )
        ttk.Label(parent, textvariable=self.current_type_var, font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W, pady=(4, 12)
        )

        ttk.Label(parent, text="File", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(parent, textvariable=self.current_file_var, wraplength=340).pack(
            anchor=tk.W, fill=tk.X, pady=(1, 8)
        )

        ttk.Label(parent, text="Line", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(parent, textvariable=self.current_line_var).pack(anchor=tk.W, pady=(1, 8))

        ttk.Label(parent, textvariable=self.current_counts_var).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(parent, text="Details / Metadata", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        metadata_frame = ttk.Frame(parent)
        metadata_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 10))
        metadata_scrollbar = ttk.Scrollbar(metadata_frame, orient=tk.VERTICAL)
        self.current_metadata_text = tk.Text(
            metadata_frame,
            height=14,
            width=42,
            wrap=tk.WORD,
            yscrollcommand=metadata_scrollbar.set,
        )
        metadata_scrollbar.configure(command=self.current_metadata_text.yview)
        self.current_metadata_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        metadata_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.current_metadata_text.configure(state=tk.DISABLED)

        # Intentionally visual-only for now; no edit behavior is implemented.
        ttk.Button(parent, text="Edit File").pack(anchor=tk.W)

    def _build_issues_tab(self) -> None:
        ttk.Label(
            self.issues_tab,
            text=(
                "Supported files that ARE could not fully parse are listed here. "
                "The rest of the repository is still explored."
            ),
        ).pack(anchor=tk.W, pady=(0, 8))

        columns = ("Parser", "File", "Reason")
        self.issues_tree = ttk.Treeview(self.issues_tab, columns=columns, show="headings")
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
        self._clear_current_node()

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
        self._clear_current_node()

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
        if result is None or self.context is None:
            return
        self._navigate_to_node(
            result.node.id,
            add_history=self.current_node_id is not None,
            score=result.score,
            matched_text=result.matched_text,
        )

    def _navigate_to_node(
        self,
        node_id: str,
        *,
        add_history: bool = True,
        score: float | None = None,
        matched_text: str | None = None,
    ) -> None:
        if self.context is None:
            return
        node = self.context.graph.get_node(node_id)
        if node is None:
            return

        if add_history and self.current_node_id and self.current_node_id != node_id:
            self.back_history.append(self.current_node_id)
            self.forward_history.clear()

        self.current_node_id = node_id
        self.current_score = score
        self.current_matched_text = matched_text
        self._render_current_node(node)
        self._update_history_buttons()

    def _render_current_node(self, node: GraphNode) -> None:
        if self.context is None:
            return

        details = self.service.node_details(self.context.graph, node.id)
        parent_edges = tuple(details.get("parent_edges", ()))
        child_edges = tuple(details.get("child_edges", ()))

        self.current_name_var.set(node.name)
        self.current_type_var.set(node.type.value)
        self.current_file_var.set(self._relative_path(node.file_path) if node.file_path else "")
        self.current_line_var.set(str(node.line or ""))
        self.current_counts_var.set(
            f"Incoming: {len(parent_edges)}   Outgoing: {len(child_edges)}"
        )

        info_lines: list[str] = []
        if self.current_score is not None:
            info_lines.append(f"Search score: {self.current_score:.1f}")
        if self.current_matched_text:
            info_lines.append(f"Matched text: {self.current_matched_text}")
        if node.metadata:
            if info_lines:
                info_lines.append("")
            for key, value in node.metadata.items():
                info_lines.append(f"{key}: {value}")
        if not info_lines:
            info_lines.append("No additional metadata.")
        self._set_current_metadata("\n".join(info_lines))

        self._populate_relationship_tree(self.incoming_tree, parent_edges, incoming=True)
        self._populate_relationship_tree(self.outgoing_tree, child_edges, incoming=False)
        self._update_relationship_tab_titles(len(parent_edges), len(child_edges))
        self.status_var.set(
            f"Current node: {node.type.value} — {node.name} | "
            f"{len(parent_edges)} incoming / {len(child_edges)} outgoing"
        )

    def _populate_relationship_tree(
        self,
        tree: ttk.Treeview,
        edges: tuple[GraphEdge, ...],
        *,
        incoming: bool,
    ) -> None:
        if self.context is None:
            return

        for item in tree.get_children():
            tree.delete(item)

        target_map = self.incoming_targets if incoming else self.outgoing_targets
        target_map.clear()

        for index, edge in enumerate(edges):
            connected_node_id = edge.source_id if incoming else edge.target_id
            connected_node = self.context.graph.get_node(connected_node_id)
            if connected_node is None:
                continue

            iid = f"{'in' if incoming else 'out'}-{index}"
            target_map[iid] = connected_node.id
            file_name = self._relative_path(connected_node.file_path) if connected_node.file_path else ""
            tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    edge.relation.value,
                    connected_node.type.value,
                    connected_node.name,
                    file_name,
                    connected_node.line or "",
                    self._edge_evidence(edge),
                ),
            )

    def _follow_relationship(self, tree: ttk.Treeview, *, incoming: bool) -> None:
        selected = tree.selection()
        if not selected:
            return
        target_map = self.incoming_targets if incoming else self.outgoing_targets
        node_id = target_map.get(selected[0])
        if not node_id:
            return
        # Relationship navigation starts a fresh node context rather than carrying search score text.
        self._navigate_to_node(node_id, add_history=True)

    def _go_back(self) -> None:
        if not self.back_history or self.current_node_id is None:
            return
        target = self.back_history.pop()
        self.forward_history.append(self.current_node_id)
        self._navigate_to_node(target, add_history=False)

    def _go_forward(self) -> None:
        if not self.forward_history or self.current_node_id is None:
            return
        target = self.forward_history.pop()
        self.back_history.append(self.current_node_id)
        self._navigate_to_node(target, add_history=False)

    def _update_history_buttons(self) -> None:
        self.back_button.configure(state=tk.NORMAL if self.back_history else tk.DISABLED)
        self.forward_button.configure(state=tk.NORMAL if self.forward_history else tk.DISABLED)

    def _update_relationship_tab_titles(self, incoming_count: int, outgoing_count: int) -> None:
        self.relationship_notebook.tab(0, text=f"Incoming Relationships ({incoming_count})")
        self.relationship_notebook.tab(1, text=f"Outgoing Relationships ({outgoing_count})")

    def _clear_current_node(self) -> None:
        self.current_node_id = None
        self.current_score = None
        self.current_matched_text = None
        self.back_history.clear()
        self.forward_history.clear()
        self.incoming_targets.clear()
        self.outgoing_targets.clear()

        for tree in (self.incoming_tree, self.outgoing_tree):
            for item in tree.get_children():
                tree.delete(item)

        self.current_name_var.set("No node selected")
        self.current_type_var.set("")
        self.current_file_var.set("")
        self.current_line_var.set("")
        self.current_counts_var.set("Incoming: 0   Outgoing: 0")
        self._set_current_metadata("")
        self._update_relationship_tab_titles(0, 0)
        self._update_history_buttons()

    @staticmethod
    def _edge_evidence(edge: GraphEdge) -> str:
        if not edge.metadata:
            return ""
        return "; ".join(f"{key}={value}" for key, value in edge.metadata.items())

    def _open_current_graph(self) -> None:
        if self.context is None:
            messagebox.showinfo("ARE", "Scan a repository first.")
            return
        if self.current_node_id is None:
            messagebox.showinfo("ARE", "Select a search result or relationship first.")
            return

        focus_node = self.context.graph.get_node(self.current_node_id)
        if focus_node is None:
            return

        nodes, edges = relationship_neighborhood(
            self.context,
            self.current_node_id,
            max_depth=5,
            include_examples=False,
        )
        if not nodes:
            messagebox.showinfo("ARE", "No relationship graph is available for this node.")
            return

        # The HTML graph treats the first node as its initial selected/focus card.
        ordered_nodes = (focus_node, *tuple(node for node in nodes if node.id != focus_node.id))
        graph_html = build_local_graph_html(
            ordered_nodes,
            edges,
            title=f"ARE — {focus_node.name}",
        )
        safe_name = str(abs(hash(focus_node.id)))
        output_path = Path(tempfile.gettempdir()) / f"are_relationship_{safe_name}.html"
        output_path.write_text(graph_html, encoding="utf-8")
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

    def _set_current_metadata(self, value: str) -> None:
        self.current_metadata_text.configure(state=tk.NORMAL)
        self.current_metadata_text.delete("1.0", tk.END)
        if value:
            self.current_metadata_text.insert("1.0", value)
        self.current_metadata_text.configure(state=tk.DISABLED)


def main() -> None:
    """Launch ARE as a local desktop application."""

    root = tk.Tk()
    ARELocalApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
