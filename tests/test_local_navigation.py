"""Tests for browser-like local relationship navigation."""

from automation_repository_explorer.local_ui.navigation import (
    NodeNavigationEntry,
    NodeNavigationHistory,
)


def test_back_forward_history_is_browser_like() -> None:
    history = NodeNavigationHistory()
    history.visit(NodeNavigationEntry("A", source="Search"))
    history.visit(NodeNavigationEntry("B", source="Outgoing"))
    history.visit(NodeNavigationEntry("C", source="Outgoing"))

    assert history.current is not None and history.current.node_id == "C"
    assert history.back_count == 2
    assert history.forward_count == 0

    assert history.back().node_id == "B"
    assert history.back().node_id == "A"
    assert history.can_back is False
    assert history.forward().node_id == "B"

    history.visit(NodeNavigationEntry("D", source="Incoming"))
    assert history.current is not None and history.current.node_id == "D"
    assert history.can_forward is False
    assert history.back().node_id == "B"
    assert history.forward().node_id == "D"


def test_revisiting_same_node_updates_context_without_duplicate_history() -> None:
    history = NodeNavigationHistory()
    history.visit(NodeNavigationEntry("A", score=10.0, source="Search"))
    history.visit(NodeNavigationEntry("A", score=99.0, source="Health"))

    assert history.back_count == 0
    assert history.current is not None
    assert history.current.score == 99.0
    assert history.current.source == "Health"
