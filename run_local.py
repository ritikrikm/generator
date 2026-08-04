"""Start Automation Repository Explorer as a local-only app.

This launcher is intentionally local. It does not deploy, upload, or copy the
target automation repository. The Streamlit process scans paths that exist on
the same machine where this command runs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run the local Streamlit UI."""

    app_path = Path(__file__).parent / "automation_repository_explorer" / "ui" / "app.py"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.fileWatcherType",
        "none",
        "--browser.gatherUsageStats",
        "false",
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
