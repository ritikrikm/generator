"""Streamlit entrypoint for Automation Repository Explorer."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from automation_repository_explorer.core.logging_config import configure_logging
from automation_repository_explorer.ui.pages.details import render_details
from automation_repository_explorer.ui.pages.home import render_home
from automation_repository_explorer.ui.pages.relationship_explorer import render_relationship_explorer
from automation_repository_explorer.ui.pages.repository_summary import render_repository_summary
from automation_repository_explorer.ui.pages.search import render_search
from automation_repository_explorer.ui.repository_upload import (
    RepositoryUploadError,
    extract_repository_zip,
)
from automation_repository_explorer.ui.state import (
    get_repository_path,
    get_service,
    set_context,
    set_repository_path,
)


def main() -> None:
    """Run the Streamlit application."""

    configure_logging()
    st.set_page_config(page_title="Automation Repository Explorer", layout="wide")
    st.title("Automation Repository Explorer")
    st.caption("Static analysis for Java Selenium Cucumber repositories. No AI involved.")

    with st.sidebar:
        st.header("Repository")
        repository_source = st.radio(
            "Repository source",
            ["Local path", "Upload ZIP"],
            horizontal=True,
        )
        if repository_source == "Local path":
            repository_text = st.text_input("Repository path", value=get_repository_path())
            if st.button("Scan repository", type="primary"):
                repository_path = Path(repository_text).expanduser().resolve()
                _scan_repository(repository_path)
        else:
            uploaded_file = st.file_uploader("Repository ZIP", type=["zip"])
            if uploaded_file is not None and st.button("Scan uploaded ZIP", type="primary"):
                try:
                    repository_path = extract_repository_zip(
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                    )
                except RepositoryUploadError as exc:
                    st.error(str(exc))
                else:
                    _scan_repository(repository_path)

        st.header("Pages")
        page = st.radio(
            "Navigate",
            ["Home", "Repository Summary", "Search", "Relationship Explorer", "Details"],
            label_visibility="collapsed",
        )

    if page == "Home":
        render_home()
    elif page == "Repository Summary":
        render_repository_summary()
    elif page == "Search":
        render_search()
    elif page == "Relationship Explorer":
        render_relationship_explorer()
    elif page == "Details":
        render_details()


def _scan_repository(repository_path: Path) -> None:
    """Scan a repository and store the active exploration context."""

    with st.spinner("Scanning repository..."):
        context = get_service().explore(repository_path)
    set_repository_path(repository_path)
    set_context(context)
    st.success("Repository scanned.")


if __name__ == "__main__":
    main()
