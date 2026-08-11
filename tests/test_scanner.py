from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation_repository_explorer.services.scanner import RepositoryScanner


class RepositoryScannerTest(unittest.TestCase):
    def test_scans_supported_files_at_arbitrary_folder_depth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deep = root / "team" / "whatever" / "level1" / "level2" / "level3"
            deep.mkdir(parents=True)
            java_file = deep / "Anything.java"
            feature_file = root / "another" / "strange" / "folder" / "Flow.feature"
            feature_file.parent.mkdir(parents=True)
            java_file.write_text("class Anything {}", encoding="utf-8")
            feature_file.write_text("Feature: Flow", encoding="utf-8")

            scanner = RepositoryScanner({".java", ".feature"})
            files = scanner.scan(root)

        paths = {item.path.name for item in files}
        self.assertEqual(paths, {"Anything.java", "Flow.feature"})

    def test_ignores_generated_directories_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "TARGET" / "nested"
            generated.mkdir(parents=True)
            (generated / "Generated.java").write_text("class Generated {}", encoding="utf-8")
            source = root / "custom" / "src"
            source.mkdir(parents=True)
            (source / "Real.java").write_text("class Real {}", encoding="utf-8")

            files = RepositoryScanner({".java"}).scan(root)

        self.assertEqual([item.path.name for item in files], ["Real.java"])
