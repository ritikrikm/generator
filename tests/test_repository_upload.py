"""Tests for repository ZIP upload handling."""

from __future__ import annotations

import unittest
import zipfile
from io import BytesIO

from automation_repository_explorer.ui.repository_upload import (
    RepositoryUploadError,
    extract_repository_zip,
)


class RepositoryUploadTests(unittest.TestCase):
    """Validate uploaded repository ZIP extraction."""

    def test_extract_repository_zip_returns_inner_repo_root(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "my-repo/src/test/features/home/Login.feature",
                "Feature: Login\n  Scenario: Login works\n    Given user logs in\n",
            )

        repository_root = extract_repository_zip("my-repo.zip", buffer.getvalue())

        self.assertEqual(repository_root.name, "my-repo")
        self.assertTrue((repository_root / "src/test/features/home/Login.feature").exists())

    def test_extract_repository_zip_rejects_path_traversal(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../escape.feature", "Feature: Escape\n")

        with self.assertRaises(RepositoryUploadError):
            extract_repository_zip("bad.zip", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
