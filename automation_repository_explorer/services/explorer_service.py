"""High-level application service for repository exploration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from automation_repository_explorer.analyzers.graph_builder import RepositoryGraphBuilder
from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.graph import GraphNode, NodeType
from automation_repository_explorer.search.search_engine import SearchEngine, SearchMode, SearchResult
from automation_repository_explorer.services.indexer import RepositoryIndex, RepositoryIndexer

ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True, slots=True)
class RepositorySummary:
    """Summary statistics for a scanned repository."""

    files: int
    features: int
    scenarios: int
    steps: int
    java_classes: int
    java_methods: int
    properties: int
    graph_nodes: int
    graph_edges: int
    parse_issues: int = 0


@dataclass(frozen=True, slots=True)
class ExplorationContext:
    """Complete state for a repository exploration session."""

    index: RepositoryIndex
    graph: RepositoryGraph
    summary: RepositorySummary


class ExplorerService:
    """Facade used by ARE user interfaces and tests."""

    def __init__(
        self,
        indexer: RepositoryIndexer | None = None,
        graph_builder: RepositoryGraphBuilder | None = None,
    ) -> None:
        self._indexer = indexer or RepositoryIndexer()
        self._graph_builder = graph_builder or RepositoryGraphBuilder()

    def explore(
        self,
        repository_path: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> ExplorationContext:
        """Build index, graph, and summary for a repository path."""

        if progress_callback:
            progress_callback(1, "Starting repository scan...")

        index = self._indexer.build_index(
            repository_path,
            progress_callback=progress_callback,
        )

        graph = self._graph_builder.build(
            index,
            progress_callback=progress_callback,
        )

        if progress_callback:
            progress_callback(97, "Calculating repository summary...")

        summary = self._summarize(index, graph)

        if progress_callback:
            if index.parse_issues:
                progress_callback(
                    100,
                    f"Repository scan complete with {len(index.parse_issues)} parse issue(s).",
                )
            else:
                progress_callback(100, "Repository scan complete.")

        return ExplorationContext(index=index, graph=graph, summary=summary)

    def search(
        self,
        graph: RepositoryGraph,
        query: str,
        mode: SearchMode = SearchMode.CASE_INSENSITIVE,
        node_types: set[NodeType] | None = None,
        limit: int = 50,
    ) -> tuple[SearchResult, ...]:
        """Search a repository graph."""

        return SearchEngine(graph).search(
            query=query,
            mode=mode,
            node_types=node_types,
            limit=limit,
        )

    @staticmethod
    def node_details(graph: RepositoryGraph, node_id: str) -> dict[str, object]:
        """Return selected node details, parents, children, and related nodes."""

        node = graph.get_node(node_id)
        if node is None:
            return {}
        return {
            "node": node,
            "parents": graph.parents(node_id),
            "children": graph.children(node_id),
            "related": graph.related(node_id),
            "parent_edges": graph.parent_edges(node_id),
            "child_edges": graph.child_edges(node_id),
        }

    @staticmethod
    def _summarize(index: RepositoryIndex, graph: RepositoryGraph) -> RepositorySummary:
        scenarios = sum(len(feature.scenarios) for feature in index.features)
        steps = sum(
            len(scenario.steps)
            for feature in index.features
            for scenario in feature.scenarios
        )
        methods = sum(len(java_class.methods) for java_class in index.java_classes)
        return RepositorySummary(
            files=len(index.files),
            features=len(index.features),
            scenarios=scenarios,
            steps=steps,
            java_classes=len(index.java_classes),
            java_methods=methods,
            properties=len(index.properties),
            graph_nodes=len(graph.nodes),
            graph_edges=len(graph.edges),
            parse_issues=len(index.parse_issues),
        )
