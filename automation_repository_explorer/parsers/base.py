"""Common parser abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

TParsed = TypeVar("TParsed")


@dataclass(frozen=True, slots=True)
class ParseResult(Generic[TParsed]):
    """Parser output for a single file."""

    file_path: Path
    items: tuple[TParsed, ...]


class RepositoryParser(ABC, Generic[TParsed]):
    """Common interface implemented by every parser."""

    @property
    @abstractmethod
    def supported_extensions(self) -> frozenset[str]:
        """Return supported file extensions, including leading dots."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult[TParsed]:
        """Parse a repository file."""
