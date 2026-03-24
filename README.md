# SciAgent

SciAgent is a typed Python foundation for natural-language paper search and safe, approval-gated Zotero writes.

## Prerequisites

- Python 3.14 recommended (3.13 and 3.14 supported)
- `uv` package manager

## Bootstrap

```bash
uv sync
cp .env.example .env
uv run pre-commit install
```

## Run

```bash
uv run streamlit run src/agt/ui/app.py
uv run python -m agt.graph.cli
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
```

## Quality

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none
```

## CI Checks

GitHub Actions runs the same quality gates on Python 3.13 and 3.14:

- `ruff check .`
- `ruff format --check .`
- `pyright`
- `pytest -q --vcr-record=none`

## Structure

```text
src/agt/config.py      # Typed settings and secret redaction helpers
src/agt/models.py      # Core normalized data models and workflow state
src/agt/graph/         # Workflow graph and CLI entrypoint
src/agt/api/           # FastAPI backend (health/run/resume/status)
src/agt/tools/         # External tool adapters (search + zotero)
src/agt/ui/app.py      # Streamlit prototype UI
```
