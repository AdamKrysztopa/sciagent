# SciAgent

SciAgent turns a research question into a reviewed Zotero collection with a
deterministic search plan, explainable results, and approval-gated writes. It
federates searches across OpenAlex, Semantic Scholar, Crossref, PubMed, arXiv,
Europe PMC, BASE, and OpenCitations — then routes approved items into your
Zotero library without silent writes.

[![CI](https://github.com/AdamKrysztopa/sciagent/actions/workflows/ci.yml/badge.svg)](https://github.com/AdamKrysztopa/sciagent/actions/workflows/ci.yml)

## Why Researchers Use It

- Review the search plan before retrieval so year limits, exclusion terms, and
  source choices stay explicit.
- Audit every result with stable rankings, source provenance, and an approval
  checkpoint before anything touches your library.
- Build clean Zotero collections without duplicate sprawl, silent writes, or
  "trust me" agent behavior.

## Quick Start

1. **Download** `sciagent-zotero-addon.xpi` from the
   [latest release](https://github.com/AdamKrysztopa/sciagent/releases/latest).
2. **Install in Zotero:** Tools → Add-ons → Install Add-on From File… → select
   the `.xpi` → restart Zotero.
3. **Paste your LLM API key** in the first-run card that appears when you open
   the SciAgent panel (Tools → SciAgent).

That is the entire install. No terminal. No Python. No `git clone`.

See [Installation](docs/install.md) for OS security warnings and platform notes.

<details>
<summary>Developer install (uv + npm)</summary>

```bash
uv sync
cp .env.example .env
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000

cd zotero-addon
npm ci
npm run build
```

Install `zotero-addon/build/sciagent-zotero-addon.xpi` from Zotero's add-ons
manager on Zotero 9.x, then launch **Tools → SciAgent**.

Other developer interfaces:

- `uv run streamlit run src/agt/ui/app.py` — Streamlit prototype and support UI
- `uv run python -m agt.graph.cli` — developer/support terminal runner
- `uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000` — backend for
  the add-on and custom clients

Prerequisites:

- Python 3.14 recommended (3.13 and 3.14 supported)
- `uv` package manager
- Node.js 20+ for the Zotero add-on quality gate
- Zotero 9.x for the supported add-on path

</details>

## Documentation

- **[Installation](docs/install.md)** — XPI download, OS security warnings, and
  platform notes
- **[User Manual](docs/user-manual.md)** — Zero-to-running guide; shareable with
  anyone new to SciAgent
- **[REST API Reference](docs/api.md)** — Backend contract for the add-on and
  developer tooling
- **[Core Roadmap](docs/core.md)** — Feature backlog and milestone details
- **[Configuration & Usage Manual](docs/manual.md)** — Full Zotero workflow,
  configuration reference, and developer interfaces
- **[Deployment Guide](docs/deployment.md)** — Local, Docker, and future SaaS
  architecture
- **[Settings](docs/settings.md)** — Runtime stack, bootstrap flow, and quality
  tooling

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

GitHub Actions runs repo-wide quality jobs for Python, the Zotero add-on, and
docs. Local hooks split the same coverage across fast `pre-commit` checks and a
full `pre-push` gate, so docs and add-on failures surface before push.

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
