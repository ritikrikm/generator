"""Repository scanner service."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from automation_repository_explorer.core.exceptions import RepositoryScanError
from automation_repository_explorer.models.domain import RepositoryFile

LOGGER = logging.getLogger(__name__)

IGNORED_DIRECTORIES = {
    ".git",
    ".idea",
    ".mvn",
    ".settings",
    "__MACOSX",
    "__pycache__",
    "allure-results",
    "build",
    "classes",
    "coverage",
    "dist",
    "generated-test-sources",
    "htmlreport",
    "log",
    "maven-archiver",
    "maven-status",
    "node_modules",
    "out",
    "surefire-reports",
    "target",
    "test-output",
    "testreport-archive",
}


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
        for root, directories, file_names in os.walk(repository_path):
            directories[:] = [
                directory
                for directory in directories
                if directory.lower() not in IGNORED_DIRECTORIES
            ]
            root_path = Path(root)
            for file_name in file_names:
                path = root_path / file_name
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

    @staticmethod
    def is_ignored_directory(path: Path) -> bool:
        """Return whether a directory is skipped during scanning."""

        return path.name.lower() in IGNORED_DIRECTORIES
