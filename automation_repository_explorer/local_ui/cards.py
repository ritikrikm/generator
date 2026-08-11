"""Reusable Tkinter card widgets for ARE local views."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True, slots=True)
class CardSpec:
    """Data-only description of one clickable UI card."""

    id: str
    eyebrow: str
    title: str
    subtitle: str = ""
    detail: str = ""
    action_label: str = "Open"


def configure_local_styles(style: ttk.Style) -> None:
    """Configure reusable local UI styles without repository-specific assumptions."""

    style.configure("ARE.Card.TLabelframe", padding=6)
    style.configure("ARE.SelectedCard.TLabelframe", padding=6, borderwidth=2)
    style.configure("ARE.CardTitle.TLabel", font=("Segoe UI", 10, "bold"))
    style.configure("ARE.CardMeta.TLabel", font=("Segoe UI", 9))
    style.configure("ARE.SectionTitle.TLabel", font=("Segoe UI", 11, "bold"))
    style.configure("ARE.Filter.TButton", padding=(10, 7))
    style.configure("ARE.SelectedFilter.TButton", padding=(10, 7))


class ScrollableCardList(ttk.Frame):
    """Scrollable reusable card list with card-level click handling."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        background = ttk.Style(self).lookup("TFrame", "background")
        if not background:
            background = str(self.winfo_toplevel().cget("background"))
        self._canvas = tk.Canvas(
            self,
            highlightthickness=0,
            borderwidth=0,
            background=background,
        )
        self._scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._content = ttk.Frame(self._canvas)
        self._window_id = self._canvas.create_window((0, 0), window=self._content, anchor="nw")

        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._content.bind("<Configure>", self._sync_scroll_region)
        self._canvas.bind("<Configure>", self._sync_content_width)
        self._bind_scroll(self._canvas)

    def clear(self) -> None:
        for child in self._content.winfo_children():
            child.destroy()
        self._canvas.yview_moveto(0)

    def set_cards(
        self,
        cards: Iterable[CardSpec],
        *,
        on_open: Callable[[str], None],
        selected_id: str | None = None,
        empty_text: str = "Nothing to show.",
    ) -> None:
        self.clear()
        card_list = tuple(cards)
        if not card_list:
            empty_label = ttk.Label(self._content, text=empty_text, wraplength=420)
            empty_label.pack(anchor=tk.W, fill=tk.X, padx=8, pady=8)
            self._bind_scroll(empty_label)
            return

        for card in card_list:
            style = (
                "ARE.SelectedCard.TLabelframe"
                if card.id == selected_id
                else "ARE.Card.TLabelframe"
            )
            frame = ttk.LabelFrame(
                self._content,
                text=card.eyebrow,
                padding=8,
                style=style,
            )
            frame.pack(fill=tk.X, padx=4, pady=5)

            title = ttk.Label(
                frame,
                text=card.title,
                style="ARE.CardTitle.TLabel",
                wraplength=430,
            )
            title.pack(anchor=tk.W, fill=tk.X)

            interactive_widgets: list[tk.Misc] = [frame, title]
            if card.subtitle:
                subtitle = ttk.Label(
                    frame,
                    text=card.subtitle,
                    style="ARE.CardMeta.TLabel",
                    wraplength=430,
                )
                subtitle.pack(anchor=tk.W, fill=tk.X, pady=(3, 0))
                interactive_widgets.append(subtitle)
            if card.detail:
                detail = ttk.Label(frame, text=card.detail, wraplength=430)
                detail.pack(anchor=tk.W, fill=tk.X, pady=(5, 0))
                interactive_widgets.append(detail)

            button = ttk.Button(
                frame,
                text=card.action_label,
                command=lambda card_id=card.id: on_open(card_id),
            )
            button.pack(anchor=tk.E, pady=(7, 0))
            interactive_widgets.append(button)

            for widget in interactive_widgets:
                self._bind_scroll(widget)
            for widget in interactive_widgets[:-1]:
                self._bind_card_click(widget, card.id, on_open)

        self._canvas.yview_moveto(0)

    def _sync_scroll_region(self, _event: object | None = None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _sync_content_width(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> str:
        if event.delta:
            self._canvas.yview_scroll(int(-event.delta / 120) * 3, "units")
        return "break"

    def _scroll_up(self, _event: tk.Event) -> str:
        self._canvas.yview_scroll(-3, "units")
        return "break"

    def _scroll_down(self, _event: tk.Event) -> str:
        self._canvas.yview_scroll(3, "units")
        return "break"

    def _bind_scroll(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._scroll_up)
        widget.bind("<Button-5>", self._scroll_down)

    @staticmethod
    def _bind_card_click(
        widget: tk.Misc,
        card_id: str,
        on_open: Callable[[str], None],
    ) -> None:
        try:
            widget.configure(cursor="hand2")
        except tk.TclError:
            pass
        widget.bind("<Button-1>", lambda _event, value=card_id: on_open(value))
