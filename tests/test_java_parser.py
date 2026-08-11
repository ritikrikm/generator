from pathlib import Path

from automation_repository_explorer.analyzers.health_analyzer import RepositoryHealthAnalyzer
from automation_repository_explorer.analyzers.optimized_graph_builder import OptimizedRepositoryGraphBuilder
from automation_repository_explorer.models.domain import JavaClass, JavaMethod, RepositoryFile, SourceLocation
from automation_repository_explorer.models.graph import RelationType
from automation_repository_explorer.parsers.jdt_project_analyzer import JdtProjectAnalyzer
from automation_repository_explorer.services.indexer import RepositoryIndex


def test_jdt_payload_maps_constructor_and_binding_edges() -> None:
    file_path = Path("GlobalSoftAssert.java").resolve()
    analyzer = JdtProjectAnalyzer()
    java_class = analyzer._map_class({
        "file": str(file_path), "name": "GlobalSoftAssert", "package": "", "imports": [],
        "line": 1, "bindingKey": "class", "methods": [
            {"name": "GlobalSoftAssert", "returnType": "", "parameters": [], "line": 5,
             "endLine": 5, "body": "", "constructor": True, "bindingKey": "ctor",
             "callExpressions": [], "resolvedCallKeys": [], "unresolvedCalls": [], "stringLiterals": []},
            {"name": "getInstance", "returnType": "GlobalSoftAssert", "parameters": [], "line": 8,
             "endLine": 11, "body": "", "constructor": False, "bindingKey": "getter",
             "callExpressions": ["new GlobalSoftAssert"], "resolvedCallKeys": ["ctor"],
             "unresolvedCalls": [], "stringLiterals": []},
        ]})
    constructor, getter = java_class.methods
    assert constructor.is_constructor is True
    assert getter.resolved_call_keys == ("ctor",)
    assert java_class.analysis_backend == "eclipse-jdt"


def test_jdt_binding_links_constructor_without_health_false_positive() -> None:
    file_path = Path("GlobalSoftAssert.java")
    constructor = JavaMethod(name="GlobalSoftAssert", return_type="", parameters=(),
        location=SourceLocation(file_path, 5), end_line=5, body="", calls=(), string_literals=(),
        is_constructor=True, binding_key="ctor")
    getter = JavaMethod(name="getInstance", return_type="GlobalSoftAssert", parameters=(),
        location=SourceLocation(file_path, 8), end_line=11, body="", calls=("GlobalSoftAssert",),
        string_literals=(), call_expressions=("new GlobalSoftAssert",), binding_key="getter",
        resolved_call_keys=("ctor",))
    java_class = JavaClass(name="GlobalSoftAssert", package="", imports=(),
        location=SourceLocation(file_path, 1), methods=(constructor, getter), binding_key="class",
        analysis_backend="eclipse-jdt")
    index = RepositoryIndex(root=Path("."), files=(RepositoryFile(file_path, ".java", 1),),
        java_classes=(java_class,))
    graph = OptimizedRepositoryGraphBuilder().build(index)
    constructor_id = OptimizedRepositoryGraphBuilder._method_id(java_class, constructor)
    getter_id = OptimizedRepositoryGraphBuilder._method_id(java_class, getter)
    assert any(edge.source_id == getter_id and edge.target_id == constructor_id
               and edge.relation == RelationType.CALLS for edge in graph.edges)
    report = RepositoryHealthAnalyzer().analyze(graph)
    assert all(finding.node_id != constructor_id for finding in report.findings)
