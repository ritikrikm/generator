"""Repository scanner service."""

from __future__ import annotations

import logging
from pathlib import Path

from automation_repository_explorer.core.exceptions import RepositoryScanError
from automation_repository_explorer.models.domain import RepositoryFile

LOGGER = logging.getLogger(__name__)


class RepositoryScanner:
    """Recursively scans repositories for supported files."""

    def __init__(self, supported_extensions: set[str]) -> None:
        self._supported_extensions = {extension.lower() for extension in supported_extensions}

    def scan(self, repository_path: Path) -> tuple[RepositoryFile, ...]:
        """Return supported files below the repository path."""

        if not repository_path.exists():
            raise RepositoryScanError(f"Repository path does not exist: {repository_path}")
        if not repository_path.is_dir():
            raise RepositoryScanError(f"Repository path must be a directory: {repository_path}")

        files: list[RepositoryFile] = []
        for path in repository_path.rglob("*"):
            if not path.is_file():
                continue
            extension = path.suffix.lower()
            if extension not in self._supported_extensions:
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                LOGGER.warning("Skipping unreadable file %s: %s", path, exc)
                continue
            files.append(RepositoryFile(path=path, extension=extension, size_bytes=size))

        return tuple(sorted(files, key=lambda item: str(item.path)))
