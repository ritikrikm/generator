"""Node details page."""

from __future__ import annotations

import streamlit as st

from automation_repository_explorer.ui.components import node_label
from automation_repository_explorer.ui.state import get_context


def render_details() -> None:
    """Render raw node details."""

    st.subheader("Details")
    context = get_context()
    if context is None:
        st.warning("Scan a repository first.")
        return

    query = st.text_input("Filter node labels", "")
    nodes = sorted(context.graph.nodes, key=lambda node: (node.type.value, node.name))
    if query:
        nodes = [node for node in nodes if query.lower() in node_label(node).lower()]

    for node in nodes[:100]:
        with st.expander(node_label(node)):
            st.code(node.id)
            st.write("File:", str(node.file_path) if node.file_path else "")
            st.write("Line:", node.line or "")
            st.json(node.metadata)
