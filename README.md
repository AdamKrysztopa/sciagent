# SciAgent

SciAgent turns a research question into a reviewed Zotero collection with a deterministic search plan, explainable results, and approval-gated writes.

## Why Researchers Use It

- Review the search plan before retrieval so year limits, exclusion terms, and source choices stay explicit.
- Audit every result with stable rankings, source provenance, and an approval checkpoint before anything touches your library.
- Build clean Zotero collections without duplicate sprawl, silent writes, or "trust me" agent behavior.

## Canonical Journey

1. Open the SciAgent add-on from Zotero's main window.
2. Enter a question, choose a target collection, and review deterministic filters before search.
3. Inspect the returned papers, summaries, and source states.
4. Approve the subset you want, then let SciAgent write those items into Zotero with audit-friendly status.

## Not Another Chatbot

SciAgent is not a floating AI sidebar, PDF chat tool, or generic browser plug-in. The primary product path is the Zotero add-on for researchers. The Streamlit app remains a prototype and support surface. The CLI and REST API remain developer and support interfaces.

## Documentation

- **[Configuration & Usage Manual](docs/manual.md)** — Primary Zotero workflow, installation, and local run guide
- **[Zotero Add-on Plan](docs/zotero.md)** — Main-window product direction, scope, and compatibility stance
- **[REST API Reference](docs/api.md)** — Backend contract for the add-on and developer/support tooling
- **[Deployment Guide](docs/deployment.md)** — Local, Docker, and future SaaS architecture
- **[Core Roadmap](docs/core.md)** — Feature backlog and milestone details
- **[Action Plan](docs/actionable-plan.md)** — Execution tracker and live status
- **[Settings](docs/settings.md)** — Runtime stack, bootstrap flow, and quality tooling

## Quick Start

```bash
uv sync
cp .env.example .env
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000

cd zotero-addon
npm ci
npm run build
```

Install `zotero-addon/build/sciagent-zotero-addon.xpi` from Zotero's add-ons manager on Zotero 9.x, then launch **Tools -> SciAgent**.

## Other Interfaces

- `uv run streamlit run src/agt/ui/app.py` — Streamlit prototype and support UI
- `uv run python -m agt.graph.cli` — developer/support terminal runner
- `uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000` — backend for the add-on and custom clients

## Prerequisites

- Python 3.14 recommended (3.13 and 3.14 supported)
- `uv` package manager
- Node.js 20+ for the Zotero add-on quality gate
- Zotero 9.x for the supported add-on path

## Docs Authoring

This workspace ships a Markdown-first docs workflow with MkDocs Material, markdownlint, recommended VS Code extensions, and local preview support.

```bash
uv run mkdocs serve -a 127.0.0.1:8001
uv run mkdocs build --strict
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

GitHub Actions runs repo-wide quality jobs for Python, the Zotero add-on, and docs. Local hooks now split the same coverage across fast `pre-commit` checks and a full `pre-push` gate, so docs and add-on failures surface before push.

## Structure

```text
src/agt/config.py      # Typed settings and secret redaction helpers
src/agt/models.py      # Core normalized data models and workflow state
src/agt/graph/         # Workflow graph and CLI entrypoint
src/agt/api/           # FastAPI backend (health/run/resume/status)
src/agt/providers/     # Provider routing and LLM adapters
src/agt/tools/         # Retrieval, ranking, and Zotero write adapters
src/agt/ui/app.py      # Streamlit prototype UI
zotero-addon/          # Primary Zotero add-on surface for researchers
```
