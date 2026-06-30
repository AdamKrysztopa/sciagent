# SciAgent

SciAgent turns a research question into a reviewed Zotero collection with a
deterministic search plan, explainable results, and approval-gated writes. It
federates searches across OpenAlex, Semantic Scholar, Crossref, PubMed, arXiv,
Europe PMC, BASE, and OpenCitations — then routes approved items into your
Zotero library without silent writes.

[![CI](https://github.com/AdamKrysztopa/sciagent/actions/workflows/ci.yml/badge.svg)](https://github.com/AdamKrysztopa/sciagent/actions/workflows/ci.yml)

## Try the Hosted Demo

Public backend: `https://sciagent-ewpafdgfya-ew.a.run.app`

### Setup

1. Install the SciAgent Zotero add-on — download
   `sciagent-zotero-addon.xpi` from the
   [latest release](https://github.com/AdamKrysztopa/sciagent/releases/latest).
2. Get a Zotero API key with read+write scope:
   <https://www.zotero.org/settings/keys/new>
3. Find your Zotero user ID: <https://www.zotero.org/settings/keys> → top of page.
4. Open **Tools → SciAgent → Preferences** and configure:
   - **Backend Mode:** Remote (hosted backend)
   - **Backend URL:** `https://sciagent-ewpafdgfya-ew.a.run.app`
   - **Zotero API Key:** (from step 2)
   - **Library ID:** (from step 3)
5. Save Preferences — the status pill should turn green.

### What the backend sees

- Your search queries.
- Your Zotero credentials (transient — used to write to your library,
  never stored server-side).
- The items it writes to your library (it does NOT read your existing
  library beyond duplicate detection).

### What the backend does NOT do

- Persist your Zotero credentials beyond a single request.
- Log your credentials (structlog redaction enforced).
- Share your data with anyone besides the LLM provider (DeepSeek by
  default; configurable per-request via the LLM Override toggle).

### LLM costs

By default, LLM calls use the operator's DeepSeek key. The demo has a
$10/month hard cap — when it runs out, the backend stops responding
until next month. Enable **Use my own LLM key** in Preferences to use
your own key instead.

### This is a demo, not a hosted product

- No SLA. The service may go offline at any time.
- No warranty. Use at your own risk.
- Source code: <https://github.com/AdamKrysztopa/sciagent>

---

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

See [Installation](docs/get-started/install.md) for OS security warnings and platform notes.

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

- **[Installation](docs/get-started/install.md)** — XPI download, OS security warnings, and
  platform notes
- **[User Manual](docs/get-started/user-manual.md)** — Zero-to-running guide; shareable with
  anyone new to SciAgent
- **[REST API Reference](docs/reference/api.md)** — Backend contract for the add-on and
  developer tooling
- **[Core Roadmap](docs/reference/core.md)** — Feature backlog and milestone details
- **[Configuration & Usage Manual](docs/power-user/manual.md)** — Full Zotero workflow,
  configuration reference, and developer interfaces
- **[Deployment Guide](docs/power-user/deployment.md)** — Local, Docker, and future SaaS
  architecture
- **[Settings](docs/reference/settings.md)** — Runtime stack, bootstrap flow, and quality
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
