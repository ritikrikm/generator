"""Streamlit entrypoint for Automation Repository Explorer."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from automation_repository_explorer.core.exceptions import RepositoryScanError
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
            st.caption("Use this when ARE is running on the same machine as the repository.")
            repository_text = st.text_input("Repository path", value=get_repository_path())
            if st.button("Scan repository", type="primary"):
                repository_path = Path(repository_text).expanduser().resolve()
                _scan_repository(repository_path)
        else:
            st.caption("Zip the repository folder and upload it here. Generated folders like target are skipped.")
            uploaded_file = st.file_uploader("Repository ZIP", type=["zip"])
            if uploaded_file is None:
                st.info("After the upload finishes, the scan button will appear here.")
            elif st.button("Scan uploaded ZIP", type="primary", use_container_width=True):
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

    try:
        with st.spinner("Scanning repository..."):
            context = get_service().explore(repository_path)
    except RepositoryScanError as exc:
        st.error(str(exc))
        st.info(
            "If this path is on your company laptop, run ARE locally on that laptop. "
            "A Streamlit Cloud website cannot read local C:\\ or /Users paths from your browser."
        )
        return

    set_repository_path(repository_path)
    set_context(context)
    st.success("Repository scanned.")


if __name__ == "__main__":
    main()
