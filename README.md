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

In the sidebar, choose one repository source:

- `Local path` scans a repository folder available on the same machine running ARE.
- `Upload ZIP` scans a zipped repository, which is the recommended option when ARE is deployed on Streamlit Cloud.

For local testing, scan:

```text
sample_repo
```

On a Windows company laptop, run:

```bat
run_are_windows.bat
```

Then open:

```text
http://localhost:8501
```

Use `Local path` and enter the repository folder path, for example:

```text
C:\Users\TAT6902\IdeaProjects\huntresspod_ng\huntress_MMSRB
```

Local paths only work when ARE is running on the same machine as the repository. A
hosted Streamlit Cloud app cannot read files from your laptop by path.

For Streamlit Community Cloud, use:

```text
streamlit_app.py
```

as the main app file.

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
