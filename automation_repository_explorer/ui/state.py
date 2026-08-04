"""Streamlit session state helpers."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from automation_repository_explorer.services.explorer_service import ExplorationContext, ExplorerService


def get_service() -> ExplorerService:
    """Return a memoized ExplorerService."""

    if "are_service" not in st.session_state:
        st.session_state["are_service"] = ExplorerService()
    return st.session_state["are_service"]


def get_context() -> ExplorationContext | None:
    """Return the active exploration context."""

    context = st.session_state.get("are_context")
    return context if isinstance(context, ExplorationContext) else None


def set_context(context: ExplorationContext) -> None:
    """Store active exploration context."""

    st.session_state["are_context"] = context


def set_repository_path(path: Path) -> None:
    """Store selected repository path."""

    st.session_state["are_repository_path"] = str(path)


def get_repository_path() -> str:
    """Return selected repository path."""

    return str(st.session_state.get("are_repository_path", "sample_repo"))
