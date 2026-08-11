"""Resolve project build metadata used by Eclipse JDT binding analysis.

ARE never guesses dependency types from source text.  This module asks the repository's
build tool for its runtime/test classpath, then supplements it with local outputs and jars.
Maven, Gradle and source-only repositories are supported.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class JavaBuildMetadata:
    classpath: tuple[Path, ...] = tuple()
    source_roots: tuple[Path, ...] = tuple()
    source_level: str | None = None
    diagnostics: tuple[str, ...] = tuple()


class JavaBuildMetadataResolver:
    """Resolve classpath/source roots without repository-specific folder assumptions."""

    _SOURCE_LEVEL = re.compile(r"^(?:1\.)?(?P<major>\d+)$")
    _LOCAL_JAR_PATTERNS = (
        "**/lib/*.jar",
        "**/libs/*.jar",
        "**/target/dependency/*.jar",
        "**/build/libs/*.jar",
    )

    def resolve(
        self,
        repository_root: Path,
        java_files: tuple[Path, ...],
    ) -> JavaBuildMetadata:
        root = repository_root.resolve()
        files = tuple(path.resolve() for path in java_files)
        diagnostics: list[str] = []
        classpath: list[Path] = []
        source_roots: list[Path] = list(self._source_roots_from_paths(root, files))

        module_poms = self._relevant_maven_poms(root, files)
        source_level: str | None = None
        if module_poms:
            for pom in module_poms:
                module_root = pom.parent
                classpath.extend(self._compiled_outputs(module_root))
                source_roots.extend(self._generated_source_roots(module_root))
                command = self._maven_command(root, module_root)
                if command is None:
                    diagnostics.append(
                        "Maven project detected but mvnw/mvn was not available; "
                        f"dependency bindings may be incomplete for {self._display(root, pom)}."
                    )
                    continue
                resolved, error = self._maven_classpath(command, pom)
                classpath.extend(resolved)
                if error:
                    diagnostics.append(
                        f"Maven classpath resolution failed for {self._display(root, pom)}: {error}"
                    )
                if source_level is None:
                    source_level = self._maven_source_level(command, pom)
        else:
            gradle_files = self._gradle_build_files(root)
            if gradle_files:
                gradle_command = self._gradle_command(root)
                if gradle_command is None:
                    diagnostics.append(
                        "Gradle project detected but gradlew/gradle was not available; "
                        "dependency bindings may be incomplete."
                    )
                else:
                    gradle_metadata, error = self._gradle_metadata(root, gradle_command)
                    classpath.extend(gradle_metadata.classpath)
                    source_roots.extend(gradle_metadata.source_roots)
                    source_level = gradle_metadata.source_level
                    if error:
                        diagnostics.append(f"Gradle classpath resolution failed: {error}")

        # These are useful even when Maven/Gradle cannot run (offline/corporate environments).
        classpath.extend(self._local_jars(root))
        classpath.extend(self._all_compiled_outputs(root))
        source_roots.extend(self._all_generated_source_roots(root))

        return JavaBuildMetadata(
            classpath=self._dedupe_existing(classpath),
            source_roots=self._dedupe_existing(source_roots, directories_only=True),
            source_level=self._normalize_source_level(source_level),
            diagnostics=tuple(dict.fromkeys(diagnostics)),
        )

    def _relevant_maven_poms(
        self,
        root: Path,
        java_files: tuple[Path, ...],
    ) -> tuple[Path, ...]:
        poms: dict[Path, None] = {}
        for java_file in java_files:
            current = java_file.parent
            while True:
                pom = current / "pom.xml"
                if pom.is_file():
                    poms[pom.resolve()] = None
                    break
                if current == root or root not in current.parents:
                    break
                current = current.parent
        if not poms and (root / "pom.xml").is_file():
            poms[(root / "pom.xml").resolve()] = None
        return tuple(sorted(poms, key=lambda value: (len(value.parts), str(value))))

    def _maven_command(self, root: Path, module_root: Path) -> list[str] | None:
        current = module_root
        while current == root or root in current.parents:
            names = ("mvnw.cmd", "mvnw") if os.name == "nt" else ("mvnw", "mvnw.cmd")
            for name in names:
                wrapper = current / name
                if wrapper.is_file():
                    return self._executable_command(wrapper)
            if current == root:
                break
            current = current.parent
        executable = shutil.which("mvn")
        return self._executable_command(Path(executable)) if executable else None

    def _maven_classpath(
        self,
        command: list[str],
        pom: Path,
    ) -> tuple[tuple[Path, ...], str | None]:
        with tempfile.TemporaryDirectory(prefix="are_maven_cp_") as directory:
            output = Path(directory) / "classpath.txt"
            completed = self._run(
                [
                    *command,
                    "-q",
                    "-f",
                    str(pom),
                    "-DincludeScope=test",
                    "-Dmdep.outputAbsoluteArtifactFilename=true",
                    f"-Dmdep.outputFile={output}",
                    "dependency:build-classpath",
                ],
                cwd=pom.parent,
            )
            if completed.returncode != 0:
                return tuple(), self._command_error(completed)
            if not output.is_file():
                return tuple(), "Maven completed without producing a dependency classpath."
            text = output.read_text(encoding="utf-8", errors="replace").strip()
            values = tuple(Path(value).resolve() for value in text.split(os.pathsep) if value.strip())
            return values, None

    def _maven_source_level(self, command: list[str], pom: Path) -> str | None:
        for expression in ("maven.compiler.release", "maven.compiler.source", "java.version"):
            completed = self._run(
                [
                    *command,
                    "-q",
                    "-f",
                    str(pom),
                    "help:evaluate",
                    f"-Dexpression={expression}",
                    "-DforceStdout",
                ],
                cwd=pom.parent,
            )
            if completed.returncode != 0:
                continue
            for line in reversed(completed.stdout.splitlines()):
                value = line.strip()
                if not value or value.startswith("[") or "null object" in value.lower():
                    continue
                normalized = self._normalize_source_level(value)
                if normalized:
                    return normalized
        return None

    def _gradle_build_files(self, root: Path) -> tuple[Path, ...]:
        candidates = list(root.glob("**/build.gradle")) + list(root.glob("**/build.gradle.kts"))
        return tuple(path.resolve() for path in candidates if ".gradle" not in path.parts)

    def _gradle_command(self, root: Path) -> list[str] | None:
        names = ("gradlew.bat", "gradlew") if os.name == "nt" else ("gradlew", "gradlew.bat")
        for name in names:
            wrapper = root / name
            if wrapper.is_file():
                return self._executable_command(wrapper)
        executable = shutil.which("gradle")
        return self._executable_command(Path(executable)) if executable else None

    def _gradle_metadata(
        self,
        root: Path,
        command: list[str],
    ) -> tuple[JavaBuildMetadata, str | None]:
        script = """
