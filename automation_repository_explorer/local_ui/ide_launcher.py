"""Open repository files in IntelliJ without repository-specific paths."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class IdeLaunchResult:
    """Outcome of an IDE file-open request."""

    success: bool
    message: str
    executable: str = ""


class IntelliJLauncher:
    """Discover IntelliJ locally and open an exact repository file/line.

    ARE never stores a user-specific IntelliJ path. Discovery is performed at runtime from
    PATH, IntelliJ home environment variables, Windows App Paths, and standard JetBrains
    installation roots. Passing an absolute file path to the IntelliJ launcher lets a running
    IDE reuse the project that owns that file; otherwise IntelliJ starts normally.
    """

    _ENV_HOME_KEYS = ("IDEA_HOME", "INTELLIJ_HOME", "JETBRAINS_IDEA_HOME")
    _COMMAND_NAMES = ("idea64.exe", "idea.exe", "idea")

    def __init__(
        self,
        *,
        executable_resolver: Callable[[], Path | None] | None = None,
        process_launcher: Callable[[Sequence[str]], object] | None = None,
    ) -> None:
        self._executable_resolver = executable_resolver or self.discover_executable
        self._process_launcher = process_launcher or self._launch_process

    def open_file(
        self,
        file_path: Path,
        *,
        line: int | None = None,
        project_root: Path | None = None,
    ) -> IdeLaunchResult:
        """Open a file in IntelliJ, optionally at a line, after repository validation."""

        target = file_path.expanduser().resolve()
        if not target.is_file():
            return IdeLaunchResult(False, f"File does not exist: {target}")

        if project_root is not None:
            root = project_root.expanduser().resolve()
            try:
                target.relative_to(root)
            except ValueError:
                return IdeLaunchResult(
                    False,
                    "ARE refused to open the file because it is outside the scanned repository.",
                )

        executable = self._executable_resolver()
        if executable is None:
            return IdeLaunchResult(
                False,
                "IntelliJ launcher was not found. Add idea/idea64.exe to PATH or set IDEA_HOME.",
            )

        command = self.build_command(executable, target, line=line)
        try:
            self._process_launcher(command)
        except OSError as exc:
            return IdeLaunchResult(False, f"Could not start IntelliJ: {exc}", str(executable))

        location = f" line {line}" if line and line > 0 else ""
        return IdeLaunchResult(
            True,
            f"Opened {target.name}{location} in IntelliJ.",
            str(executable),
        )

    @staticmethod
    def build_command(
        executable: Path,
        file_path: Path,
        *,
        line: int | None = None,
    ) -> list[str]:
        """Build IntelliJ's normal command-line file navigation request."""

        command = [str(executable)]
        if line is not None and line > 0:
            command.extend(("--line", str(line)))
        command.append(str(file_path))
        return command

    @classmethod
    def discover_executable(cls) -> Path | None:
        """Discover IntelliJ without hardcoding any repository or user path."""

        for command in cls._COMMAND_NAMES:
            resolved = shutil.which(command)
            if resolved:
                return Path(resolved)

        for key in cls._ENV_HOME_KEYS:
            home = os.environ.get(key)
            if not home:
                continue
            candidate = cls._candidate_from_home(Path(home))
            if candidate is not None:
                return candidate

        if os.name == "nt":
            registry_candidate = cls._windows_app_path()
            if registry_candidate is not None:
                return registry_candidate
            for candidate in cls._windows_install_candidates():
                if candidate.is_file():
                    return candidate

        return None

    @classmethod
    def _candidate_from_home(cls, home: Path) -> Path | None:
        names = ("idea64.exe", "idea.exe") if os.name == "nt" else ("idea",)
        for name in names:
            candidate = home.expanduser() / "bin" / name
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _windows_app_path() -> Path | None:
        try:
            import winreg  # type: ignore[attr-defined]
        except ImportError:  # pragma: no cover - Windows-only
            return None

        key_paths = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\idea64.exe",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\idea.exe",
        )
        hives = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
        for hive in hives:
            for key_path in key_paths:
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        value, _kind = winreg.QueryValueEx(key, None)
                except OSError:
                    continue
                candidate = Path(str(value).strip('"'))
                if candidate.is_file():
                    return candidate
        return None

    @staticmethod
    def _windows_install_candidates() -> tuple[Path, ...]:
        """Return dynamically discovered IntelliJ launcher candidates on Windows."""

        roots = tuple(
            Path(value)
            for key in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)")
            if (value := os.environ.get(key))
        )
        patterns = (
            "JetBrains/Toolbox/apps/IDEA*/**/bin/idea64.exe",
            "JetBrains/IntelliJ IDEA*/bin/idea64.exe",
            "Programs/IntelliJ IDEA*/bin/idea64.exe",
        )
        candidates: list[Path] = []
        for root in roots:
            for pattern in patterns:
                candidates.extend(root.glob(pattern))
        candidates.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
        return tuple(candidates)

    @staticmethod
    def _launch_process(command: Sequence[str]) -> subprocess.Popen[bytes]:
        creation_flags = 0
        if os.name == "nt":
            creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return subprocess.Popen(  # noqa: S603 - command is locally discovered, not shell text
            list(command),
            shell=False,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
