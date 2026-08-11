"""Public local ARE desktop entrypoint.

The stable implementation lives in ``local_app_base`` and local-only UX enhancements live in
``local_app_enhanced``. Keeping this entrypoint small preserves ``python -m
 automation_repository_explorer.local_app`` while letting UI features stay modular.
"""

from automation_repository_explorer.local_app_enhanced import ARELocalApp, main

__all__ = ["ARELocalApp", "main"]


if __name__ == "__main__":
    main()
