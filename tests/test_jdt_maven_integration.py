from __future__ import annotations

from pathlib import Path

import pytest

from automation_repository_explorer.parsers.jdt_project_analyzer import JdtProjectAnalyzer


@pytest.mark.integration
def test_jdt_resolves_maven_test_dependencies(tmp_path: Path) -> None:
    project = tmp_path / "sample"
    source = project / "src" / "test" / "java" / "demo" / "SampleSteps.java"
    source.parent.mkdir(parents=True)

    (project / "pom.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo</groupId>
  <artifactId>jdt-fixture</artifactId>
  <version>1.0-SNAPSHOT</version>
  <properties>
    <maven.compiler.release>17</maven.compiler.release>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.seleniumhq.selenium</groupId>
      <artifactId>selenium-api</artifactId>
      <version>4.35.0</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
""",
        encoding="utf-8",
    )

    source.write_text(
        """package demo;

import org.junit.Assert;
import org.openqa.selenium.WebElement;

public class SampleSteps {
    public void click(WebElement element) {
        Assert.assertNotNull(element);
        element.click();
    }
}
""",
        encoding="utf-8",
    )

    result = JdtProjectAnalyzer().analyze(project, (source,))

    messages = "\n".join(item.message for item in result.diagnostics)
    assert result.classes
    assert "WebElement cannot be resolved" not in messages
    assert "org.junit cannot be resolved" not in messages
    assert "org.openqa.selenium cannot be resolved" not in messages
    assert "Assert cannot be resolved" not in messages
    assert result.semantic_complete is True

    sample_class = result.classes[0]
    method = next(item for item in sample_class.methods if item.name == "click")
    assert method.binding_key
    assert method.resolved_call_keys
    assert not method.unresolved_call_expressions
