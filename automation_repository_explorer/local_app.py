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

from automation_repository_explorer.analyzers.health_analyzer import HealthSeverity
from automation_repository_explorer.local_graph import build_local_graph_html
from automation_repository_explorer.local_project_flow import build_local_project_flow_html
from automation_repository_explorer.local_ui.cards import (
    CardSpec,
    ScrollableCardList,
    configure_local_styles,
)
from automation_repository_explorer.local_ui.health_presenter import (
    DEFAULT_HEALTH_PAGE_SIZE,
    HealthIssueGroup,
    group_health_findings,
    page_health_group,
    severity_counts,
)
from automation_repository_explorer.local_ui.navigation import (
    NodeNavigationEntry,
    NodeNavigationHistory,
)
from automation_repository_explorer.local_ui.relationship_presenter import (
    RelationshipCard,
    build_relationship_view,
)
from automation_repository_explorer.models.graph import GraphNode, NodeType
from automation_repository_explorer.project_flow import (
    ProjectFlowModel,
    build_project_flow_model,
    project_flow_category_counts,
)
from automation_repository_explorer.search.search_engine import SearchMode, SearchResult
from automation_repository_explorer.services.explorer_service import ExplorationContext, ExplorerService
from automation_repository_explorer.ui.flow_graph import forward_relationship_neighborhood


