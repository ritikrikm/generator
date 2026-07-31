# Automation Repository Explorer (ARE)

Automation Repository Explorer is a production-oriented static analysis tool for Java
Selenium Cucumber automation repositories.

It maps:

```text
Feature File
-> Scenario
-> Step
-> Step Definition
-> Java Method
-> Page Object
-> Wrapper Method
-> Property Key
-> XPath
```

This is not an AI project. It uses no LLMs, OpenAI APIs, embeddings, vector databases,
semantic search, or machine learning.

## Requirements

- Python 3.12+

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Run Tests

```bash
pytest
```

## Run UI

```bash
streamlit run automation_repository_explorer/ui/app.py
```

In the sidebar, scan:

```text
sample_repo
```

## Project Structure

```text
automation_repository_explorer/
  core/
  models/
  parsers/
  analyzers/
  graph/
  search/
  services/
  ui/
tests/
sample_repo/
docs/
```

## Version 1 Capabilities

- Recursive repository scanner
- Feature parser
- Java parser
- Properties parser
- JSON/XML text indexing
- Bidirectional relationship graph
- Exact, partial, case-insensitive, and fuzzy search
- Reverse mapping
- Scenario Outline example value mapping
- Streamlit UI
- Unit tests
