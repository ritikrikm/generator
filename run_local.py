"""One-file local launcher for Automation Repository Explorer.

Run this file from the project root:

    python run_local.py

Useful options:

    python run_local.py --check
    python run_local.py --install
    python run_local.py --port 8502

This launcher is intentionally local. It does not deploy, upload, copy, or
modify the target automation repository. The app scans only folders that exist
on the same machine where this command runs.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 12)
REQUIRED_MODULES = ("streamlit", "rapidfuzz")


class LauncherError(Exception):
    """Raised when the local launcher cannot start ARE safely."""


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _app_path() -> Path:
    return _project_root() / "automation_repository_explorer" / "ui" / "app.py"


def _requirements_path() -> Path:
    return _project_root() / "requirements-dev.txt"


def _print_header() -> None:
    print("Automation Repository Explorer - Local Runner")
    print("Mode: local only, read only, no deployment, no repository upload")
    print()


def _validate_python() -> None:
    if sys.version_info < MIN_PYTHON:
        version = ".".join(str(part) for part in MIN_PYTHON)
        current = ".".join(str(part) for part in sys.version_info[:3])
        raise LauncherError(
            f"Python {version}+ is required. Current Python is {current}.\n"
            "Install Python 3.12+, then run this file again."
        )


def _validate_project_files() -> None:
    missing: list[Path] = []
    for path in (_app_path(), _requirements_path()):
        if not path.exists():
            missing.append(path)

    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise LauncherError(
            "Required ARE project files are missing:\n"
            f"{formatted}\n\n"
            "Run this launcher from the ARE project folder, or re-clone the repository."
        )


def _missing_modules() -> list[str]:
    return [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]


def _install_dependencies() -> None:
    requirements = _requirements_path()
    print(f"Installing dependencies from {requirements} ...")
    command = [sys.executable, "-m", "pip", "install", "-r", str(requirements)]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise LauncherError(
            "Dependency installation failed.\n"
            "Try running this manually:\n\n"
            f"  {sys.executable} -m pip install -r {requirements}\n"
        )


def _dependency_error_message(missing: list[str]) -> str:
    requirements = _requirements_path()
    missing_text = ", ".join(missing)
    return (
        f"Missing Python package(s): {missing_text}\n\n"
        "Install them once, then run ARE again:\n\n"
        f"  {sys.executable} -m pip install -r {requirements}\n\n"
        "Or let this launcher install them:\n\n"
        "  python run_local.py --install\n"
    )


def _run_preflight(install: bool) -> None:
    _validate_python()
    _validate_project_files()

    missing = _missing_modules()
    if missing and install:
        _install_dependencies()
        missing = _missing_modules()

    if missing:
        raise LauncherError(_dependency_error_message(missing))


def _start_streamlit(port: int | None) -> int:
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(_app_path()),
        "--server.fileWatcherType",
        "none",
        "--browser.gatherUsageStats",
        "false",
    ]
    if port is not None:
        command.extend(["--server.port", str(port)])

    print("Starting local UI ...")
    print("After the browser opens, paste your automation repo folder path in the sidebar.")
    print("Press Ctrl+C in this terminal to stop ARE.")
    print()

    return subprocess.call(command, env=env)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ARE locally.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run preflight checks and exit without starting the UI.",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install missing Python dependencies before starting.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Optional local Streamlit port, for example 8502.",
    )
    return parser


def main() -> int:
    """Run preflight checks and start the local Streamlit UI."""

    _print_header()
    args = _build_parser().parse_args()

    try:
        _run_preflight(install=args.install)
        if args.check:
            print("Preflight checks passed.")
            return 0
        return _start_streamlit(port=args.port)
    except KeyboardInterrupt:
        print("\nARE stopped.")
        return 130
    except LauncherError as exc:
        print("Cannot start ARE.")
        print()
        print(exc)
        return 1
    except OSError as exc:
        print("Cannot start ARE because the operating system blocked the command.")
        print()
        print(f"System error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
