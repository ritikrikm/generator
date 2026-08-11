"""Tests for reusable IntelliJ source navigation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation_repository_explorer.local_ui.ide_launcher import IntelliJLauncher


class IntelliJLauncherTests(unittest.TestCase):
    def test_build_command_includes_exact_line_and_file(self) -> None:
        command = IntelliJLauncher.build_command(
            Path("idea64.exe"),
            Path("C:/repo/src/test/java/Steps.java"),
            line=141,
        )
        self.assertEqual(
            command,
            ["idea64.exe", "--line", "141", "C:/repo/src/test/java/Steps.java"],
        )

    def test_open_file_launches_only_inside_selected_project(self) -> None:
        launched: list[list[str]] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "src" / "Steps.java"
            target.parent.mkdir(parents=True)
            target.write_text("class Steps {}", encoding="utf-8")

            launcher = IntelliJLauncher(
                executable_resolver=lambda: Path("idea64.exe"),
                process_launcher=lambda command: launched.append(list(command)),
            )
            result = launcher.open_file(target, line=7, project_root=root)

        self.assertTrue(result.success)
        self.assertEqual(len(launched), 1)
        self.assertEqual(launched[0][-3:], ["--line", "7", str(target.resolve())])

    def test_open_file_rejects_path_outside_selected_project(self) -> None:
        launched: list[list[str]] = []
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir)
            target = Path(other_dir) / "Outside.java"
            target.write_text("class Outside {}", encoding="utf-8")

            launcher = IntelliJLauncher(
                executable_resolver=lambda: Path("idea64.exe"),
                process_launcher=lambda command: launched.append(list(command)),
            )
            result = launcher.open_file(target, project_root=project_root)

        self.assertFalse(result.success)
        self.assertEqual(launched, [])
        self.assertIn("outside the scanned repository", result.message)


if __name__ == "__main__":
    unittest.main()
