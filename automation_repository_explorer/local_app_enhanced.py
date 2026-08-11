"""Enhanced local ARE desktop app with IDE navigation and popup Health workspace."""

from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

from automation_repository_explorer.analyzers.health_analyzer import HealthSeverity
from automation_repository_explorer.local_app_base import ARELocalApp as BaseARELocalApp
from automation_repository_explorer.local_ui.cards import CardSpec
from automation_repository_explorer.local_ui.health_presenter import (
    DEFAULT_HEALTH_PAGE_SIZE,
    severity_counts,
)
from automation_repository_explorer.local_ui.health_window import RepositoryHealthWindow
from automation_repository_explorer.local_ui.ide_launcher import IntelliJLauncher
from automation_repository_explorer.local_ui.relationship_presenter import build_relationship_view


class ARELocalApp(BaseARELocalApp):
    """Local ARE app with modular Repository Health and IntelliJ source navigation."""

    def __init__(self, root: tk.Tk) -> None:
        self.ide_launcher = IntelliJLauncher()
        self.health_window: RepositoryHealthWindow | None = None
        self.file_targets: dict[str, Path] = {}
        self.health_summary_var = tk.StringVar(
            master=root,
            value="Scan a repository to generate Repository Health.",
        )
        super().__init__(root)

    def _build_files_tab(self) -> None:
        controls = ttk.Frame(self.files_tab)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(
            controls,
            text="Open selected file",
            command=self._open_selected_file,
        ).pack(side=tk.LEFT)
        ttk.Label(
            controls,
            text="Double-click any file to open it in the scanned IntelliJ project.",
        ).pack(side=tk.LEFT, padx=(10, 0))

        table_frame = ttk.Frame(self.files_tab)
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("Type", "Path", "Size")
        self.files_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for name in columns:
            self.files_tree.heading(name, text=name)
        self.files_tree.column("Type", width=90, anchor=tk.W)
        self.files_tree.column("Path", width=800, anchor=tk.W)
        self.files_tree.column("Size", width=120, anchor=tk.E)
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=scrollbar.set)
        self.files_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.files_tree.bind("<Double-1>", lambda _event: self._open_selected_file())

    def _build_current_node_panel(self, parent: ttk.Frame) -> None:
        super()._build_current_node_panel(parent)
        self.open_current_file_button = ttk.Button(
            parent,
            text="Open File in IntelliJ",
            command=self._open_current_node_file,
            state=tk.DISABLED,
        )
        self.open_current_file_button.pack(anchor=tk.W, pady=(6, 0))

    def _build_health_tab(self) -> None:
        # Build the stable Health widgets used by the base app's scan lifecycle, then keep them
        # off-screen. The visible tab is intentionally compact; the full workspace lives in a
        # dedicated RepositoryHealthWindow.
        BaseARELocalApp._build_health_tab(self)
        for child in self.health_tab.winfo_children():
            child.pack_forget()

        container = ttk.Frame(self.health_tab, padding=18)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text="Repository Health",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            container,
            text=(
                "Repository Health opens in its own workspace so large finding sets do not crowd "
                "the main ARE window. The Health window contains All, High, Medium and Review "
                "filters, grouped findings, evidence, Explore Node and Open File in IntelliJ."
            ),
            wraplength=1100,
        ).pack(anchor=tk.W, fill=tk.X, pady=(5, 16))

        summary_frame = ttk.LabelFrame(container, text="Latest Scan", padding=14)
        summary_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(
            summary_frame,
            textvariable=self.health_summary_var,
            font=("Segoe UI", 11, "bold"),
            wraplength=1100,
        ).pack(anchor=tk.W, fill=tk.X)

        self.health_window_button = ttk.Button(
            container,
            text="Open Repository Health",
            command=self._show_repository_health,
            state=tk.DISABLED,
        )
        self.health_window_button.pack(anchor=tk.W)

    def _clear_scan_views(self) -> None:
        if self.health_window is not None and self.health_window.is_open:
            self.health_window.close()
        self.health_window = None
        self.file_targets.clear()
        self.health_summary_var.set("Scan a repository to generate Repository Health.")
        if hasattr(self, "health_window_button"):
            self.health_window_button.configure(state=tk.DISABLED)
        super()._clear_scan_views()

    def _populate_files(self) -> None:
        assert self.context is not None
        self.file_targets.clear()
        for index, repository_file in enumerate(self.context.index.files):
            iid = f"file-{index}"
            self.file_targets[iid] = repository_file.path
            self.files_tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    repository_file.extension,
                    self._relative_path(repository_file.path),
                    repository_file.size_bytes,
                ),
            )

    def _populate_health(self) -> None:
        assert self.context is not None
        # Keep the base Health state valid for compatibility, even though its widgets are hidden.
        BaseARELocalApp._populate_health(self)
        counts = severity_counts(self.context.health)
        issue_types = len(self.context.health.count_by_check())
        self.health_summary_var.set(
            f"Total {self.context.health.total} findings • "
            f"High {counts.get(HealthSeverity.HIGH, 0)} • "
            f"Medium {counts.get(HealthSeverity.MEDIUM, 0)} • "
            f"Review {counts.get(HealthSeverity.REVIEW, 0)} • "
            f"{issue_types} issue type(s)"
        )
        self.health_window_button.configure(state=tk.NORMAL)

    def _render_current_node(self, node, entry) -> None:  # type: ignore[no-untyped-def]
        super()._render_current_node(node, entry)
        if self.context is None:
            return

        self.open_current_file_button.configure(
            state=tk.NORMAL if node.file_path is not None else tk.DISABLED
        )
        relationship_view = build_relationship_view(
            self.context.graph,
            node.id,
            path_formatter=self._relative_path,
        )
        if relationship_view is None:
            return

        self.incoming_cards.set_cards(
            tuple(self._relationship_card_spec(card) for card in relationship_view.incoming),
            on_open=lambda card_id: self._visit_node(card_id, source="Incoming relationship"),
            on_secondary=self._open_node_file,
            empty_text="No incoming relationships. Nothing in the analyzed graph points to this node.",
        )
        self.outgoing_cards.set_cards(
            tuple(self._relationship_card_spec(card) for card in relationship_view.outgoing),
            on_open=lambda card_id: self._visit_node(card_id, source="Outgoing relationship"),
            on_secondary=self._open_node_file,
            empty_text="No outgoing relationships. This is currently an end node in the analyzed graph.",
        )

    @staticmethod
    def _relationship_card_spec(card):  # type: ignore[no-untyped-def]
        spec = BaseARELocalApp._relationship_card_spec(card)
        return CardSpec(
            id=spec.id,
            eyebrow=spec.eyebrow,
            title=spec.title,
            subtitle=spec.subtitle,
            detail=spec.detail,
            action_label=spec.action_label,
            secondary_action_label="Open File" if card.location else "",
        )

    def _clear_current_node(self) -> None:
        super()._clear_current_node()
        if hasattr(self, "open_current_file_button"):
            self.open_current_file_button.configure(state=tk.DISABLED)

    def _show_repository_health(self) -> None:
        if self.context is None:
            messagebox.showinfo("ARE", "Scan a repository first.")
            return
        if self.health_window is not None and self.health_window.is_open:
            self.health_window.show()
            return

        self.health_window = RepositoryHealthWindow(
            self.root,
            report=self.context.health,
            graph=self.context.graph,
            path_formatter=self._relative_path,
            on_explore=self._explore_health_node,
            on_open_file=self._open_node_file,
            page_size=DEFAULT_HEALTH_PAGE_SIZE,
            on_close=self._health_window_closed,
        )

    def _health_window_closed(self) -> None:
        self.health_window = None

    def _explore_health_node(self, node_id: str, source: str) -> None:
        self.notebook.select(self.search_tab)
        self._visit_node(node_id, source=source)
        self.root.lift()

    def _open_current_node_file(self) -> None:
        current = self.navigation.current
        if current is not None:
            self._open_node_file(current.node_id)

    def _open_node_file(self, node_id: str) -> None:
        if self.context is None:
            return
        node = self.context.graph.get_node(node_id)
        if node is None or node.file_path is None:
            messagebox.showinfo("Open File", "This node does not have a source file.")
            return
        self._open_file_in_idea(node.file_path, line=node.line)

    def _open_selected_file(self) -> None:
        selected = self.files_tree.selection()
        if not selected:
            messagebox.showinfo("Open File", "Select a file first.")
            return
        file_path = self.file_targets.get(selected[0])
        if file_path is not None:
            self._open_file_in_idea(file_path)

    def _open_file_in_idea(self, file_path: Path, *, line: int | None = None) -> None:
        if self.context is None:
            return
        result = self.ide_launcher.open_file(
            file_path,
            line=line,
            project_root=self.context.index.root,
        )
        if result.success:
            self.status_var.set(result.message)
        else:
            messagebox.showerror("Open File in IntelliJ", result.message)


def main() -> None:
    """Launch the enhanced ARE desktop application."""

    root = tk.Tk()
    ARELocalApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
