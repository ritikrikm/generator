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
    """Scan a repository, show real progress, and retain non-fatal parser diagnostics."""

    progress_bar = st.progress(1, text="1% — Starting repository scan...")

    def update_progress(percent: int, message: str) -> None:
        safe_percent = max(1, min(percent, 100))
        progress_bar.progress(
            safe_percent,
            text=f"{safe_percent}% — {message}",
        )

    try:
        context = get_service().explore(
            repository_path,
            progress_callback=update_progress,
        )
    except RepositoryScanError as exc:
        progress_bar.empty()
        st.error(str(exc))
        st.info(
            "If this path is on your company laptop, run ARE locally on that laptop. "
            "A Streamlit Cloud website cannot read local C:\\ or /Users paths from your browser."
        )
        return
    except Exception as exc:  # noqa: BLE001 - surface an actionable scan failure in the UI
        progress_bar.empty()
        st.error(f"Repository scan failed: {exc}")
        return

    set_repository_path(repository_path)
    set_context(context)

    if context.index.parse_issues:
        st.warning(
            f"Repository scanned with {len(context.index.parse_issues)} file(s) that ARE could not fully parse."
        )
        with st.expander("View scan issues"):
            st.dataframe(
                [
                    {
                        "File": str(issue.file_path),
                        "Parser": issue.parser_name,
                        "Reason": issue.message,
                    }
                    for issue in context.index.parse_issues
                ],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.success("Repository scanned successfully.")


if __name__ == "__main__":
    main()
