import os
from pathlib import Path

from automation_repository_explorer.parsers.jdt_project_analyzer import JdtProjectAnalyzer


def test_bridge_current_requires_jar_newer_than_every_bridge_input(tmp_path: Path) -> None:
    pom = tmp_path / "pom.xml"
    analyzer_source = tmp_path / "JdtAnalyzerMain.java"
    bootstrap_source = tmp_path / "JdtBootstrapMain.java"
    jar = tmp_path / "are-jdt-bridge.jar"

    for path in (pom, analyzer_source, bootstrap_source, jar):
        path.write_text(path.name, encoding="utf-8")

    # Use whole seconds with wide gaps: Windows/filesystem timestamp precision varies.
    base = 1_700_000_000
    os.utime(pom, (base, base))
    os.utime(analyzer_source, (base + 10, base + 10))
    os.utime(bootstrap_source, (base + 20, base + 20))
    os.utime(jar, (base + 30, base + 30))

    inputs = (pom, analyzer_source, bootstrap_source)
    assert JdtProjectAnalyzer._bridge_is_current(jar, inputs) is True

    os.utime(bootstrap_source, (base + 40, base + 40))
    assert JdtProjectAnalyzer._bridge_is_current(jar, inputs) is False
