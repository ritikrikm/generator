"""Shared text decoding helpers for heterogeneous automation repositories."""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from pathlib import Path

from automation_repository_explorer.core.exceptions import ParserError


@dataclass(frozen=True, slots=True)
class TextReadResult:
    """Decoded text plus the encoding that successfully decoded it."""

    text: str
    encoding: str
    used_fallback: bool = False


def read_repository_text(file_path: Path) -> TextReadResult:
    """Read a repository text file without assuming every team uses UTF-8.

    ARE first respects Unicode byte-order marks, then prefers UTF-8, then falls back to
    common Windows/legacy encodings used by Java automation repositories. Decoding is always
    strict; ARE never silently replaces undecodable bytes with replacement characters.
    """

    try:
        data = file_path.read_bytes()
    except OSError as exc:
        raise ParserError(f"Unable to read file {file_path}: {exc}") from exc

    bom_candidates: tuple[tuple[bytes, str], ...] = (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    )
    for bom, encoding in bom_candidates:
        if bom and data.startswith(bom):
            try:
                return TextReadResult(text=data.decode(encoding), encoding=encoding)
            except UnicodeDecodeError:
                break

    # UTF-8 is the preferred modern format. CP1252 and ISO-8859-1 cover common
    # Windows/legacy Java .properties and resource files found in enterprise repos.
    candidates = ("utf-8", "cp1252", "iso-8859-1")
    failures: list[str] = []
    for index, encoding in enumerate(candidates):
        try:
            return TextReadResult(
                text=data.decode(encoding),
                encoding=encoding,
                used_fallback=index > 0,
            )
        except UnicodeDecodeError as exc:
            failures.append(f"{encoding}: byte 0x{data[exc.start]:02x} at position {exc.start}")

    raise ParserError(
        f"Unable to decode text file {file_path}. Tried: " + "; ".join(failures)
    )
