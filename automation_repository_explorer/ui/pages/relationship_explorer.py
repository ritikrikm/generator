"""Relationship explorer page."""

from __future__ import annotations

import streamlit as st

from automation_repository_explorer.ui.components import node_label, node_table_rows
from automation_repository_explorer.ui.state import get_context


def render_relationship_explorer() -> None:
    """Render relationship explorer page."""

    st.subheader("Relationship Explorer")
    context = get_context()
    if context is None:
        st.warning("Scan a repository first.")
        return

    nodes = sorted(context.graph.nodes, key=lambda node: (node.type.value, node.name))
    node_options = {node_label(node): node.id for node in nodes}
    selected_label = st.selectbox("Select node", list(node_options))
    selected_id = node_options[selected_label]

    node = context.graph.get_node(selected_id)
    if node is None:
        st.error("Node not found.")
        return

    st.write("Selected")
    st.dataframe(node_table_rows((node,)), use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.write("Parents")
        st.dataframe(node_table_rows(context.graph.parents(selected_id)), use_container_width=True)
    with right:
        st.write("Children")
        st.dataframe(node_table_rows(context.graph.children(selected_id)), use_container_width=True)

    st.write("Navigation path")
    st.dataframe(node_table_rows(context.graph.traverse(selected_id)), use_container_width=True)
