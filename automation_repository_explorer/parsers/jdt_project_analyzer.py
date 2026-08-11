"""Project-level Java analysis backed by Eclipse JDT."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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


class JdtProjectAnalyzer:
    """Run one Eclipse JDT batch analysis for all Java files in a repository."""

    BACKEND_NAME = "eclipse-jdt"

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

        jar_path = self._ensure_bridge()
        java_executable = shutil.which("java")
        if java_executable is None:
            raise ParserError(
                "Eclipse JDT analysis requires Java on PATH. "
                "Install/configure a JDK and run ARE again."
            )

        repository_root = repository_root.resolve()
        build_metadata = self._build_metadata_resolver.resolve(repository_root, java_files)

        with tempfile.TemporaryDirectory(prefix="are_jdt_") as directory:
            work = Path(directory)
            file_list = work / "java-files.txt"
            classpath_file = work / "classpath.txt"
            source_roots_file = work / "source-roots.txt"

            self._write_path_list(file_list, java_files)
            self._write_path_list(classpath_file, build_metadata.classpath)
            self._write_path_list(source_roots_file, build_metadata.source_roots)

            command = [
                java_executable,
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

            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ParserError(
                "Eclipse JDT analyzer failed" + (f": {detail}" if detail else ".")
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
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
        return JdtAnalysisResult(
            classes=classes,
            diagnostics=build_diagnostics + jdt_diagnostics,
        )

    def _ensure_bridge(self) -> Path:
        pom = self._bridge_root / "pom.xml"
        jar = self._bridge_root / "target" / "are-jdt-bridge.jar"
        source = (
            self._bridge_root
            / "src"
            / "main"
            / "java"
            / "com"
            / "are"
            / "jdt"
            / "JdtAnalyzerMain.java"
        )
        if not pom.is_file() or not source.is_file():
            raise ParserError(f"Eclipse JDT bridge source is missing under {self._bridge_root}.")

        newest_source = max(pom.stat().st_mtime, source.stat().st_mtime)
        if jar.is_file() and jar.stat().st_mtime >= newest_source:
            return jar

        maven = self._maven_command()
        if maven is None:
            raise ParserError(
                "Eclipse JDT bridge needs Maven for its first local build. "
                "Put mvn/mvnw on PATH, then run ARE again."
            )

        command = [*maven, "-q", "-f", str(pom), "-DskipTests", "package"]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0 or not jar.is_file():
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ParserError(
                "Could not build the Eclipse JDT bridge" + (f": {detail}" if detail else ".")
            )
        return jar

    def _maven_command(self) -> list[str] | None:
        wrapper_names = ("mvnw.cmd", "mvnw") if os.name == "nt" else ("mvnw", "mvnw.cmd")
        for wrapper_name in wrapper_names:
            wrapper = self._bridge_root / wrapper_name
            if wrapper.is_file():
                return self._executable_command(wrapper)

        maven = shutil.which("mvn")
        if maven:
            return self._executable_command(Path(maven))
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
            return ["cmd", "/c", str(executable)]
        return [str(executable)]

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
