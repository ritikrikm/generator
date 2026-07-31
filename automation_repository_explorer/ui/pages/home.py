"""Home page."""

from __future__ import annotations

import streamlit as st

from automation_repository_explorer.ui.state import get_context


def render_home() -> None:
    """Render home page."""

    st.subheader("Home")
    st.write(
        "ARE scans Java Selenium Cucumber automation repositories and builds a static "
        "relationship map between features, scenarios, steps, step definitions, Java methods, "
        "page objects, wrapper methods, property keys, and XPath locators."
    )
    st.info("Select a repository in the sidebar and scan it to begin.")

    context = get_context()
    if context is not None:
        st.success("Repository is loaded. Use Search or Relationship Explorer.")
