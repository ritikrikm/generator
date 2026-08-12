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


def test_source_level_normalization_handles_common_java_versions() -> None:
    resolver = JavaBuildMetadataResolver()

    assert resolver._normalize_source_level("1.8") == "8"
    assert resolver._normalize_source_level("17") == "17"
    assert resolver._normalize_source_level("VERSION_21") == "21"
    assert resolver._normalize_source_level("${java.version}") is None


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
