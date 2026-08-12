"""Project-level Java analysis backed by Eclipse JDT."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from automation_repository_explorer.core.exceptions import ParserError
from automation_repository_explorer.models.domain import (
    JavaClass,
    JavaMethod,
    SourceLocation,
    StepDefinition,
)
from automation_repository_explorer.parsers.java_build_metadata import JavaBuildMetadataResolver


@dataclass(frozen=True, slots=True)
class JdtDiagnostic:
    file_path: Path
    message: str
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class JdtAnalysisResult:
    classes: tuple[JavaClass, ...]
    diagnostics: tuple[JdtDiagnostic, ...] = tuple()
    semantic_complete: bool = True


class JdtProjectAnalyzer:
    """Run one Eclipse JDT batch analysis for all Java files in a repository."""

    BACKEND_NAME = "eclipse-jdt"
    TRACE_PREFIX = "[ARE:JDT]"

    def __init__(
        self,
        bridge_root: Path | None = None,
        build_metadata_resolver: JavaBuildMetadataResolver | None = None,
    ) -> None:
        self._bridge_root = bridge_root or Path(__file__).resolve().parents[2] / "jdt_bridge"
        self._build_metadata_resolver = build_metadata_resolver or JavaBuildMetadataResolver()

    def analyze(
        self,
        repository_root: Path,
        java_files: tuple[Path, ...],
    ) -> JdtAnalysisResult:
        if not java_files:
            return JdtAnalysisResult(classes=tuple())

        self._trace(f"Starting Java analysis for {len(java_files)} file(s).")
        self._trace(f"Bridge root: {self._bridge_root}")

        jar_path = self._ensure_bridge()
        self._trace(f"Using JDT bridge JAR: {jar_path}")

        java_command = self._java_command()
        if java_command is None:
            self._trace("Java executable was not found on PATH.")
            raise ParserError(
                "Eclipse JDT analysis requires Java on PATH. "
                "Install/configure a JDK and run ARE again."
            )
        self._trace(f"Java launcher: {self._format_command(java_command)}")

        repository_root = repository_root.resolve()
        build_metadata = self._build_metadata_resolver.resolve(repository_root, java_files)
        self._trace(
            "Build metadata: "
            f"{len(build_metadata.classpath)} classpath item(s), "
            f"{len(build_metadata.source_roots)} source root(s), "
            f"source level={build_metadata.source_level or 'JDT-auto'}."
        )

        with tempfile.TemporaryDirectory(prefix="are_jdt_") as directory:
            work = Path(directory)
            file_list = work / "java-files.txt"
            classpath_file = work / "classpath.txt"
            source_roots_file = work / "source-roots.txt"

            self._write_path_list(file_list, java_files)
            self._write_path_list(classpath_file, build_metadata.classpath)
            self._write_path_list(source_roots_file, build_metadata.source_roots)

            command = [
                *java_command,
                "-jar",
                str(jar_path),
                "--project-root",
                str(repository_root),
                "--file-list",
                str(file_list),
                "--classpath-file",
                str(classpath_file),
                "--source-root-list",
                str(source_roots_file),
            ]
            if build_metadata.source_level:
                command.extend(["--source-level", build_metadata.source_level])

            completed = self._run(command)

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            self._trace(f"JDT analyzer failed with exit code {completed.returncode}.")
            raise ParserError(
                "Eclipse JDT analyzer failed" + (f": {detail}" if detail else ".")
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            self._trace(f"JDT analyzer returned invalid JSON: {exc}")
            raise ParserError(f"Eclipse JDT analyzer returned invalid JSON: {exc}") from exc

        classes = tuple(self._map_class(item) for item in payload.get("classes", []))
        build_diagnostics = tuple(
            JdtDiagnostic(repository_root, message, "warning")
            for message in build_metadata.diagnostics
        )
        jdt_diagnostics = tuple(
            self._map_diagnostic(item, repository_root)
            for item in payload.get("diagnostics", [])
        )
        diagnostics = build_diagnostics + jdt_diagnostics
        self._trace(
            f"Analysis completed: {len(classes)} class(es), "
            f"{len(diagnostics)} diagnostic(s)."
        )
        return JdtAnalysisResult(
            classes=classes,
            diagnostics=diagnostics,
            semantic_complete=not diagnostics,
        )

    def _ensure_bridge(self) -> Path:
        pom = self._bridge_root / "pom.xml"
        jar = self._bridge_root / "target" / "are-jdt-bridge.jar"
        source_root = self._bridge_root / "src" / "main" / "java"
        sources = tuple(sorted(source_root.rglob("*.java"))) if source_root.is_dir() else tuple()
        if not pom.is_file() or not sources:
            raise ParserError(f"Eclipse JDT bridge source is missing under {self._bridge_root}.")

        self._trace(f"JDT bridge contains {len(sources)} Java source file(s).")
        bridge_inputs = (pom, *sources)
        if self._bridge_is_current(jar, bridge_inputs):
            self._trace("JDT bridge is already built and up to date.")
            return jar

        self._trace("JDT bridge needs a local build; locating Maven.")
        maven = self._maven_command()
        if maven is None:
            self._trace("Maven executable/wrapper was not found on PATH.")
            raise ParserError(
                "Eclipse JDT bridge needs Maven for its first local build. "
                "Put mvn/mvnw on PATH, then run ARE again."
            )

        self._trace(f"Maven launcher: {self._format_command(maven)}")
        command = [*maven, "-q", "-f", str(pom), "-DskipTests", "package"]
        completed = self._run(command)
        if completed.returncode != 0 or not jar.is_file():
            detail = completed.stderr.strip() or completed.stdout.strip()
            self._trace(
                "JDT bridge build failed: "
                f"exit={completed.returncode}, jar_created={jar.is_file()}."
            )
            raise ParserError(
                "Could not build the Eclipse JDT bridge" + (f": {detail}" if detail else ".")
            )
        self._trace("JDT bridge build completed successfully.")
        return jar

    @staticmethod
    def _bridge_is_current(jar: Path, bridge_inputs: tuple[Path, ...]) -> bool:
        """Return true only when the JAR is at least as new as every bridge input."""
        if not jar.is_file() or not bridge_inputs:
            return False
        jar_mtime = jar.stat().st_mtime_ns
        return all(path.is_file() and path.stat().st_mtime_ns <= jar_mtime for path in bridge_inputs)

    def _java_command(self) -> list[str] | None:
        if os.name == "nt":
            executable = self._which_windows(("java.exe", "java.cmd", "java.bat"))
        else:
            executable = shutil.which("java")
        return self._executable_command(Path(executable)) if executable else None

    def _maven_command(self) -> list[str] | None:
        wrapper_names = ("mvnw.cmd", "mvnw.bat") if os.name == "nt" else ("mvnw",)
        for wrapper_name in wrapper_names:
            wrapper = self._bridge_root / wrapper_name
            if wrapper.is_file():
                return self._executable_command(wrapper)

        if os.name == "nt":
            executable = self._which_windows(("mvn.cmd", "mvn.bat", "mvn.exe"))
        else:
            executable = shutil.which("mvn")
        return self._executable_command(Path(executable)) if executable else None

    @staticmethod
    def _which_windows(names: tuple[str, ...]) -> str | None:
        """Return only a Windows-native executable/script, never a POSIX shim."""
        for name in names:
            executable = shutil.which(name)
            if not executable:
                continue
            suffix = Path(executable).suffix.lower()
            if suffix in {".exe", ".cmd", ".bat"}:
                return executable
        return None

    @staticmethod
    def _write_path_list(file_path: Path, values: tuple[Path, ...]) -> None:
        file_path.write_text(
            "\n".join(str(path.resolve()) for path in values),
            encoding="utf-8",
        )

    @staticmethod
    def _executable_command(executable: Path) -> list[str]:
        if os.name == "nt" and executable.suffix.lower() in {".cmd", ".bat"}:
            # `cmd /s /c <batch path>` is fragile when the batch path contains spaces.
            # `call` makes the quoted batch path an argument to a cmd builtin instead of
            # the first token of the command string, so paths under "Program Files" work.
            command_processor = os.environ.get("COMSPEC") or "cmd.exe"
            return [command_processor, "/d", "/c", "call", str(executable)]
        return [str(executable)]

    @classmethod
    def _run(cls, command: list[str]) -> subprocess.CompletedProcess[str]:
        cls._trace(f"EXEC {cls._format_command(command)}")
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            cls._trace(f"EXEC failed before process start: {exc.__class__.__name__}: {exc}")
            return subprocess.CompletedProcess(
                args=command,
                returncode=getattr(exc, "winerror", None) or 126,
                stdout="",
                stderr=f"{exc.__class__.__name__}: {exc}",
            )

        cls._trace(f"EXIT {completed.returncode}")
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            if detail:
                cls._trace(f"PROCESS ERROR: {detail[:2000]}")
        return completed

    @staticmethod
    def _format_command(command: list[str]) -> str:
        return subprocess.list2cmdline(command)

    @classmethod
    def _trace(cls, message: str) -> None:
        print(f"{cls.TRACE_PREFIX} {message}", file=sys.stderr, flush=True)

    def _map_class(self, item: dict[str, Any]) -> JavaClass:
        file_path = Path(str(item["file"])).resolve()
        methods = tuple(self._map_method(method, file_path) for method in item.get("methods", []))
        return JavaClass(
            name=str(item.get("name", "")),
            package=str(item.get("package", "")),
            imports=tuple(str(value) for value in item.get("imports", [])),
            location=SourceLocation(
                file_path,
                int(item.get("line", 1)),
                int(item.get("column", 1)),
            ),
            methods=methods,
            binding_key=_optional_text(item.get("bindingKey")),
            analysis_backend=self.BACKEND_NAME,
        )

    @staticmethod
    def _map_method(item: dict[str, Any], file_path: Path) -> JavaMethod:
        step_data = item.get("stepDefinition")
        step_definition = None
        if isinstance(step_data, dict):
            step_definition = StepDefinition(
                keyword=str(step_data.get("keyword", "")),
                pattern=str(step_data.get("pattern", "")),
                location=SourceLocation(
                    file_path,
                    int(step_data.get("line", item.get("line", 1))),
                    int(step_data.get("column", 1)),
                ),
            )

        call_expressions = tuple(str(value) for value in item.get("callExpressions", []))
        calls = tuple(_simple_call_name(value) for value in call_expressions)
        return JavaMethod(
            name=str(item.get("name", "")),
            return_type=str(item.get("returnType", "")),
            parameters=tuple(str(value) for value in item.get("parameters", [])),
            location=SourceLocation(
                file_path,
                int(item.get("line", 1)),
                int(item.get("column", 1)),
            ),
            end_line=int(item.get("endLine", item.get("line", 1))),
            body=str(item.get("body", "")),
            calls=calls,
            string_literals=tuple(str(value) for value in item.get("stringLiterals", [])),
            step_definition=step_definition,
            call_expressions=call_expressions,
            is_constructor=bool(item.get("constructor", False)),
            binding_key=_optional_text(item.get("bindingKey")),
            resolved_call_keys=tuple(str(value) for value in item.get("resolvedCallKeys", [])),
            unresolved_call_expressions=tuple(
                str(value) for value in item.get("unresolvedCalls", [])
            ),
        )

    @staticmethod
    def _map_diagnostic(item: dict[str, Any], repository_root: Path) -> JdtDiagnostic:
        raw_path = item.get("file")
        file_path = Path(str(raw_path)).resolve() if raw_path else repository_root.resolve()
        return JdtDiagnostic(
            file_path=file_path,
            message=str(item.get("message", "Eclipse JDT diagnostic")),
            severity=str(item.get("severity", "warning")).lower(),
        )


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _simple_call_name(call_expression: str) -> str:
    clean = call_expression.strip()
    if clean.startswith("new "):
        clean = clean[4:]
    clean = clean.split("(", 1)[0]
    return clean.rsplit(".", 1)[-1]
