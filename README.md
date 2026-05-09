# SciAgent

SciAgent is a typed Python foundation for natural-language paper search and safe, approval-gated Zotero writes.

## Documentation

- **[Configuration & Usage Manual](docs/manual.md)** — Installation, configuration, and local run guide
- **[REST API Reference](docs/api.md)** — Backend API contract for programmatic access
- **[Deployment Guide](docs/deployment.md)** — Local, Docker, and future SaaS architecture
- **[Core Roadmap](docs/core.md)** — Feature backlog and milestone details
- **[Action Plan](docs/actionable-plan.md)** — Execution tracker and live status
- **[Settings](docs/settings.md)** — Runtime stack, bootstrap flow, and quality tooling

## Prerequisites

- Python 3.14 recommended (3.13 and 3.14 supported)
- `uv` package manager
- Node.js 20+ when working on the Zotero add-on or running the full repo quality gate

## Bootstrap

```bash
uv sync
cp .env.example .env
uv run pre-commit install
```

## Docs Authoring

This workspace ships a modern Markdown workflow for docs work:

- autosave after a short delay in this workspace
- Markdown format-on-save via the recommended formatter extension
- advanced preview and Mermaid support through recommended VS Code extensions
- MCP browser automation via the workspace Puppeteer server for docs QA
- a full docs-site build from `docs/*.md` via MkDocs Material

Useful commands:

```bash
uv run mkdocs serve -a 127.0.0.1:8001
uv run mkdocs build --strict
```

## Run

```bash
uv run streamlit run src/agt/ui/app.py
uv run python -m agt.graph.cli
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
```

## Quality

```bash
# Python backend
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none

# Zotero add-on
cd zotero-addon
npm ci
npm run lint
npm run build
npm run typecheck
npm run test
cd ..

# Docs and agent instructions
npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" "examples/**/*.md" ".github/**/*.md" "zotero-addon/README.md"
uv run mkdocs build --strict
```

## CI Checks

GitHub Actions runs three quality jobs:

- Python quality on 3.13 and 3.14: `ruff check .`, `ruff format --check .`, `pyright`, `pytest -q --vcr-record=none`
- Zotero add-on quality in `zotero-addon/`: `npm ci`, `npm run lint`, `npm run build`, `npm run typecheck`, `npm run test`
- Docs quality: `markdownlint-cli2` plus `uv run mkdocs build --strict`

Local `pre-commit` remains intentionally lightweight and Python-only.

## Structure

```text
src/agt/config.py      # Typed settings and secret redaction helpers
src/agt/models.py      # Core normalized data models and workflow state
src/agt/graph/         # Workflow graph and CLI entrypoint
src/agt/api/           # FastAPI backend (health/run/resume/status)
src/agt/tools/         # External tool adapters (search + zotero)
src/agt/ui/app.py      # Streamlit prototype UI
```
