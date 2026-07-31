"""Repository summary page."""

from __future__ import annotations

import streamlit as st

from automation_repository_explorer.ui.state import get_context


def render_repository_summary() -> None:
    """Render repository summary."""

    st.subheader("Repository Summary")
    context = get_context()
    if context is None:
        st.warning("Scan a repository first.")
        return

    summary = context.summary
    cols = st.columns(4)
    cols[0].metric("Files", summary.files)
    cols[1].metric("Features", summary.features)
    cols[2].metric("Scenarios", summary.scenarios)
    cols[3].metric("Steps", summary.steps)

    cols = st.columns(4)
    cols[0].metric("Java Classes", summary.java_classes)
    cols[1].metric("Java Methods", summary.java_methods)
    cols[2].metric("Properties", summary.properties)
    cols[3].metric("Graph Edges", summary.graph_edges)

    st.write("Indexed files")
    st.dataframe(
        [
            {
                "Path": str(file.path),
                "Extension": file.extension,
                "Size": file.size_bytes,
            }
            for file in context.index.files
        ],
        use_container_width=True,
    )
