"""Navigation state for the local relationship explorer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NodeNavigationEntry:
    """One visited relationship-explorer node with optional search context."""

    node_id: str
    score: float | None = None
    matched_text: str | None = None
    source: str | None = None


@dataclass(slots=True)
class NodeNavigationHistory:
    """Browser-like back/forward history for relationship exploration."""

    current: NodeNavigationEntry | None = None
    _back: list[NodeNavigationEntry] = field(default_factory=list)
    _forward: list[NodeNavigationEntry] = field(default_factory=list)

    @property
    def can_back(self) -> bool:
        return bool(self._back)

    @property
    def can_forward(self) -> bool:
        return bool(self._forward)

    @property
    def back_count(self) -> int:
        return len(self._back)

    @property
    def forward_count(self) -> int:
        return len(self._forward)

    def visit(self, entry: NodeNavigationEntry) -> NodeNavigationEntry:
        """Visit a node and clear forward history just like a browser."""

        if self.current is not None and self.current.node_id == entry.node_id:
            self.current = entry
            return entry
        if self.current is not None:
            self._back.append(self.current)
        self.current = entry
        self._forward.clear()
        return entry

    def back(self) -> NodeNavigationEntry | None:
        if not self._back:
            return None
        if self.current is not None:
            self._forward.append(self.current)
        self.current = self._back.pop()
        return self.current

    def forward(self) -> NodeNavigationEntry | None:
        if not self._forward:
            return None
        if self.current is not None:
            self._back.append(self.current)
        self.current = self._forward.pop()
        return self.current

    def reset(self, entry: NodeNavigationEntry | None = None) -> None:
        self.current = entry
        self._back.clear()
        self._forward.clear()
