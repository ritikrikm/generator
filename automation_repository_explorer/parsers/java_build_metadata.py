"""Resolve project build metadata used by Eclipse JDT binding analysis.

ARE never guesses dependency types from source text. This module asks the repository's
build tool for its runtime/test classpath and declared Java language level, then supplements
that metadata with local outputs and jars. Maven, Gradle and source-only repositories are
supported without hard-coding a particular Java release.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class JavaBuildMetadata:
    classpath: tuple[Path, ...] = tuple()
    source_roots: tuple[Path, ...] = tuple()
    source_level: str | None = None
    diagnostics: tuple[str, ...] = tuple()


class JavaBuildMetadataResolver:
    """Resolve classpath/source roots/language level from real project build metadata."""

    TRACE_PREFIX = "[ARE:JAVA-BUILD]"
    _SOURCE_LEVEL = re.compile(r"^(?:1[._])?(?P<major>\d+)(?:[._-].*)?$")
    _MAVEN_LEVEL_EXPRESSIONS = (
        "maven.compiler.testRelease",
        "maven.compiler.release",
        "maven.compiler.testSource",
        "maven.compiler.source",
        "java.version",
    )
    _MAVEN_COMPILER_LEVEL_ELEMENTS = ("testRelease", "release", "testSource", "source")
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
        source_levels: list[str] = []

        self._trace(f"Resolving Java build metadata for {root}.")
        module_poms = self._relevant_maven_poms(root, files)
        if module_poms:
            self._trace(f"Detected {len(module_poms)} relevant Maven module(s).")
            for pom in module_poms:
                module_root = pom.parent
                display = self._display(root, pom)
                classpath.extend(self._compiled_outputs(module_root))
                source_roots.extend(self._generated_source_roots(module_root))

                raw_level = self._source_level_from_pom_file(pom)
                if raw_level:
                    source_levels.append(raw_level)
                    self._trace(f"{display}: raw POM Java level candidate={raw_level}.")

                command = self._maven_command(root, module_root)
                if command is None:
                    diagnostics.append(
                        "Maven project detected but a Windows-native mvn/mvnw or POSIX mvn/mvnw "
                        f"was not available for {display}; dependency bindings may be incomplete."
                    )
                    continue

                self._trace(f"{display}: Maven launcher={self._format_command(command)}")
                resolved, error = self._maven_classpath(command, pom)
                classpath.extend(resolved)
                if error:
                    diagnostics.append(f"Maven classpath resolution failed for {display}: {error}")
                    self._trace(f"{display}: Maven classpath resolution failed: {error}")
                else:
                    self._trace(f"{display}: resolved {len(resolved)} Maven dependency path(s).")

                maven_level = self._maven_source_level(command, pom)
                if maven_level:
                    source_levels.append(maven_level)
                    self._trace(f"{display}: effective Maven Java level={maven_level}.")
        else:
            gradle_files = self._gradle_build_files(root)
            if gradle_files:
                self._trace(f"Detected {len(gradle_files)} Gradle build file(s).")
                gradle_command = self._gradle_command(root)
                if gradle_command is None:
                    diagnostics.append(
                        "Gradle project detected but a native gradle/gradlew executable was not available; "
                        "dependency bindings may be incomplete."
                    )
                else:
                    self._trace(f"Gradle launcher={self._format_command(gradle_command)}")
                    gradle_metadata, error = self._gradle_metadata(root, gradle_command)
                    classpath.extend(gradle_metadata.classpath)
                    source_roots.extend(gradle_metadata.source_roots)
                    if gradle_metadata.source_level:
                        source_levels.append(gradle_metadata.source_level)
                    if error:
                        diagnostics.append(f"Gradle classpath resolution failed: {error}")
                        self._trace(f"Gradle metadata resolution failed: {error}")

        classpath.extend(self._local_jars(root))
        classpath.extend(self._all_compiled_outputs(root))
        source_roots.extend(self._all_generated_source_roots(root))

        source_level = self._highest_source_level(source_levels)
        if source_level:
            unique_levels = sorted(set(source_levels), key=self._source_level_sort_key)
            self._trace(
                f"Selected Java source level {source_level} from candidate(s): "
                + ", ".join(unique_levels)
                + "."
            )
        else:
            self._trace(
                "No project Java source level declaration was resolved; "
                "Eclipse JDT will select its latest fully supported source level dynamically."
            )

        resolved_classpath = self._dedupe_existing(classpath)
        resolved_roots = self._dedupe_existing(source_roots, directories_only=True)
        self._trace(
            f"Metadata complete: {len(resolved_classpath)} classpath item(s), "
            f"{len(resolved_roots)} source root(s), source level={source_level or 'JDT-auto'}."
        )
        return JavaBuildMetadata(
            classpath=resolved_classpath,
            source_roots=resolved_roots,
            source_level=source_level,
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
            names = ("mvnw.cmd", "mvnw.bat") if os.name == "nt" else ("mvnw",)
            for name in names:
                wrapper = current / name
                if wrapper.is_file():
                    return self._executable_command(wrapper)
            if current == root:
                break
            current = current.parent

        if os.name == "nt":
            executable = self._which_windows(("mvn.cmd", "mvn.bat", "mvn.exe"))
        else:
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
        effective_level = self._maven_effective_pom_source_level(command, pom)
        if effective_level:
            return effective_level

        candidates: list[str] = []
        for expression in self._MAVEN_LEVEL_EXPRESSIONS:
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
                    candidates.append(normalized)
                    break
        return self._highest_source_level(candidates) or self._source_level_from_pom_file(pom)

    def _maven_effective_pom_source_level(
        self,
        command: list[str],
        pom: Path,
    ) -> str | None:
        with tempfile.TemporaryDirectory(prefix="are_maven_effective_") as directory:
            output = Path(directory) / "effective-pom.xml"
            completed = self._run(
                [
                    *command,
                    "-q",
                    "-f",
                    str(pom),
                    "help:effective-pom",
                    f"-Doutput={output}",
                ],
                cwd=pom.parent,
            )
            if completed.returncode != 0 or not output.is_file():
                return None
            return self._source_level_from_pom_file(output)

    def _source_level_from_pom_file(self, pom: Path) -> str | None:
        try:
            root = ET.parse(pom).getroot()
        except (OSError, ET.ParseError):
            return None

        properties = self._pom_properties(root)
        candidates: list[str] = []
        for key in self._MAVEN_LEVEL_EXPRESSIONS:
            value = properties.get(key)
            normalized = self._normalize_source_level(self._resolve_property(value, properties))
            if normalized:
                candidates.append(normalized)

        for plugin in root.iter():
            if self._local_name(plugin.tag) != "plugin":
                continue
            artifact_id = self._direct_child_text(plugin, "artifactId")
            if artifact_id != "maven-compiler-plugin":
                continue
            for element in plugin.iter():
                if self._local_name(element.tag) not in self._MAVEN_COMPILER_LEVEL_ELEMENTS:
                    continue
                value = self._resolve_property(element.text, properties)
                normalized = self._normalize_source_level(value)
                if normalized:
                    candidates.append(normalized)
        return self._highest_source_level(candidates)

    @classmethod
    def _pom_properties(cls, root: ET.Element) -> dict[str, str]:
        values: dict[str, str] = {}
        for element in root.iter():
            if cls._local_name(element.tag) != "properties":
                continue
            for child in list(element):
                name = cls._local_name(child.tag)
                text = (child.text or "").strip()
                if name and text:
                    values[name] = text
        return values

    @staticmethod
    def _resolve_property(value: str | None, properties: dict[str, str]) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        seen: set[str] = set()
        while text.startswith("${") and text.endswith("}"):
            key = text[2:-1].strip()
            if not key or key in seen or key not in properties:
                break
            seen.add(key)
            text = properties[key].strip()
        return text

    def _gradle_build_files(self, root: Path) -> tuple[Path, ...]:
        candidates = list(root.glob("**/build.gradle")) + list(root.glob("**/build.gradle.kts"))
        return tuple(path.resolve() for path in candidates if ".gradle" not in path.parts)

    def _gradle_command(self, root: Path) -> list[str] | None:
        names = ("gradlew.bat", "gradlew.cmd") if os.name == "nt" else ("gradlew",)
        for name in names:
            wrapper = root / name
            if wrapper.is_file():
                return self._executable_command(wrapper)

        if os.name == "nt":
            executable = self._which_windows(("gradle.bat", "gradle.cmd", "gradle.exe"))
        else:
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
            sourceSets.each { ss ->
                try { println('ARE_SOURCE_ROOT=' + ss.allJava.srcDirs.collect { it.absolutePath }.join(File.pathSeparator)) } catch (Exception ignored) { }
                try { println('ARE_CLASSPATH=' + ss.runtimeClasspath.asPath) } catch (Exception ignored) { }
            }
        }
        def javaExt = p.extensions.findByName('java')
        if (javaExt != null) {
            try { println('ARE_SOURCE_LEVEL=' + javaExt.sourceCompatibility) } catch (Exception ignored) { }
            try {
                def languageVersion = javaExt.toolchain.languageVersion.orNull
                if (languageVersion != null) println('ARE_SOURCE_LEVEL=' + languageVersion.asInt())
            } catch (Exception ignored) { }
        }
        try {
            p.tasks.withType(org.gradle.api.tasks.compile.JavaCompile).all { t ->
                try { println('ARE_SOURCE_LEVEL=' + t.sourceCompatibility) } catch (Exception ignored) { }
                try {
                    def release = t.options.release.orNull
                    if (release != null) println('ARE_SOURCE_LEVEL=' + release)
                } catch (Exception ignored) { }
            }
        } catch (Exception ignored) { }
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
        source_levels: list[str] = []
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
            elif line.startswith("ARE_SOURCE_LEVEL="):
                normalized = self._normalize_source_level(line.partition("=")[2])
                if normalized:
                    source_levels.append(normalized)
        return JavaBuildMetadata(
            classpath=tuple(classpath),
            source_roots=tuple(source_roots),
            source_level=self._highest_source_level(source_levels),
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
        text = str(value).strip().strip("\"'")
        if not text or text.startswith("${"):
            return None
        upper = text.upper()
        for prefix in ("JAVAVERSION.", "VERSION_", "JAVA_", "JDK_"):
            if upper.startswith(prefix):
                text = text[len(prefix) :]
                upper = text.upper()
        text = text.replace("_", ".")
        match = cls._SOURCE_LEVEL.fullmatch(text)
        if not match:
            return None
        major = int(match.group("major"))
        if text.startswith("1.") or text.startswith("1_"):
            parts = re.split(r"[._-]", text)
            if len(parts) > 1 and parts[1].isdigit():
                major = int(parts[1])
        return str(major) if major > 0 else None

    @classmethod
    def _highest_source_level(cls, values: list[str] | tuple[str, ...]) -> str | None:
        normalized = [cls._normalize_source_level(value) for value in values]
        valid = [value for value in normalized if value is not None]
        return max(valid, key=cls._source_level_sort_key) if valid else None

    @staticmethod
    def _source_level_sort_key(value: str) -> int:
        try:
            return int(value)
        except ValueError:
            return -1

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _direct_child_text(cls, element: ET.Element, name: str) -> str | None:
        for child in list(element):
            if cls._local_name(child.tag) == name:
                value = (child.text or "").strip()
                return value or None
        return None

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
    def _which_windows(names: tuple[str, ...]) -> str | None:
        """Return only native Windows executables/scripts and reject POSIX shims."""
        for name in names:
            executable = shutil.which(name)
            if not executable:
                continue
            suffix = Path(executable).suffix.lower()
            if suffix in {".exe", ".cmd", ".bat"}:
                return executable
        return None

    @staticmethod
    def _executable_command(executable: Path) -> list[str]:
        if os.name == "nt" and executable.suffix.lower() in {".cmd", ".bat"}:
            command_processor = os.environ.get("COMSPEC") or "cmd.exe"
            return [command_processor, "/d", "/c", "call", str(executable)]
        return [str(executable)]

    @staticmethod
    def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            return subprocess.CompletedProcess(
                args=command,
                returncode=getattr(exc, "winerror", None) or 126,
                stdout="",
                stderr=f"{exc.__class__.__name__}: {exc}",
            )

    @staticmethod
    def _command_error(completed: subprocess.CompletedProcess[str]) -> str:
        detail = (completed.stderr or completed.stdout).strip()
        if not detail:
            return f"command exited with code {completed.returncode}"
        return detail.splitlines()[-1][:500]

    @staticmethod
    def _format_command(command: list[str]) -> str:
        return subprocess.list2cmdline(command)

    @classmethod
    def _trace(cls, message: str) -> None:
        print(f"{cls.TRACE_PREFIX} {message}", file=sys.stderr, flush=True)

    @staticmethod
    def _display(root: Path, path: Path) -> str:
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
