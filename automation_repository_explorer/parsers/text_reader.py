"""Text file reading helpers for mixed-encoding enterprise repositories."""

from __future__ import annotations

from pathlib import Path

from automation_repository_explorer.core.exceptions import ParserError

TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def read_text_file(file_path: Path, file_kind: str) -> str:
    """Read a text file using safe fallback encodings.

    Enterprise automation repositories often contain French or Windows-authored
    resources that are not valid UTF-8. `latin-1` is intentionally last because
    it can decode any byte sequence; this keeps parsing resilient while still
    preferring UTF-8 when possible.
    """

    errors: list[str] = []
    for encoding in TEXT_ENCODINGS:
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
        except OSError as exc:
            raise ParserError(f"Unable to read {file_kind} file {file_path}: {exc}") from exc

    formatted_errors = "; ".join(errors)
    raise ParserError(
        f"Unable to decode {file_kind} file {file_path}. Tried {TEXT_ENCODINGS}. "
        f"Errors: {formatted_errors}"
    )