class ARELocalApp:
    """Tkinter desktop UI backed by ARE analysis and reusable local UI presenters."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.service = ExplorerService()
        self.context: ExplorationContext | None = None
        self.project_flow_model: ProjectFlowModel | None = None
        self.search_results: tuple[SearchResult, ...] = tuple()
        self.scan_thread: threading.Thread | None = None

        self.navigation = NodeNavigationHistory()
        self.health_filter: HealthSeverity | None = None
        self.health_groups: tuple[HealthIssueGroup, ...] = tuple()
        self.health_groups_by_id: dict[str, HealthIssueGroup] = {}
        self.health_selected_group_id: str | None = None
        self.health_finding_targets: dict[str, str] = {}
        self.health_page_index = 0
        self.health_filter_buttons: dict[HealthSeverity | None, ttk.Button] = {}

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
        self.navigation_status_var = tk.StringVar(value="No relationship navigation yet.")

        self.health_total_var = tk.StringVar(value="Health findings: 0")
        self.health_group_title_var = tk.StringVar(value="Select a severity to review findings.")
        self.health_group_description_var = tk.StringVar(value="")
        self.health_page_var = tk.StringVar(value="")
        self.project_flow_status_var = tk.StringVar(
            value="Scan a repository to build complete project flow."
        )

        self.root.title("Automation Repository Explorer")
        self.root.geometry("1540x960")
        self.root.minsize(1180, 760)
        configure_local_styles(ttk.Style(self.root))
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
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )
        ttk.Button(repository_frame, text="Browse", command=self._browse_repository).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )
        self.scan_button = ttk.Button(
            repository_frame,
            text="Scan repository",
            command=self._start_scan,
        )
        self.scan_button.pack(side=tk.LEFT, padx=(8, 0))

        progress_frame = ttk.Frame(root_frame)
        progress_frame.pack(fill=tk.X, pady=(10, 8))
        ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        ).pack(fill=tk.X)
        ttk.Label(progress_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=(4, 0))

        self.notebook = ttk.Notebook(root_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.summary_tab = ttk.Frame(self.notebook, padding=10)
        self.project_flow_tab = ttk.Frame(self.notebook, padding=10)
        self.files_tab = ttk.Frame(self.notebook, padding=10)
        self.search_tab = ttk.Frame(self.notebook, padding=10)
        self.health_tab = ttk.Frame(self.notebook, padding=10)
        self.issues_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.summary_tab, text="Summary")
        self.notebook.add(self.project_flow_tab, text="Project Flow")
        self.notebook.add(self.files_tab, text="Files")
        self.notebook.add(self.search_tab, text="Search & Relationships")
        self.notebook.add(self.health_tab, text="Repository Health")
        self.notebook.add(self.issues_tab, text="Scan Issues")

        self._build_summary_tab()
        self._build_project_flow_tab()
        self._build_files_tab()
        self._build_search_tab()
        self._build_health_tab()
        self._build_issues_tab()

    def _build_summary_tab(self) -> None:
        self.summary_tree = ttk.Treeview(
            self.summary_tab,
            columns=("Metric", "Value"),
            show="headings",
            height=16,
        )
        self.summary_tree.heading("Metric", text="Metric")
        self.summary_tree.heading("Value", text="Value")
        self.summary_tree.column("Metric", width=320, anchor=tk.W)
        self.summary_tree.column("Value", width=180, anchor=tk.E)
        self.summary_tree.pack(fill=tk.BOTH, expand=True)

    def _build_project_flow_tab(self) -> None:
        ttk.Label(
            self.project_flow_tab,
            text=(
                "Complete project navigation without graph noise. Start at Project, then click through "
                "file categories, folders, files, and real automation relationships. Only the current "
                "card and its direct next level are shown."
            ),
            wraplength=1200,
        ).pack(anchor=tk.W, pady=(0, 8))
        ttk.Label(
            self.project_flow_tab,
            textvariable=self.project_flow_status_var,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W, pady=(0, 10))

        action_frame = ttk.Frame(self.project_flow_tab)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        self.project_flow_button = ttk.Button(
            action_frame,
            text="Open complete project flow",
            command=self._open_project_flow,
            state=tk.DISABLED,
        )
        self.project_flow_button.pack(side=tk.LEFT)
        ttk.Label(
            action_frame,
            text="Local HTML only — no server, no upload. Edit File remains visual-only.",
        ).pack(side=tk.LEFT, padx=(10, 0))

        summary_frame = ttk.LabelFrame(
            self.project_flow_tab,
            text="Project Flow Coverage",
            padding=8,
        )
        summary_frame.pack(fill=tk.BOTH, expand=True)
        self.project_flow_tree = ttk.Treeview(
            summary_frame,
            columns=("Section", "Count"),
            show="headings",
        )
        self.project_flow_tree.heading("Section", text="Section")
        self.project_flow_tree.heading("Count", text="Indexed files")
        self.project_flow_tree.column("Section", width=520, anchor=tk.W)
        self.project_flow_tree.column("Count", width=160, anchor=tk.E)
        self.project_flow_tree.pack(fill=tk.BOTH, expand=True)

    def _build_files_tab(self) -> None:
        columns = ("Type", "Path", "Size")
        self.files_tree = ttk.Treeview(self.files_tab, columns=columns, show="headings")
        for name in columns:
            self.files_tree.heading(name, text=name)
        self.files_tree.column("Type", width=90, anchor=tk.W)
        self.files_tree.column("Path", width=800, anchor=tk.W)
        self.files_tree.column("Size", width=120, anchor=tk.E)
        scrollbar = ttk.Scrollbar(
            self.files_tab,
            orient=tk.VERTICAL,
            command=self.files_tree.yview,
        )
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
        content_pane.add(result_frame, minsize=155, stretch="always")
        columns = ("Score", "Type", "Name", "File", "Line")
        self.search_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=7,
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

        explorer_frame = ttk.LabelFrame(
            content_pane,
            text="Interactive Relationship Explorer",
            padding=8,
        )
        content_pane.add(explorer_frame, minsize=430, stretch="always")

        action_frame = ttk.Frame(explorer_frame)
        action_frame.pack(fill=tk.X, pady=(0, 6))
        self.back_button = ttk.Button(
            action_frame,
            text="← Back",
            command=self._go_back,
            state=tk.DISABLED,
        )
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
            textvariable=self.navigation_status_var,
        ).pack(side=tk.LEFT, padx=(14, 0))

        ttk.Label(
            explorer_frame,
            text=(
                "Read the explorer left → center → right. Incoming cards point into the current node; "
                "Outgoing cards are relationships leaving it. Click any card to make that node current."
            ),
            wraplength=1300,
        ).pack(anchor=tk.W, fill=tk.X, pady=(0, 8))

        relationship_pane = tk.PanedWindow(
            explorer_frame,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            borderwidth=0,
        )
        relationship_pane.pack(fill=tk.BOTH, expand=True)

        incoming_frame = ttk.LabelFrame(
            relationship_pane,
            text="← Incoming",
            padding=8,
        )
        current_frame = ttk.LabelFrame(
            relationship_pane,
            text="Current Node",
            padding=12,
        )
        outgoing_frame = ttk.LabelFrame(
            relationship_pane,
            text="Outgoing →",
            padding=8,
        )
        relationship_pane.add(incoming_frame, minsize=320, stretch="always")
        relationship_pane.add(current_frame, minsize=360, stretch="always")
        relationship_pane.add(outgoing_frame, minsize=320, stretch="always")

        ttk.Label(
            incoming_frame,
            text="Nodes whose relationships point to the current node.",
            wraplength=380,
        ).pack(anchor=tk.W, fill=tk.X, pady=(0, 6))
        self.incoming_cards = ScrollableCardList(incoming_frame)
        self.incoming_cards.pack(fill=tk.BOTH, expand=True)

        self._build_current_node_panel(current_frame)

        ttk.Label(
            outgoing_frame,
            text="Nodes reached directly from the current node.",
            wraplength=380,
        ).pack(anchor=tk.W, fill=tk.X, pady=(0, 6))
        self.outgoing_cards = ScrollableCardList(outgoing_frame)
        self.outgoing_cards.pack(fill=tk.BOTH, expand=True)

    def _build_current_node_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            textvariable=self.current_name_var,
            font=("Segoe UI", 14, "bold"),
            wraplength=410,
        ).pack(anchor=tk.W, fill=tk.X)
        ttk.Label(
            parent,
            textvariable=self.current_type_var,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(4, 12))

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        ttk.Label(parent, text="File", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(
            parent,
            textvariable=self.current_file_var,
            wraplength=410,
        ).pack(anchor=tk.W, fill=tk.X, pady=(1, 8))
        ttk.Label(parent, text="Line", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(parent, textvariable=self.current_line_var).pack(anchor=tk.W, pady=(1, 8))
        ttk.Label(
            parent,
            textvariable=self.current_counts_var,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(
            parent,
            text="Details / Metadata",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor=tk.W)
        metadata_frame = ttk.Frame(parent)
        metadata_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 10))
        metadata_scrollbar = ttk.Scrollbar(metadata_frame, orient=tk.VERTICAL)
        self.current_metadata_text = tk.Text(
            metadata_frame,
            height=12,
            width=42,
            wrap=tk.WORD,
            yscrollcommand=metadata_scrollbar.set,
        )
        metadata_scrollbar.configure(command=self.current_metadata_text.yview)
        self.current_metadata_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        metadata_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.current_metadata_text.configure(state=tk.DISABLED)
        ttk.Button(parent, text="Edit File", state=tk.DISABLED).pack(anchor=tk.W)

    def _build_health_tab(self) -> None:
        ttk.Label(
            self.health_tab,
            text=(
                "Health findings are grouped by severity and check type. Click a severity, then an issue "
                "group, then any finding card to inspect the exact node and evidence. Review findings are "
                "investigation candidates, not deletion recommendations."
            ),
            wraplength=1300,
        ).pack(anchor=tk.W, pady=(0, 8))

        self.health_filter_frame = ttk.Frame(self.health_tab)
        self.health_filter_frame.pack(fill=tk.X, pady=(0, 8))
        self._build_health_filter_buttons()

        ttk.Label(
            self.health_tab,
            textvariable=self.health_total_var,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        health_pane = tk.PanedWindow(
            self.health_tab,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            borderwidth=0,
        )
        health_pane.pack(fill=tk.BOTH, expand=True)

        groups_frame = ttk.LabelFrame(health_pane, text="Grouped Issues", padding=8)
        findings_frame = ttk.LabelFrame(health_pane, text="Finding Details", padding=8)
        health_pane.add(groups_frame, minsize=360, stretch="always")
        health_pane.add(findings_frame, minsize=560, stretch="always")

        ttk.Label(
            groups_frame,
            text="Same health checks are grouped together so large counts stay understandable.",
            wraplength=440,
        ).pack(anchor=tk.W, fill=tk.X, pady=(0, 6))
        self.health_group_cards = ScrollableCardList(groups_frame)
        self.health_group_cards.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            findings_frame,
            textvariable=self.health_group_title_var,
            style="ARE.SectionTitle.TLabel",
            wraplength=720,
        ).pack(anchor=tk.W, fill=tk.X)
        ttk.Label(
            findings_frame,
            textvariable=self.health_group_description_var,
            wraplength=720,
        ).pack(anchor=tk.W, fill=tk.X, pady=(3, 8))

        page_frame = ttk.Frame(findings_frame)
        page_frame.pack(fill=tk.X, pady=(0, 6))
        self.health_previous_button = ttk.Button(
            page_frame,
            text="← Previous 100",
            command=self._previous_health_page,
            state=tk.DISABLED,
        )
        self.health_previous_button.pack(side=tk.LEFT)
        self.health_next_button = ttk.Button(
            page_frame,
            text="Next 100 →",
            command=self._next_health_page,
            state=tk.DISABLED,
        )
        self.health_next_button.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(page_frame, textvariable=self.health_page_var).pack(side=tk.LEFT, padx=(12, 0))

        self.health_finding_cards = ScrollableCardList(findings_frame)
        self.health_finding_cards.pack(fill=tk.BOTH, expand=True)

    def _build_health_filter_buttons(self) -> None:
        for child in self.health_filter_frame.winfo_children():
            child.destroy()
        self.health_filter_buttons.clear()

        all_button = ttk.Button(
            self.health_filter_frame,
            text="All 0",
            style="ARE.SelectedFilter.TButton",
            command=lambda: self._apply_health_filter(None),
        )
        all_button.pack(side=tk.LEFT)
        self.health_filter_buttons[None] = all_button

        for severity in HealthSeverity:
            button = ttk.Button(
                self.health_filter_frame,
                text=f"{severity.value} 0",
                style="ARE.Filter.TButton",
                command=lambda selected=severity: self._apply_health_filter(selected),
            )
            button.pack(side=tk.LEFT, padx=(6, 0))
            self.health_filter_buttons[severity] = button

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
        scrollbar = ttk.Scrollbar(
            self.issues_tab,
            orient=tk.VERTICAL,
            command=self.issues_tree.yview,
        )
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
            context = self.service.explore(
                repository_path,
                progress_callback=progress,
            )
            project_flow_model = build_project_flow_model(context)
        except Exception as exc:  # noqa: BLE001 - UI must surface scan failures cleanly
            self.root.after(0, self._scan_failed, str(exc))
            return
        self.root.after(0, self._scan_finished, context, project_flow_model)

    def _update_progress(self, percent: int, message: str) -> None:
        safe_percent = max(0, min(int(percent), 100))
        self.progress_var.set(safe_percent)
        self.status_var.set(f"{safe_percent}% — {message}")

    def _scan_failed(self, message: str) -> None:
        self.scan_button.configure(state=tk.NORMAL)
        self.status_var.set("Scan failed.")
        messagebox.showerror("ARE scan failed", message)

    def _scan_finished(
        self,
        context: ExplorationContext,
        project_flow_model: ProjectFlowModel,
    ) -> None:
        self.context = context
        self.project_flow_model = project_flow_model
        self.scan_button.configure(state=tk.NORMAL)
        self.project_flow_button.configure(state=tk.NORMAL)
        self.progress_var.set(100)

        issue_count = len(context.index.parse_issues)
        health_count = context.health.total
        if issue_count:
            self.status_var.set(
                f"100% — Scan complete: {health_count} health finding(s), "
                f"{issue_count} parse issue(s)."
            )
        else:
            self.status_var.set(f"100% — Scan complete: {health_count} health finding(s).")

        self._populate_summary()
        self._populate_project_flow_summary()
        self._populate_files()
        self._populate_health()
        self._populate_issues()

    def _clear_scan_views(self) -> None:
        self.context = None
        self.project_flow_model = None
        self.search_results = tuple()
        self.project_flow_button.configure(state=tk.DISABLED)
        self.project_flow_status_var.set("Scan a repository to build complete project flow.")

        for tree in (
            self.summary_tree,
            self.project_flow_tree,
            self.files_tree,
            self.search_tree,
            self.issues_tree,
        ):
            for item in tree.get_children():
                tree.delete(item)

        self.health_groups = tuple()
        self.health_groups_by_id.clear()
        self.health_selected_group_id = None
        self.health_finding_targets.clear()
        self.health_page_index = 0
        self.health_total_var.set("Health findings: 0")
        self.health_group_title_var.set("Select a severity to review findings.")
        self.health_group_description_var.set("")
        self.health_page_var.set("")
        self.health_group_cards.clear()
        self.health_finding_cards.clear()
        self._update_health_filter_button_labels()
        self._update_health_page_buttons(False, False)
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
            ("Health findings", self.context.health.total),
            ("Parse issues", summary.parse_issues),
        )
        for metric, value in rows:
            self.summary_tree.insert("", tk.END, values=(metric, value))

    def _populate_project_flow_summary(self) -> None:
        assert self.project_flow_model is not None
        counts = project_flow_category_counts(self.project_flow_model)
        total = sum(count for _label, count in counts)
        self.project_flow_status_var.set(
            f"Complete project flow ready: {total} indexed file(s) across {len(counts)} section(s)."
        )
        for label, count in counts:
            self.project_flow_tree.insert("", tk.END, values=(label, count))

    def _populate_files(self) -> None:
        assert self.context is not None
        for repository_file in self.context.index.files:
            self.files_tree.insert(
                "",
                tk.END,
                values=(
                    repository_file.extension,
                    self._relative_path(repository_file.path),
                    repository_file.size_bytes,
                ),
            )

    def _populate_health(self) -> None:
        assert self.context is not None
        self.health_filter = None
        self._update_health_filter_button_labels()
        self._apply_health_filter(None)

    def _update_health_filter_button_labels(self) -> None:
        if self.context is None:
            total = 0
            counts = {severity: 0 for severity in HealthSeverity}
        else:
            total = self.context.health.total
            counts = severity_counts(self.context.health)

        self.health_filter_buttons[None].configure(text=f"All {total}")
        for severity, button in self.health_filter_buttons.items():
            if severity is None:
                continue
            button.configure(text=f"{severity.value} {counts.get(severity, 0)}")

    def _apply_health_filter(self, severity: HealthSeverity | None) -> None:
        if self.context is None:
            return

        self.health_filter = severity
        self.health_groups = group_health_findings(self.context.health, severity=severity)
        self.health_groups_by_id = {group.id: group for group in self.health_groups}
        self.health_selected_group_id = self.health_groups[0].id if self.health_groups else None
        self.health_page_index = 0

        for filter_value, button in self.health_filter_buttons.items():
            button.configure(
                style=(
                    "ARE.SelectedFilter.TButton"
                    if filter_value == severity
                    else "ARE.Filter.TButton"
                )
            )

        selected_count = sum(group.count for group in self.health_groups)
        filter_name = severity.value if severity is not None else "All severities"
        self.health_total_var.set(
            f"{filter_name}: {selected_count} finding(s) grouped into {len(self.health_groups)} issue type(s)."
        )
        self._render_health_groups()
        self._render_health_findings()

    def _render_health_groups(self) -> None:
        cards = tuple(
            CardSpec(
                id=group.id,
                eyebrow=f"{group.severity.value} • {group.count} finding(s)",
                title=group.check_name,
                detail=group.description,
                action_label="Show findings",
            )
            for group in self.health_groups
        )
        self.health_group_cards.set_cards(
            cards,
            on_open=self._select_health_group,
            selected_id=self.health_selected_group_id,
            empty_text="No health findings in this severity.",
        )

    def _select_health_group(self, group_id: str) -> None:
        if group_id not in self.health_groups_by_id:
            return
        self.health_selected_group_id = group_id
        self.health_page_index = 0
        self._render_health_groups()
        self._render_health_findings()

    def _render_health_findings(self) -> None:
        if self.context is None or self.health_selected_group_id is None:
            self.health_group_title_var.set("No issue group selected.")
            self.health_group_description_var.set("")
            self.health_page_var.set("")
            self.health_finding_targets.clear()
            self.health_finding_cards.set_cards(
                tuple(),
                on_open=lambda _card_id: None,
                empty_text="No findings to display.",
            )
            self._update_health_page_buttons(False, False)
            return

        group = self.health_groups_by_id[self.health_selected_group_id]
        page = page_health_group(
            group,
            self.context.graph,
            page_index=self.health_page_index,
            page_size=DEFAULT_HEALTH_PAGE_SIZE,
            path_formatter=self._relative_path,
        )
        self.health_page_index = page.page_index
        self.health_group_title_var.set(f"{group.check_name} — {group.count} finding(s)")
        self.health_group_description_var.set(f"What ARE detected: {group.description}")

        start = page.page_index * DEFAULT_HEALTH_PAGE_SIZE + 1 if page.total else 0
        end = start + len(page.cards) - 1 if page.cards else 0
        self.health_page_var.set(
            f"Showing {start}-{end} of {page.total} • Page {page.page_index + 1}/{page.page_count}"
        )
        self._update_health_page_buttons(page.can_previous, page.can_next)

        self.health_finding_targets = {card.id: card.node_id for card in page.cards}
        cards = tuple(
            CardSpec(
                id=card.id,
                eyebrow=f"{card.confidence} confidence • {card.node_type}",
                title=card.name,
                subtitle=card.location,
                detail=card.message,
                action_label="Explore node",
            )
            for card in page.cards
        )
        self.health_finding_cards.set_cards(
            cards,
            on_open=self._open_health_finding_card,
            empty_text="No resolvable nodes were available for this finding page.",
        )

    def _previous_health_page(self) -> None:
        if self.health_page_index <= 0:
            return
        self.health_page_index -= 1
        self._render_health_findings()

    def _next_health_page(self) -> None:
        if self.context is None or self.health_selected_group_id is None:
            return
        group = self.health_groups_by_id[self.health_selected_group_id]
        page = page_health_group(
            group,
            self.context.graph,
            page_index=self.health_page_index,
            page_size=DEFAULT_HEALTH_PAGE_SIZE,
            path_formatter=self._relative_path,
        )
        if not page.can_next:
            return
        self.health_page_index += 1
        self._render_health_findings()

    def _update_health_page_buttons(self, can_previous: bool, can_next: bool) -> None:
        self.health_previous_button.configure(state=tk.NORMAL if can_previous else tk.DISABLED)
        self.health_next_button.configure(state=tk.NORMAL if can_next else tk.DISABLED)

    def _open_health_finding_card(self, card_id: str) -> None:
        node_id = self.health_finding_targets.get(card_id)
        if not node_id:
            return
        group = self.health_groups_by_id.get(self.health_selected_group_id or "")
        source = f"Health: {group.check_name}" if group is not None else "Health"
        self.notebook.select(self.search_tab)
        self._visit_node(node_id, source=source)

    def _populate_issues(self) -> None:
        assert self.context is not None
        for issue in self.context.index.parse_issues:
            self.issues_tree.insert(
                "",
                tk.END,
                values=(
                    issue.parser_name,
                    self._relative_path(issue.file_path),
                    issue.message,
                ),
            )

    def _open_project_flow(self) -> None:
        if self.context is None or self.project_flow_model is None:
            messagebox.showinfo("ARE", "Scan a repository first.")
            return
        graph_html = build_local_project_flow_html(
            self.project_flow_model,
            title=f"ARE Project Flow — {self.context.index.root.name}",
        )
        safe_name = str(abs(hash(str(self.context.index.root))))
        output_path = Path(tempfile.gettempdir()) / f"are_project_flow_{safe_name}.html"
        output_path.write_text(graph_html, encoding="utf-8")
        webbrowser.open(output_path.resolve().as_uri())

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
            self.search_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    f"{result.score:.1f}",
                    node.type.value,
                    node.name,
                    self._relative_path(node.file_path) if node.file_path else "",
                    node.line or "",
                ),
            )
        self.status_var.set(f"Search returned {len(self.search_results)} result(s).")

    def _show_selected_result(self, _event: object | None = None) -> None:
        result = self._selected_search_result()
        if result is None or self.context is None:
            return
        self._visit_node(
            result.node.id,
            score=result.score,
            matched_text=result.matched_text,
            source="Search",
        )

    def _visit_node(
        self,
        node_id: str,
        *,
        score: float | None = None,
        matched_text: str | None = None,
        source: str | None = None,
    ) -> None:
        if self.context is None or self.context.graph.get_node(node_id) is None:
            return
        entry = self.navigation.visit(
            NodeNavigationEntry(
                node_id=node_id,
                score=score,
                matched_text=matched_text,
                source=source,
            )
        )
        self._render_navigation_entry(entry)

    def _render_navigation_entry(self, entry: NodeNavigationEntry) -> None:
        if self.context is None:
            return
        node = self.context.graph.get_node(entry.node_id)
        if node is None:
            return
        self._render_current_node(node, entry)
        self._update_history_buttons()

    def _render_current_node(self, node: GraphNode, entry: NodeNavigationEntry) -> None:
        if self.context is None:
            return
        relationship_view = build_relationship_view(
            self.context.graph,
            node.id,
            path_formatter=self._relative_path,
        )
        if relationship_view is None:
            return

        self.current_name_var.set(node.name)
        self.current_type_var.set(node.type.value)
        self.current_file_var.set(self._relative_path(node.file_path) if node.file_path else "")
        self.current_line_var.set(str(node.line or ""))
        self.current_counts_var.set(
            f"Incoming: {len(relationship_view.incoming)}   •   Outgoing: {len(relationship_view.outgoing)}"
        )

        info_lines: list[str] = []
        if entry.source:
            info_lines.append(f"Opened from: {entry.source}")
        if entry.score is not None:
            info_lines.append(f"Search score: {entry.score:.1f}")
        if entry.matched_text:
            info_lines.append(f"Matched text: {entry.matched_text}")
        if node.metadata:
            if info_lines:
                info_lines.append("")
            info_lines.extend(f"{key}: {value}" for key, value in node.metadata.items())
        self._set_current_metadata(
            "\n".join(info_lines) if info_lines else "No additional metadata."
        )

        self.incoming_cards.set_cards(
            tuple(self._relationship_card_spec(card) for card in relationship_view.incoming),
            on_open=lambda card_id: self._visit_node(card_id, source="Incoming relationship"),
            empty_text="No incoming relationships. Nothing in the analyzed graph points to this node.",
        )
        self.outgoing_cards.set_cards(
            tuple(self._relationship_card_spec(card) for card in relationship_view.outgoing),
            on_open=lambda card_id: self._visit_node(card_id, source="Outgoing relationship"),
            empty_text="No outgoing relationships. This is currently an end node in the analyzed graph.",
        )

        self.status_var.set(
            f"Current node: {node.type.value} — {node.name} | "
            f"{len(relationship_view.incoming)} incoming / {len(relationship_view.outgoing)} outgoing"
        )

    @staticmethod
    def _relationship_card_spec(card: RelationshipCard) -> CardSpec:
        relation_label = card.relation.replace("_", " ").title()
        return CardSpec(
            id=card.node_id,
            eyebrow=f"{relation_label} • {card.node_type}",
            title=card.name,
            subtitle=card.location,
            detail=card.evidence,
            action_label="Make current",
        )

    def _go_back(self) -> None:
        entry = self.navigation.back()
        if entry is not None:
            self._render_navigation_entry(entry)
        else:
            self._update_history_buttons()

    def _go_forward(self) -> None:
        entry = self.navigation.forward()
        if entry is not None:
            self._render_navigation_entry(entry)
        else:
            self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        self.back_button.configure(
            state=tk.NORMAL if self.navigation.can_back else tk.DISABLED,
        )
        self.forward_button.configure(
            state=tk.NORMAL if self.navigation.can_forward else tk.DISABLED,
        )
        if self.navigation.current is None:
            self.navigation_status_var.set("No relationship navigation yet.")
            return
        source = self.navigation.current.source or "Relationship Explorer"
        self.navigation_status_var.set(
            f"{source} • Back {self.navigation.back_count} • Forward {self.navigation.forward_count}"
        )

    def _clear_current_node(self) -> None:
        self.navigation.reset()
        self.incoming_cards.clear()
        self.outgoing_cards.clear()
        self.current_name_var.set("No node selected")
        self.current_type_var.set("")
        self.current_file_var.set("")
        self.current_line_var.set("")
        self.current_counts_var.set("Incoming: 0   Outgoing: 0")
        self._set_current_metadata("")
        self._update_history_buttons()

    def _open_current_graph(self) -> None:
        if self.context is None:
            messagebox.showinfo("ARE", "Scan a repository first.")
            return
        current = self.navigation.current
        if current is None:
            messagebox.showinfo(
                "ARE",
                "Select a search result, health finding, or relationship first.",
            )
            return
        focus_node = self.context.graph.get_node(current.node_id)
        if focus_node is None:
            return

        nodes, edges = forward_relationship_neighborhood(
            self.context,
            current.node_id,
            max_depth=14,
            include_examples=False,
            max_nodes=1500,
        )
        if not nodes:
            messagebox.showinfo("ARE", "No relationship graph is available for this node.")
            return
        ordered_nodes = (
            focus_node,
            *tuple(node for node in nodes if node.id != focus_node.id),
        )
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
