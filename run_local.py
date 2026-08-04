"""One-file local launcher for Automation Repository Explorer.

Run from the project root:

    python run_local.py

This launcher uses only Python standard-library modules. It does not require
any third-party UI package approval.
"""

from __future__ import annotations

import argparse
import sys

MIN_PYTHON = (3, 12)


class LauncherError(Exception):
    """Raised when the local launcher cannot start ARE safely."""


def _print_header() -> None:
    print("Automation Repository Explorer - Local Runner")
    print("Mode: local only, read only, no deployment, no repository upload")
    print("UI: Python standard library HTTP server")
    print()


def _validate_python() -> None:
    if sys.version_info < MIN_PYTHON:
        version = ".".join(str(part) for part in MIN_PYTHON)
        current = ".".join(str(part) for part in sys.version_info[:3])
        raise LauncherError(
            f"Python {version}+ is required. Current Python is {current}.\n"
            "Install Python 3.12+, then run this file again."
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ARE with the local standard-library UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Local host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8501, help="Local port. Default: 8501")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server without opening a browser automatically.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run startup checks and exit without starting the UI.",
    )
    return parser


def main() -> int:
    """Run preflight checks and start the local web UI."""

    _print_header()
    args = _build_parser().parse_args()

    try:
        _validate_python()
        if args.check:
            print("Preflight checks passed.")
            return 0

        from automation_repository_explorer.local_web_app import run_local_server

        run_local_server(host=args.host, port=args.port, open_browser=not args.no_browser)
        return 0
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
