# Automation Repository Explorer (ARE)

Automation Repository Explorer is a local static-analysis tool for Java + Selenium + Cucumber automation repositories.

It maps relationships such as:

```text
Feature File
-> Scenario
-> Step
-> Step Definition
-> Java Method
-> Page / UI Automation Method
-> Wrapper / Helper Method
-> Property Key
-> XPath
```

ARE is deterministic static analysis. It does not use LLMs, OpenAI APIs, embeddings, vector databases, or machine learning.

## Local-only execution

ARE is designed to run entirely on the same laptop that contains the repository.

- No Streamlit command is required.
- No local web server is started.
- No repository content is uploaded anywhere.
- Repository folders are read directly from the local file system.
- Relationship diagrams are generated as temporary local HTML files and opened with a `file://` URL in the default browser.

## Requirements

- Python 3.12+
- Tkinter / Tk support included with the Python installation

The normal ARE runtime has no required third-party Python packages.

`rapidfuzz` is optional. If it is not installed, fuzzy search automatically uses Python's built-in `difflib` fallback.

## Windows company laptop

From the repository root, double-click or run:

```bat
run_are_windows.bat
```

The launcher creates `.venv` if needed and starts:

```bash
python -m automation_repository_explorer.local_app
```

You can also run that command yourself from an activated virtual environment.

## Manual setup

Windows:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m automation_repository_explorer.local_app
```

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m automation_repository_explorer.local_app
```

## Using ARE

1. Click `Browse` and select the root of any Java + Selenium + Cucumber repository.
2. Click `Scan repository`.
3. Watch the real progress bar while ARE discovers files, parses them, builds relationships, and summarizes the graph.
4. Use `Summary` to see repository counts.
5. Use `Files` to verify what ARE discovered at any directory depth.
6. Use `Search & Relationships` to find features, steps, Java methods, property keys, locators, etc.
7. Select a search result and click `Open relationship graph` to open an offline local relationship diagram.
8. Check `Scan Issues` for supported files ARE could not fully parse.

## Generic repository goal

ARE does not require team-specific folder names such as:

```text
steps/
stepDefs/
pages/
pageObjects/
features/
resources/
```

The scanner recursively explores supported files at any folder depth.

For the current product scope, ARE targets repositories built around:

- Java
- Selenium
- Cucumber / Gherkin
- `.properties` locator/config files
- JSON/XML/YAML configuration resources

The repository itself should not need to be reorganized for ARE.

## Scan diagnostics

A parser problem in one supported file does not stop the complete repository scan.

ARE records the issue and continues exploring everything else. The local UI shows:

```text
File
Parser
Reason
```

This makes partial coverage visible instead of silently skipping files.

## Run tests

Developer dependencies are separate from the normal local runtime:

```bash
python -m pip install -r requirements-dev.txt
pytest
```

## Project structure

```text
automation_repository_explorer/
  analyzers/
  core/
  graph/
  models/
  parsers/
  search/
  services/
  ui/
  local_app.py
  local_graph.py

tests/
sample_repo/
docs/
```

## Current capabilities

- Recursive structure-independent repository scanning
- Real scan progress from 1% to 100%
- Parse diagnostics instead of silent failures
- Cucumber feature/scenario/step parsing
- Background and Rule-aware Gherkin parsing
- Java class/method parsing independent of folder names
- Package-private Java method discovery
- Fully-qualified Cucumber annotation recognition
- Java method-call indexing with receiver-aware call expressions
- Conservative method relationship resolution to avoid false same-name links
- Properties parsing
- JSON/XML/YAML text-resource indexing
- Bidirectional relationship graph
- Exact, partial, case-insensitive, and fuzzy search
- Reverse mapping
- Scenario Outline example value mapping
- Offline local relationship graph
- Local desktop UI
