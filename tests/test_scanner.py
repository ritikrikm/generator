"""Tests for repository scanner behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation_repository_explorer.services.scanner import RepositoryScanner


class RepositoryScannerTests(unittest.TestCase):
    """Validate repository scanner filtering."""

    def test_scan_skips_generated_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository_root = Path(temp_dir)
            feature_file = repository_root / "src/test/features/home/Home.feature"
            generated_file = repository_root / "target/generated-test-sources/Generated.feature"
            feature_file.parent.mkdir(parents=True)
            generated_file.parent.mkdir(parents=True)
            feature_file.write_text("Feature: Home\n", encoding="utf-8")
            generated_file.write_text("Feature: Generated\n", encoding="utf-8")

            files = RepositoryScanner({".feature"}).scan(repository_root)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path.name, "Home.feature")


if __name__ == "__main__":
    unittest.main()
