import os
from pathlib import Path

import pytest

from automation_repository_explorer.parsers.java_build_metadata import JavaBuildMetadataResolver


def test_detects_generic_maven_modules_and_source_sets(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    module_a = root / "module-a"
    module_b = root / "nested" / "module-b"
    java_a = module_a / "src" / "test" / "java" / "a" / "ATest.java"
    java_b = module_b / "src" / "integrationTest" / "java" / "b" / "BTest.java"

    java_a.parent.mkdir(parents=True)
    java_b.parent.mkdir(parents=True)
    (module_a / "pom.xml").write_text("<project/>", encoding="utf-8")
    (module_b / "pom.xml").write_text("<project/>", encoding="utf-8")
    java_a.write_text("package a; class ATest {}", encoding="utf-8")
    java_b.write_text("package b; class BTest {}", encoding="utf-8")

    resolver = JavaBuildMetadataResolver()
    poms = resolver._relevant_maven_poms(root.resolve(), (java_a.resolve(), java_b.resolve()))
    roots = resolver._source_roots_from_paths(root.resolve(), (java_a.resolve(), java_b.resolve()))

    assert set(poms) == {(module_a / "pom.xml").resolve(), (module_b / "pom.xml").resolve()}
    assert (module_a / "src" / "test" / "java").resolve() in set(roots)
    assert (module_b / "src" / "integrationTest" / "java").resolve() in set(roots)


def test_source_level_normalization_handles_legacy_current_and_future_style_values() -> None:
    resolver = JavaBuildMetadataResolver()

    assert resolver._normalize_source_level("1.8") == "8"
    assert resolver._normalize_source_level("8") == "8"
    assert resolver._normalize_source_level("17") == "17"
    assert resolver._normalize_source_level("17.0.12") == "17"
    assert resolver._normalize_source_level("VERSION_21") == "21"
    assert resolver._normalize_source_level("JavaVersion.VERSION_22") == "22"
    assert resolver._normalize_source_level("JDK_25") == "25"
    assert resolver._normalize_source_level("26-ea") == "26"
    assert resolver._normalize_source_level("${java.version}") is None


def test_maven_compiler_plugin_release_resolves_property_without_version_hardcoding(tmp_path: Path) -> None:
    pom = tmp_path / "pom.xml"
    pom.write_text(
        """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <properties>
    <project.java.level>21</project.java.level>
  </properties>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <configuration>
          <release>${project.java.level}</release>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
""",
        encoding="utf-8",
    )

    assert JavaBuildMetadataResolver()._source_level_from_pom_file(pom) == "21"


def test_maven_test_release_wins_when_it_requires_newer_test_language(tmp_path: Path) -> None:
    pom = tmp_path / "pom.xml"
    pom.write_text(
        """<project>
  <properties>
    <maven.compiler.release>11</maven.compiler.release>
    <maven.compiler.testRelease>17</maven.compiler.testRelease>
  </properties>
</project>
""",
        encoding="utf-8",
    )

    assert JavaBuildMetadataResolver()._source_level_from_pom_file(pom) == "17"


def test_highest_source_level_is_numeric_not_lexicographic() -> None:
    resolver = JavaBuildMetadataResolver()

    assert resolver._highest_source_level(["8", "11", "17", "21", "9"]) == "21"


def test_fallback_discovers_local_outputs_and_jars(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    classes = root / "module" / "target" / "test-classes"
    local_jar = root / "module" / "libs" / "internal.jar"
    classes.mkdir(parents=True)
    local_jar.parent.mkdir(parents=True)
    local_jar.write_bytes(b"jar")

    resolver = JavaBuildMetadataResolver()

    assert classes.resolve() in set(resolver._all_compiled_outputs(root.resolve()))
    assert local_jar.resolve() in set(resolver._local_jars(root.resolve()))


# Regression for the enterprise Windows setup: Maven may live below "Program Files".
@pytest.mark.skipif(os.name != "nt", reason="Windows cmd.exe regression test")
def test_windows_build_metadata_batch_launcher_handles_program_files_path(tmp_path: Path) -> None:
    script = tmp_path / "Program Files" / "Apache Maven" / "bin" / "mvn.cmd"
    script.parent.mkdir(parents=True)
    script.write_text(
        "@echo off\r\necho ARE_BUILD_METADATA_BATCH_OK\r\nexit /b 0\r\n",
        encoding="utf-8",
    )

    resolver = JavaBuildMetadataResolver()
    command = [*resolver._executable_command(script), "--version"]
    completed = resolver._run(command, cwd=tmp_path)

    assert completed.returncode == 0, completed.stderr
    assert "ARE_BUILD_METADATA_BATCH_OK" in completed.stdout
