# Automation Repository Explorer (ARE)

Automation Repository Explorer is a production-oriented static analysis tool for Java
Selenium Cucumber automation repositories.

ARE is intended to run locally on the same laptop or workstation that contains the
automation repository. It does not upload, copy, deploy, or modify the target repository.

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
python run_local.py
```

If dependencies are not installed yet, use:

```bash
python run_local.py --install
```

To only check whether the local machine is ready:

```bash
python run_local.py --check
```

In the sidebar, paste the local folder path of the automation repository.

For the included sample repository, scan:

```text
sample_repo
```

You can also run Streamlit directly if needed:

```bash
streamlit run automation_repository_explorer/ui/app.py
```

## Local-Only Usage

- Run ARE on the same machine where the automation repository exists.
- Use the local repository folder path. ZIP upload and cloud scanning are not required.
- Streamlit Cloud cannot read `C:\...` or `/Users/...` paths from your laptop. Those paths
  only work when the app is running locally on that same laptop.
- ARE is read-only for the target repository.

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
- Local Streamlit UI
- Unit tests
