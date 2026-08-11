"""Complete Repository Health workspace for the local ARE desktop app."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from automation_repository_explorer.analyzers.health_analyzer import (
    HealthSeverity,
    RepositoryHealthReport,
)
from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.local_ui.cards import CardSpec, ScrollableCardList
from automation_repository_explorer.local_ui.health_presenter import (
    DEFAULT_HEALTH_PAGE_SIZE,
    HealthIssueGroup,
    group_health_findings,
    page_health_group,
    severity_counts,
)


class RepositoryHealthWindow:
    """Filterable, grouped, paged Repository Health workspace in its own window."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        report: RepositoryHealthReport,
        graph: RepositoryGraph,
        path_formatter: Callable[[Path], str],
        on_explore: Callable[[str, str], None],
        on_open_file: Callable[[str], None],
        page_size: int = DEFAULT_HEALTH_PAGE_SIZE,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self._report = report
        self._graph = graph
        self._path_formatter = path_formatter
        self._on_explore = on_explore
        self._on_open_file = on_open_file
        self._page_size = max(1, int(page_size))
        self._on_close = on_close

        self._severity: HealthSeverity | None = None
        self._groups: tuple[HealthIssueGroup, ...] = tuple()
        self._groups_by_id: dict[str, HealthIssueGroup] = {}
        self._selected_group_id: str | None = None
        self._page_index = 0
        self._finding_targets: dict[str, str] = {}
        self._filter_buttons: dict[HealthSeverity | None, ttk.Button] = {}

        self.window = tk.Toplevel(parent)
        self.window.title("ARE — Repository Health")
        self.window.geometry("1360x860")
        self.window.minsize(1040, 680)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._summary_var = tk.StringVar(value="")
        self._title_var = tk.StringVar(value="Select an issue group.")
        self._description_var = tk.StringVar(value="")
        self._page_var = tk.StringVar(value="")

        self._build_ui()
        self._apply_filter(None)

    @property
    def is_open(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def show(self) -> None:
        if not self.is_open:
            return
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def close(self) -> None:
        if self.is_open:
            self.window.destroy()
        if self._on_close is not None:
            self._on_close()

    def _build_ui(self) -> None:
        root = ttk.Frame(self.window, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            root,
            text="Repository Health",
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            root,
            text=(
                "Inspect evidence-backed automation findings in one place. High findings have the "
                "strongest evidence, Medium findings should be investigated, and Review findings "
                "are conservative candidates—not deletion recommendations."
            ),
            wraplength=1280,
        ).pack(anchor=tk.W, fill=tk.X, pady=(3, 9))

        filters = ttk.Frame(root)
        filters.pack(fill=tk.X, pady=(0, 7))
        counts = severity_counts(self._report)

        all_button = ttk.Button(
            filters,
            text=f"All {self._report.total}",
            command=lambda: self._apply_filter(None),
        )
        all_button.pack(side=tk.LEFT)
        self._filter_buttons[None] = all_button

        for severity in HealthSeverity:
            button = ttk.Button(
                filters,
                text=f"{severity.value} {counts.get(severity, 0)}",
                command=lambda selected=severity: self._apply_filter(selected),
            )
            button.pack(side=tk.LEFT, padx=(6, 0))
            self._filter_buttons[severity] = button

        ttk.Label(
            root,
            textvariable=self._summary_var,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        pane = tk.PanedWindow(
            root,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            borderwidth=0,
        )
        pane.pack(fill=tk.BOTH, expand=True)

        groups_frame = ttk.LabelFrame(pane, text="Issue Groups", padding=8)
        details_frame = ttk.LabelFrame(pane, text="Findings", padding=8)
        pane.add(groups_frame, minsize=380, stretch="always")
        pane.add(details_frame, minsize=620, stretch="always")

        ttk.Label(
            groups_frame,
            text=(
                "Similar findings are grouped together. Select a group to see every affected "
                "file/node without flooding the screen."
            ),
            wraplength=450,
        ).pack(anchor=tk.W, fill=tk.X, pady=(0, 6))
        self._group_cards = ScrollableCardList(groups_frame)
        self._group_cards.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            details_frame,
            textvariable=self._title_var,
            style="ARE.SectionTitle.TLabel",
            wraplength=780,
        ).pack(anchor=tk.W, fill=tk.X)
        ttk.Label(
            details_frame,
            textvariable=self._description_var,
            wraplength=780,
        ).pack(anchor=tk.W, fill=tk.X, pady=(3, 8))

        paging = ttk.Frame(details_frame)
        paging.pack(fill=tk.X, pady=(0, 6))
        self._previous_button = ttk.Button(
            paging,
            text=f"← Previous {self._page_size}",
            command=self._previous_page,
            state=tk.DISABLED,
        )
        self._previous_button.pack(side=tk.LEFT)
        self._next_button = ttk.Button(
            paging,
            text=f"Next {self._page_size} →",
            command=self._next_page,
            state=tk.DISABLED,
        )
        self._next_button.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(paging, textvariable=self._page_var).pack(side=tk.LEFT, padx=(12, 0))

        self._finding_cards = ScrollableCardList(details_frame)
        self._finding_cards.pack(fill=tk.BOTH, expand=True)

    def _apply_filter(self, severity: HealthSeverity | None) -> None:
        self._severity = severity
        self._groups = group_health_findings(self._report, severity=severity)
        self._groups_by_id = {group.id: group for group in self._groups}
        self._selected_group_id = self._groups[0].id if self._groups else None
        self._page_index = 0

        for filter_value, button in self._filter_buttons.items():
            button.configure(
                style=(
                    "ARE.SelectedFilter.TButton"
                    if filter_value == severity
                    else "ARE.Filter.TButton"
                )
            )

        selected_count = sum(group.count for group in self._groups)
        label = severity.value if severity is not None else "All severities"
        self._summary_var.set(
            f"{label}: {selected_count} finding(s) grouped into {len(self._groups)} issue type(s)."
        )
        self._render_groups()
        self._render_findings()

    def _render_groups(self) -> None:
        cards = tuple(
            CardSpec(
                id=group.id,
                eyebrow=f"{group.severity.value} • {group.count} finding(s)",
                title=group.check_name,
                detail=group.description,
                action_label="Show findings",
            )
            for group in self._groups
        )
        self._group_cards.set_cards(
            cards,
            on_open=self._select_group,
            selected_id=self._selected_group_id,
            empty_text="No findings in this severity.",
        )

    def _select_group(self, group_id: str) -> None:
        if group_id not in self._groups_by_id:
            return
        self._selected_group_id = group_id
        self._page_index = 0
        self._render_groups()
        self._render_findings()

    def _render_findings(self) -> None:
        if self._selected_group_id is None:
            self._title_var.set("No issue group selected.")
            self._description_var.set("")
            self._page_var.set("")
            self._finding_targets.clear()
            self._finding_cards.set_cards(
                (),
                on_open=lambda _card_id: None,
                empty_text="No findings to display.",
            )
            self._update_page_buttons(False, False)
            return

        group = self._groups_by_id[self._selected_group_id]
        page = page_health_group(
            group,
            self._graph,
            page_index=self._page_index,
            page_size=self._page_size,
            path_formatter=self._path_formatter,
        )
        self._page_index = page.page_index
        self._title_var.set(f"{group.check_name} — {group.count} finding(s)")
        self._description_var.set(f"What ARE detected: {group.description}")

        start = page.page_index * self._page_size + 1 if page.total else 0
        end = start + len(page.cards) - 1 if page.cards else 0
        self._page_var.set(
            f"Showing {start}-{end} of {page.total} • Page {page.page_index + 1}/{page.page_count}"
        )
        self._update_page_buttons(page.can_previous, page.can_next)

        self._finding_targets = {card.id: card.node_id for card in page.cards}
        cards = tuple(
            CardSpec(
                id=card.id,
                eyebrow=f"{group.severity.value} • {card.confidence} confidence • {card.node_type}",
                title=card.name,
                subtitle=card.location,
                detail=card.message,
                action_label="Explore node",
                secondary_action_label="Open File",
            )
            for card in page.cards
        )
        self._finding_cards.set_cards(
            cards,
            on_open=self._open_finding,
            on_secondary=self._open_file,
            empty_text="No resolvable nodes were available for this page.",
        )

    def _open_finding(self, card_id: str) -> None:
        node_id = self._finding_targets.get(card_id)
        if node_id is None:
            return
        group = self._groups_by_id.get(self._selected_group_id or "")
        source = f"Repository Health: {group.check_name}" if group else "Repository Health"
        self._on_explore(node_id, source)

    def _open_file(self, card_id: str) -> None:
        node_id = self._finding_targets.get(card_id)
        if node_id is not None:
            self._on_open_file(node_id)

    def _previous_page(self) -> None:
        if self._page_index <= 0:
            return
        self._page_index -= 1
        self._render_findings()

    def _next_page(self) -> None:
        if self._selected_group_id is None:
            return
        group = self._groups_by_id[self._selected_group_id]
        page = page_health_group(
            group,
            self._graph,
            page_index=self._page_index,
            page_size=self._page_size,
            path_formatter=self._path_formatter,
        )
        if page.can_next:
            self._page_index += 1
            self._render_findings()

    def _update_page_buttons(self, can_previous: bool, can_next: bool) -> None:
        self._previous_button.configure(state=tk.NORMAL if can_previous else tk.DISABLED)
        self._next_button.configure(state=tk.NORMAL if can_next else tk.DISABLED)
