"""Enhanced local ARE desktop app with separate Review workflow and IDE navigation."""

from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

from automation_repository_explorer.analyzers.health_analyzer import HealthSeverity
from automation_repository_explorer.local_app_base import ARELocalApp as BaseARELocalApp
from automation_repository_explorer.local_ui.cards import CardSpec, ScrollableCardList
from automation_repository_explorer.local_ui.health_presenter import (
    DEFAULT_HEALTH_PAGE_SIZE,
    group_health_findings,
    page_health_group,
    severity_counts,
)
from automation_repository_explorer.local_ui.health_review_window import HealthReviewWindow
from automation_repository_explorer.local_ui.ide_launcher import IntelliJLauncher
from automation_repository_explorer.local_ui.relationship_presenter import build_relationship_view


PRIMARY_HEALTH_SEVERITIES = (HealthSeverity.HIGH, HealthSeverity.MEDIUM)


class ARELocalApp(BaseARELocalApp):
    """Local ARE app that keeps Review candidates separate and opens source in IntelliJ."""

    def __init__(self, root: tk.Tk) -> None:
        self.ide_launcher = IntelliJLauncher()
        self.review_window: HealthReviewWindow | None = None
        self.file_targets: dict[str, Path] = {}
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
        super()._build_health_tab()

    def _build_health_filter_buttons(self) -> None:
        for child in self.health_filter_frame.winfo_children():
            child.destroy()
        self.health_filter_buttons.clear()

        all_button = ttk.Button(
            self.health_filter_frame,
            text="All Actionable 0",
            style="ARE.SelectedFilter.TButton",
            command=lambda: self._apply_health_filter(None),
        )
        all_button.pack(side=tk.LEFT)
        self.health_filter_buttons[None] = all_button

        for severity in PRIMARY_HEALTH_SEVERITIES:
            button = ttk.Button(
                self.health_filter_frame,
                text=f"{severity.value} 0",
                style="ARE.Filter.TButton",
                command=lambda selected=severity: self._apply_health_filter(selected),
            )
            button.pack(side=tk.LEFT, padx=(6, 0))
            self.health_filter_buttons[severity] = button

        self.show_review_button = ttk.Button(
            self.health_filter_frame,
            text="Show Review 0",
            command=self._show_review,
        )
        self.show_review_button.pack(side=tk.LEFT, padx=(16, 0))

    def _clear_scan_views(self) -> None:
        if self.review_window is not None and self.review_window.is_open:
            self.review_window.close()
        self.review_window = None
        self.file_targets.clear()
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
        self.health_filter = None
        self._update_health_filter_button_labels()
        self._apply_health_filter(None)

    def _update_health_filter_button_labels(self) -> None:
        if self.context is None:
            counts = {severity: 0 for severity in HealthSeverity}
        else:
            counts = severity_counts(self.context.health)

        actionable_total = sum(counts.get(severity, 0) for severity in PRIMARY_HEALTH_SEVERITIES)
        self.health_filter_buttons[None].configure(text=f"All Actionable {actionable_total}")
        for severity in PRIMARY_HEALTH_SEVERITIES:
            button = self.health_filter_buttons.get(severity)
            if button is not None:
                button.configure(text=f"{severity.value} {counts.get(severity, 0)}")
        self.show_review_button.configure(
            text=f"Show Review {counts.get(HealthSeverity.REVIEW, 0)}"
        )

    def _apply_health_filter(self, severity: HealthSeverity | None) -> None:
        if self.context is None:
            return
        if severity == HealthSeverity.REVIEW:
            self._show_review()
            return

        self.health_filter = severity
        if severity is None:
            groups = []
            for main_severity in PRIMARY_HEALTH_SEVERITIES:
                groups.extend(group_health_findings(self.context.health, severity=main_severity))
            self.health_groups = tuple(groups)
        else:
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
        filter_name = severity.value if severity is not None else "Actionable findings"
        review_count = severity_counts(self.context.health).get(HealthSeverity.REVIEW, 0)
        self.health_total_var.set(
            f"{filter_name}: {selected_count} finding(s) in {len(self.health_groups)} issue type(s) "
            f"• Review candidates: {review_count} (open separately)"
        )
        self._render_health_groups()
        self._render_health_findings()

    def _render_health_findings(self) -> None:
        if self.context is None or self.health_selected_group_id is None:
            self.health_group_title_var.set("No issue group selected.")
            self.health_group_description_var.set("")
            self.health_page_var.set("")
            self.health_finding_targets.clear()
            self.health_finding_cards.set_cards(
                (),
                on_open=lambda _card_id: None,
                empty_text="No actionable findings to display.",
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
                secondary_action_label="Open File",
            )
            for card in page.cards
        )
        self.health_finding_cards.set_cards(
            cards,
            on_open=self._open_health_finding_card,
            on_secondary=self._open_health_card_file,
            empty_text="No resolvable nodes were available for this finding page.",
        )

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

    def _show_review(self) -> None:
        if self.context is None:
            messagebox.showinfo("ARE", "Scan a repository first.")
            return
        review_count = severity_counts(self.context.health).get(HealthSeverity.REVIEW, 0)
        if review_count == 0:
            messagebox.showinfo("ARE Review", "No Review candidates were found.")
            return
        if self.review_window is not None and self.review_window.is_open:
            self.review_window.show()
            return

        self.review_window = HealthReviewWindow(
            self.root,
            report=self.context.health,
            graph=self.context.graph,
            path_formatter=self._relative_path,
            on_explore=self._explore_review_node,
            on_open_file=self._open_node_file,
            page_size=DEFAULT_HEALTH_PAGE_SIZE,
            on_close=self._review_closed,
        )

    def _review_closed(self) -> None:
        self.review_window = None

    def _explore_review_node(self, node_id: str, source: str) -> None:
        self.notebook.select(self.search_tab)
        self._visit_node(node_id, source=source)
        self.root.lift()

    def _open_health_card_file(self, card_id: str) -> None:
        node_id = self.health_finding_targets.get(card_id)
        if node_id is not None:
            self._open_node_file(node_id)

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
