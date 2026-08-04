# Automation Repository Explorer Architecture

Automation Repository Explorer is a local-only static-analysis application. It does not
use LLMs, OpenAI APIs, embeddings, vector databases, semantic search, or machine learning.
It scans repository folders on the same machine where the app is running and treats the
target repository as read-only input.

## Layers

### Models

Immutable dataclasses represent parsed source objects and graph objects:

- FeatureDocument
- Scenario
- Step
- ExamplesTable
- JavaClass
- JavaMethod
- PropertyEntry
- GraphNode
- GraphEdge

### Parsers

Every parser implements `RepositoryParser`.

Current parsers:

- `FeatureParser`
- `JavaParser`
- `PropertyParser`
- `TextResourceParser`

The Java parser uses deterministic static heuristics. The output model is designed so a
future tree-sitter adapter can be added without changing graph/search/UI layers.

### Services

`RepositoryIndexer` coordinates scanning and parsing.

`ExplorerService` is the application facade used by tests and Streamlit.

### Graph

`RepositoryGraph` stores directed edges and reverse adjacency. This makes reverse mapping
native:

Property Key -> Wrapper -> Page -> Step Definition -> Step -> Scenario -> Feature

### Search

`SearchEngine` searches graph nodes and metadata. Supported modes:

- exact
- partial
- case-insensitive
- fuzzy via RapidFuzz

## Extension Points

- Add new parser by implementing `RepositoryParser`.
- Add new node or relation type in `models/graph.py`.
- Add language-specific analyzers behind the graph builder.
- Replace Java parser internals with tree-sitter while preserving `JavaClass` and `JavaMethod`.
