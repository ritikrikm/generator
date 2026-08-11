"""Repository scanner service."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

from automation_repository_explorer.core.exceptions import RepositoryScanError
from automation_repository_explorer.models.domain import RepositoryFile

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[int, str], None]

_IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".gradle",
    ".idea",
    ".mvn",
    ".settings",
    ".vscode",
    "__macosx",
    "__pycache__",
    "allure-results",
    "build",
    "classes",
    "coverage",
    "dist",
    "generated-sources",
    "generated-test-sources",
    "htmlreport",
    "log",
    "logs",
    "maven-archiver",
    "maven-status",
    "node_modules",
    "out",
    "surefire-reports",
    "target",
    "test-output",
    "testreport-archive",
}
IGNORED_DIRECTORIES = frozenset(name.lower() for name in _IGNORED_DIRECTORY_NAMES)


class RepositoryScanner:
    """Recursively scans repositories for supported files at any folder depth."""

    def __init__(self, supported_extensions: set[str]) -> None:
        self._supported_extensions = {extension.lower() for extension in supported_extensions}

    def scan(
        self,
        repository_path: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[RepositoryFile, ...]:
        """Return supported files below the repository path.

        Folder names such as ``steps``, ``pages``, ``features`` or ``resources`` are never
        required. ARE walks the complete repository tree and selects files only by parser
        capability, while excluding common generated/build directories.
        """

        if not repository_path.exists():
            raise RepositoryScanError(f"Repository path does not exist: {repository_path}")
        if not repository_path.is_dir():
            raise RepositoryScanError(f"Repository path must be a directory: {repository_path}")

        if progress_callback:
            progress_callback(5, "Discovering supported files at every folder depth...")

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

        sorted_files = tuple(sorted(files, key=lambda item: str(item.path)))
        if progress_callback:
            progress_callback(10, f"Found {len(sorted_files)} supported files across the repository.")
        return sorted_files

    @staticmethod
    def is_ignored_directory(path: Path) -> bool:
        """Return whether a directory is skipped during scanning."""

        return path.name.lower() in IGNORED_DIRECTORIES
