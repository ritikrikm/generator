"""Search over repository graph nodes."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - exercised only without optional dependency
    fuzz = None  # type: ignore[assignment]

from automation_repository_explorer.graph.repository_graph import RepositoryGraph
from automation_repository_explorer.models.graph import GraphNode, NodeType


class SearchMode(StrEnum):
    """Supported search modes."""

    EXACT = "exact"
    PARTIAL = "partial"
    CASE_INSENSITIVE = "case_insensitive"
    FUZZY = "fuzzy"


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A ranked search hit."""

    node: GraphNode
    score: float
    matched_text: str


class SearchEngine:
    """Searches graph node names and metadata without AI."""

    def __init__(self, graph: RepositoryGraph) -> None:
        self._graph = graph

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.CASE_INSENSITIVE,
        node_types: set[NodeType] | None = None,
        limit: int = 50,
    ) -> tuple[SearchResult, ...]:
        """Search graph nodes by exact, partial, case-insensitive, or fuzzy matching."""

        clean_query = query.strip()
        if not clean_query:
            return tuple()

        results: list[SearchResult] = []
        for node in self._graph.nodes:
            if node_types is not None and node.type not in node_types:
                continue
            candidate_texts = self._candidate_texts(node)
            best_score = 0.0
            best_text = ""
            for text in candidate_texts:
                score = self._score(clean_query, text, mode)
                if score > best_score:
                    best_score = score
                    best_text = text
            if best_score > 0:
                results.append(SearchResult(node=node, score=best_score, matched_text=best_text))

        results.sort(key=lambda result: (-result.score, result.node.type.value, result.node.name))
        return tuple(results[:limit])

    def _candidate_texts(self, node: GraphNode) -> tuple[str, ...]:
        values = [node.name, node.type.value]
        if node.file_path is not None:
            values.append(str(node.file_path))
        for value in node.metadata.values():
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, (tuple, list, set)):
                values.extend(str(item) for item in value)
            elif isinstance(value, dict):
                values.extend(str(item) for pair in value.items() for item in pair)
        return tuple(value for value in values if value)

    @staticmethod
    def _score(query: str, candidate: str, mode: SearchMode) -> float:
        if mode == SearchMode.EXACT:
            return 100.0 if candidate == query else 0.0
        if mode == SearchMode.PARTIAL:
            return 100.0 if query in candidate else 0.0
        if mode == SearchMode.CASE_INSENSITIVE:
            return 100.0 if query.lower() in candidate.lower() else 0.0
        if mode == SearchMode.FUZZY:
            if fuzz is not None:
                return float(fuzz.partial_ratio(query.lower(), candidate.lower()))
            query_lower = query.lower()
            candidate_lower = candidate.lower()
            if query_lower in candidate_lower:
                return 100.0
            ratio = SequenceMatcher(None, query_lower, candidate_lower).ratio() * 100
            token_scores = [
                SequenceMatcher(None, query_lower, token).ratio() * 100
                for token in re_split_tokens(candidate_lower)
            ]
            return max([ratio, *token_scores], default=0.0)
        return 0.0


def re_split_tokens(value: str) -> tuple[str, ...]:
    """Split text into searchable tokens without requiring regex at call sites."""

    separators = [" ", ".", "_", "-", "/", ":", "@", "\"", "'", "(", ")", "[", "]"]
    tokens = [value]
    for separator in separators:
        next_tokens: list[str] = []
        for token in tokens:
            next_tokens.extend(token.split(separator))
        tokens = next_tokens
    return tuple(token for token in tokens if token)
