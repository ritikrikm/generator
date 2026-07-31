"""Search page."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import streamlit as st

from automation_repository_explorer.models.graph import GraphNode, NodeType
from automation_repository_explorer.search.search_engine import SearchMode, SearchResult
from automation_repository_explorer.services.explorer_service import ExplorationContext
from automation_repository_explorer.ui.components import node_label, node_table_rows
from automation_repository_explorer.ui.flow_graph import relationship_neighborhood
from automation_repository_explorer.ui.interactive_graph import render_interactive_graph
from automation_repository_explorer.ui.state import get_context, get_service


class SearchArea(StrEnum):
    """High-level file areas available in repository search."""

    ALL = "All"
    FEATURE = "Feature files"
    JAVA = "Java files"
    PROPERTY = "Property files"
    JSON = "JSON files"
    XML = "XML files"
    OTHER = "Other files"


@dataclass(frozen=True, slots=True)
class GroupedSearchResult:
    """Search result with display grouping metadata."""

    result: SearchResult
    area: SearchArea


def render_search() -> None:
    """Render repository search page."""

    st.subheader("Search")
    context = get_context()
    if context is None:
        st.warning("Scan a repository first.")
        return

    query = st.text_input("Search")
    filters = _render_filters(context)

    if not query:
        st.info("Enter text to search features, Java code, properties, locators, and resource files.")
        return

    results = get_service().search(
        context.graph,
        query,
        mode=filters["mode"],
        node_types=filters["node_types"],
        limit=500,
    )
    filtered_results = _filter_results(
        results,
        area=filters["area"],
        selected_file=filters["selected_file"],
        include_examples=filters["include_examples"],
    )
    grouped_results = _group_results(filtered_results)

    st.write(f"{len(filtered_results)} result(s)")
    if not filtered_results:
        st.info("No matches found for the selected filters.")
        return

    if filters["area"] == SearchArea.ALL:
        _render_group_tabs(context, grouped_results)
    else:
        _render_result_group(context, filters["area"], grouped_results.get(filters["area"], tuple()))


def _render_filters(context: ExplorationContext) -> dict[str, object]:
    left, right = st.columns(2)
    with left:
        area = st.selectbox("Search area", list(SearchArea), format_func=lambda item: item.value)
        mode = st.selectbox("Search mode", list(SearchMode), format_func=lambda item: item.value, index=2)
    with right:
        node_types = st.multiselect(
            "Node types",
            list(NodeType),
            format_func=lambda item: item.value,
        )
        include_examples = st.toggle("Include Scenario Outline example values", value=False)

    selectable_files = _files_for_area(context, area)
    file_options: dict[str, Path | None] = {"All files in selected area": None}
    file_options.update({_relative_path(context, path): path for path in selectable_files})
    selected_file = file_options[
        st.selectbox(
            "Specific file",
            list(file_options),
            help="Optional. Use this when you want to search inside one feature, Java, or property file.",
        )
    ]

    return {
        "area": area,
        "mode": mode,
        "node_types": set(node_types) if node_types else None,
        "selected_file": selected_file,
        "include_examples": include_examples,
    }


def _filter_results(
    results: tuple[SearchResult, ...],
    area: SearchArea,
    selected_file: Path | None,
    include_examples: bool,
) -> tuple[SearchResult, ...]:
    filtered: list[SearchResult] = []
    for result in results:
        node = result.node
        if not include_examples and node.type == NodeType.EXAMPLE_VALUE:
            continue
        if selected_file is not None and node.file_path != selected_file:
            continue
        result_area = _area_for_node(node)
        if area != SearchArea.ALL and result_area != area:
            continue
        filtered.append(result)
    return tuple(filtered)


def _group_results(results: tuple[SearchResult, ...]) -> dict[SearchArea, tuple[GroupedSearchResult, ...]]:
    grouped: dict[SearchArea, list[GroupedSearchResult]] = defaultdict(list)
    for result in results:
        area = _area_for_node(result.node)
        grouped[area].append(GroupedSearchResult(result=result, area=area))
    return {area: tuple(items) for area, items in grouped.items()}


def _render_group_tabs(
    context: ExplorationContext,
    grouped_results: dict[SearchArea, tuple[GroupedSearchResult, ...]],
) -> None:
    ordered_areas = [
        SearchArea.FEATURE,
        SearchArea.JAVA,
        SearchArea.PROPERTY,
        SearchArea.JSON,
        SearchArea.XML,
        SearchArea.OTHER,
    ]
    present_areas = [area for area in ordered_areas if grouped_results.get(area)]
    tabs = st.tabs([f"{area.value} ({len(grouped_results[area])})" for area in present_areas])
    for tab, area in zip(tabs, present_areas, strict=True):
        with tab:
            _render_result_group(context, area, grouped_results[area])


def _render_result_group(
    context: ExplorationContext,
    area: SearchArea,
    results: tuple[GroupedSearchResult, ...],
) -> None:
    st.write(area.value)
    if not results:
        st.info("No matches in this area.")
        return

    table_rows = [_result_table_row(context, item.result) for item in results]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    for item in results:
        result = item.result
        with st.expander(f"{result.score:.0f} - {node_label(result.node)}"):
            if st.button("View Flow", key=f"view-flow-{abs(hash(result.node.id))}"):
                st.session_state["are_search_flow_node_id"] = result.node.id
            st.dataframe(node_table_rows((result.node,)), use_container_width=True, hide_index=True)
            st.write("Matched text")
            st.code(result.matched_text)
            metadata = _display_metadata(result.node)
            if metadata:
                st.write("Metadata")
                st.json(metadata)
            if st.session_state.get("are_search_flow_node_id") == result.node.id:
                st.write("Interactive Flow")
                graph_nodes, graph_edges = relationship_neighborhood(
                    context,
                    result.node.id,
                    max_depth=5,
                    include_examples=False,
                )
                render_interactive_graph(graph_nodes, graph_edges, height=620)


def _result_table_row(context: ExplorationContext, result: SearchResult) -> dict[str, object]:
    node = result.node
    return {
        "Score": round(result.score, 1),
        "Area": _area_for_node(node).value,
        "Node Type": node.type.value,
        "Name": node.name,
        "Matched Text": result.matched_text,
        "File": _relative_path(context, node.file_path) if node.file_path else "",
        "Line": node.line or "",
    }


def _files_for_area(context: ExplorationContext, area: SearchArea) -> tuple[Path, ...]:
    paths = [file.path for file in context.index.files]
    if area == SearchArea.ALL:
        return tuple(sorted(paths, key=str))
    return tuple(sorted((path for path in paths if _area_for_path(path) == area), key=str))


def _area_for_node(node: GraphNode) -> SearchArea:
    if node.type in {NodeType.FEATURE, NodeType.SCENARIO, NodeType.STEP, NodeType.EXAMPLE_VALUE}:
        return SearchArea.FEATURE
    if node.type in {
        NodeType.JAVA_CLASS,
        NodeType.JAVA_METHOD,
        NodeType.PAGE_OBJECT,
        NodeType.WRAPPER_METHOD,
        NodeType.STEP_DEFINITION,
    }:
        return SearchArea.JAVA
    if node.type in {NodeType.PROPERTY_KEY, NodeType.XPATH}:
        return SearchArea.PROPERTY
    if node.file_path is None:
        return SearchArea.OTHER
    return _area_for_path(node.file_path)


def _area_for_path(path: Path) -> SearchArea:
    extension = path.suffix.lower()
    if extension == ".feature":
        return SearchArea.FEATURE
    if extension == ".java":
        return SearchArea.JAVA
    if extension == ".properties":
        return SearchArea.PROPERTY
    if extension == ".json":
        return SearchArea.JSON
    if extension == ".xml":
        return SearchArea.XML
    return SearchArea.OTHER


def _relative_path(context: ExplorationContext, path: Path) -> str:
    try:
        return str(path.relative_to(context.index.root))
    except ValueError:
        return str(path)


def _display_metadata(node: GraphNode) -> dict[str, object]:
    return {
        key: value
        for key, value in node.metadata.items()
        if key not in {"body"}
    }