allprojects {
    afterEvaluate { p ->
        def sourceSets = p.extensions.findByName('sourceSets')
        if (sourceSets != null) {
            ['main', 'test'].each { n ->
                def ss = sourceSets.findByName(n)
                if (ss != null) {
                    println('ARE_SOURCE_ROOT=' + ss.allJava.srcDirs.collect { it.absolutePath }.join(File.pathSeparator))
                    try { println('ARE_CLASSPATH=' + ss.runtimeClasspath.asPath) } catch (Exception ignored) { }
                }
            }
        }
        def javaExt = p.extensions.findByName('java')
        if (javaExt != null) {
            try { println('ARE_SOURCE_LEVEL=' + javaExt.sourceCompatibility) } catch (Exception ignored) { }
        }
    }
}
""".strip()
        with tempfile.TemporaryDirectory(prefix="are_gradle_cp_") as directory:
            init_script = Path(directory) / "are-init.gradle"
            init_script.write_text(script, encoding="utf-8")
            completed = self._run(
                [*command, "-q", "-I", str(init_script), "help"],
                cwd=root,
            )
        if completed.returncode != 0:
            return JavaBuildMetadata(), self._command_error(completed)

        classpath: list[Path] = []
        source_roots: list[Path] = []
        source_level: str | None = None
        for line in completed.stdout.splitlines():
            if line.startswith("ARE_CLASSPATH="):
                classpath.extend(
                    Path(value).resolve()
                    for value in line.partition("=")[2].split(os.pathsep)
                    if value.strip()
                )
            elif line.startswith("ARE_SOURCE_ROOT="):
                source_roots.extend(
                    Path(value).resolve()
                    for value in line.partition("=")[2].split(os.pathsep)
                    if value.strip()
                )
            elif line.startswith("ARE_SOURCE_LEVEL=") and source_level is None:
                source_level = self._normalize_source_level(line.partition("=")[2])
        return JavaBuildMetadata(
            classpath=tuple(classpath),
            source_roots=tuple(source_roots),
            source_level=source_level,
        ), None

    @staticmethod
    def _source_roots_from_paths(root: Path, java_files: tuple[Path, ...]) -> tuple[Path, ...]:
        roots: list[Path] = []
        for file_path in java_files:
            try:
                parts = file_path.relative_to(root).parts
            except ValueError:
                continue
            for index in range(max(0, len(parts) - 2)):
                if parts[index] == "src" and index + 2 < len(parts) and parts[index + 2] == "java":
                    roots.append(root.joinpath(*parts[: index + 3]))
                    break
        return tuple(roots)

    @staticmethod
    def _compiled_outputs(module_root: Path) -> tuple[Path, ...]:
        candidates = (
            module_root / "target" / "classes",
            module_root / "target" / "test-classes",
            module_root / "build" / "classes" / "java" / "main",
            module_root / "build" / "classes" / "java" / "test",
        )
        return tuple(path for path in candidates if path.is_dir())

    @classmethod
    def _generated_source_roots(cls, module_root: Path) -> tuple[Path, ...]:
        roots: list[Path] = []
        for base in (
            module_root / "target" / "generated-sources",
            module_root / "target" / "generated-test-sources",
            module_root / "build" / "generated" / "sources",
        ):
            if base.is_dir():
                roots.extend(path for path in base.rglob("*") if path.is_dir())
        return tuple(roots)

    @classmethod
    def _all_compiled_outputs(cls, root: Path) -> tuple[Path, ...]:
        values: list[Path] = []
        for pattern in (
            "**/target/classes",
            "**/target/test-classes",
            "**/build/classes/java/main",
            "**/build/classes/java/test",
        ):
            values.extend(path for path in root.glob(pattern) if path.is_dir())
        return tuple(values)

    @classmethod
    def _all_generated_source_roots(cls, root: Path) -> tuple[Path, ...]:
        values: list[Path] = []
        for pattern in (
            "**/target/generated-sources",
            "**/target/generated-test-sources",
            "**/build/generated/sources",
        ):
            for base in root.glob(pattern):
                if base.is_dir():
                    values.extend(path for path in base.rglob("*") if path.is_dir())
        return tuple(values)

    @classmethod
    def _local_jars(cls, root: Path) -> tuple[Path, ...]:
        jars: list[Path] = []
        for pattern in cls._LOCAL_JAR_PATTERNS:
            jars.extend(path for path in root.glob(pattern) if path.is_file())
        return tuple(jars)

    @classmethod
    def _normalize_source_level(cls, value: str | None) -> str | None:
        if not value:
            return None
        text = str(value).strip()
        if text.startswith("VERSION_"):
            text = text.removeprefix("VERSION_").replace("_", ".")
        match = cls._SOURCE_LEVEL.fullmatch(text)
        return match.group("major") if match else None

    @staticmethod
    def _dedupe_existing(
        values: list[Path] | tuple[Path, ...],
        *,
        directories_only: bool = False,
    ) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[Path] = set()
        for value in values:
            path = value.resolve()
            if path in seen or not path.exists():
                continue
            if directories_only and not path.is_dir():
                continue
            seen.add(path)
            result.append(path)
        return tuple(result)

    @staticmethod
    def _executable_command(executable: Path) -> list[str]:
        if os.name == "nt" and executable.suffix.lower() in {".cmd", ".bat"}:
            return ["cmd", "/c", str(executable)]
        return [str(executable)]

    @staticmethod
    def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    @staticmethod
    def _command_error(completed: subprocess.CompletedProcess[str]) -> str:
        detail = (completed.stderr or completed.stdout).strip()
        if not detail:
            return f"command exited with code {completed.returncode}"
        return detail.splitlines()[-1][:500]

    @staticmethod
    def _display(root: Path, path: Path) -> str:
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
