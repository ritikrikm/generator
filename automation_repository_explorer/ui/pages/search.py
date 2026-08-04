"""Search page."""

from __future__ import annotations

import streamlit as st

from automation_repository_explorer.models.graph import NodeType
from automation_repository_explorer.search.search_engine import SearchMode
from automation_repository_explorer.ui.components import node_label
from automation_repository_explorer.ui.state import get_context, get_service


def render_search() -> None:
    """Render repository search page."""

    st.subheader("Search")
    context = get_context()
    if context is None:
        st.warning("Scan a repository first.")
        return

    query = st.text_input("Search anything")
    mode = st.selectbox("Search mode", list(SearchMode), format_func=lambda item: item.value)
    selected_types = st.multiselect(
        "Node types",
        list(NodeType),
        format_func=lambda item: item.value,
    )
    node_types = set(selected_types) if selected_types else None

    if query:
        results = get_service().search(context.graph, query, mode=mode, node_types=node_types)
        st.write(f"{len(results)} result(s)")
        for result in results:
            with st.expander(f"{result.score:.0f} - {node_label(result.node)}"):
                st.code(result.node.id)
                st.write("Matched text:", result.matched_text)
                st.json(result.node.metadata)
