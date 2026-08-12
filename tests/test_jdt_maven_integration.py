from __future__ import annotations

from pathlib import Path

import pytest

from automation_repository_explorer.analyzers.optimized_graph_builder import OptimizedRepositoryGraphBuilder
from automation_repository_explorer.models.domain import RepositoryFile
from automation_repository_explorer.models.graph import RelationType
from automation_repository_explorer.parsers.jdt_project_analyzer import JdtProjectAnalyzer
from automation_repository_explorer.services.indexer import RepositoryIndex


@pytest.mark.integration
def test_jdt_resolves_maven_test_dependencies(tmp_path: Path) -> None:
    project = tmp_path / "sample"
    source = project / "src" / "test" / "java" / "demo" / "SampleSteps.java"
    source.parent.mkdir(parents=True)

    _write_pom(project)
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


@pytest.mark.integration
def test_jdt_resolves_project_calls_constructors_overloads_and_inheritance(tmp_path: Path) -> None:
    project = tmp_path / "sample"
    source_root = project / "src" / "test" / "java" / "demo"
    source_root.mkdir(parents=True)
    _write_pom(project)

    service = source_root / "Service.java"
    child = source_root / "ChildService.java"
    caller = source_root / "Caller.java"
    singleton = source_root / "GlobalSoftAssert.java"

    service.write_text(
        """package demo;
public class Service {
    public Service() {}
    public String save(String value) { return value; }
    public String save(int value) { return Integer.toString(value); }
    public String inherited() { return "ok"; }
}
""",
        encoding="utf-8",
    )
    child.write_text(
        """package demo;
public class ChildService extends Service {
    public ChildService() { super(); }
}
""",
        encoding="utf-8",
    )
    caller.write_text(
        """package demo;
public class Caller {
    public String run() {
        ChildService service = new ChildService();
        return service.save("value") + service.inherited();
    }
}
""",
        encoding="utf-8",
    )
    singleton.write_text(
        """package demo;
public class GlobalSoftAssert {
    private static GlobalSoftAssert INSTANCE;
    private GlobalSoftAssert() {}
    public static GlobalSoftAssert getInstance() {
        if (INSTANCE == null) INSTANCE = new GlobalSoftAssert();
        return INSTANCE;
    }
}
""",
        encoding="utf-8",
    )

    files = (service, child, caller, singleton)
    result = JdtProjectAnalyzer().analyze(project, files)
    assert result.semantic_complete is True, "\n".join(item.message for item in result.diagnostics)

    classes = {item.name: item for item in result.classes}
    run_method = next(item for item in classes["Caller"].methods if item.name == "run")
    constructor = next(
        item for item in classes["GlobalSoftAssert"].methods if item.is_constructor
    )
    getter = next(item for item in classes["GlobalSoftAssert"].methods if item.name == "getInstance")
    string_save = next(
        item
        for item in classes["Service"].methods
        if item.name == "save" and any("String" in parameter for parameter in item.parameters)
    )
    inherited = next(item for item in classes["Service"].methods if item.name == "inherited")
    child_constructor = next(item for item in classes["ChildService"].methods if item.is_constructor)

    assert constructor.binding_key in getter.resolved_call_keys
    assert child_constructor.binding_key in run_method.resolved_call_keys
    assert string_save.binding_key in run_method.resolved_call_keys
    assert inherited.binding_key in run_method.resolved_call_keys
    assert not run_method.unresolved_call_expressions

    index = RepositoryIndex(
        root=project,
        files=tuple(
            RepositoryFile(path=file, extension=".java", size_bytes=file.stat().st_size)
            for file in files
        ),
        java_classes=result.classes,
        java_analysis_complete=True,
    )
    graph = OptimizedRepositoryGraphBuilder().build(index)
    caller_id = OptimizedRepositoryGraphBuilder._method_id(classes["Caller"], run_method)
    getter_id = OptimizedRepositoryGraphBuilder._method_id(classes["GlobalSoftAssert"], getter)
    constructor_id = OptimizedRepositoryGraphBuilder._method_id(classes["GlobalSoftAssert"], constructor)

    caller_targets = {
        edge.target_id
        for edge in graph.child_edges(caller_id)
        if edge.relation == RelationType.CALLS
    }
    assert OptimizedRepositoryGraphBuilder._method_id(classes["Service"], string_save) in caller_targets
    assert OptimizedRepositoryGraphBuilder._method_id(classes["Service"], inherited) in caller_targets
    assert OptimizedRepositoryGraphBuilder._method_id(classes["ChildService"], child_constructor) in caller_targets
    assert any(
        edge.source_id == getter_id
        and edge.target_id == constructor_id
        and edge.relation == RelationType.CALLS
        for edge in graph.edges
    )


def _write_pom(project: Path) -> None:
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
