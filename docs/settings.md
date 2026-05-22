# AGT Quick-Start: Full Technical Stack & Bootstrap Guide (2026 Edition)

**Target:** Zero-to-MVP in <30 minutes for a solo dev or small team.
**Python requirement:** `>= 3.13` (recommended: **3.14** – released Oct 2025, fully stable in March 2026).
**Package manager:** `uv` (Astral) – 10–20× faster than pip/poetry.
**Quality tooling:** Python uses `ruff` + `pyright`; the Zotero add-on uses its real `npm` lint/build/typecheck/test scripts; docs and agent instructions use `markdownlint-cli2` plus a MkDocs Material site build.

This document is **copy-paste ready**. Follow the steps in order and you will have a clean, production-grade repo with the exact stack from the AGT epics.

## 1. Core Stack Summary

| Layer                 | Tool / Library                                                                                                                      | Version Pin (uv)    | Reason                                                                                       |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------- | -------------------------------------------------------------------------------------------- |
| **Runtime**           | Python                                                                                                                              | `>=3.13` (use 3.14) | Free-threaded GIL optional + better error messages                                           |
| **Project Mgmt**      | `uv`                                                                                                                                | latest (via curl)   | Replaces poetry/pip + venv in one binary                                                     |
| **Agent Framework**   | `langgraph`                                                                                                                         | `>=0.2.0`           | Stateful graphs + native checkpoints                                                         |
| **LLM**               | Native xAI REST adapter (`httpx`)                                                                                                   | latest              | Pydantic v2-only runtime path (no langchain bridge)                                          |
| **Academic Search**   | Keyless-first federation (`httpx` clients for OpenAlex, Crossref, Semantic Scholar, PubMed, Europe PMC, arXiv, BASE, OpenCitations) | latest              | Strong default discovery without search-engine API keys; keyed sources are opt-in enrichment |
| **Zotero**            | `pyzotero`                                                                                                                          | latest              | Full v3 Web API (create, upsert, attachments)                                                |
| **Settings**          | `pydantic-settings`                                                                                                                 | `>=2.6`             | Typed, validated, secret-redacted config                                                     |
| **UI**                | `streamlit`                                                                                                                         | `>=1.40`            | Instant chat + fragments for approval buttons                                                |
| **Async / HTTP**      | `httpx` + `anyio`                                                                                                                   | latest              | PDF downloads, rate-limit backoff                                                            |
| **Logging / Tracing** | `structlog` + `langsmith` (optional)                                                                                                | latest              | Structured logs + full LangGraph traces                                                      |
| **Lint / Format**     | `ruff`                                                                                                                              | latest              | One tool for formatting + linting (replaces black/flake8/isort)                              |
| **Type Checking**     | `pyright`                                                                                                                           | latest              | Fastest “ty” checker – works perfectly with ruff                                             |
| **Testing**           | `pytest` + `responses` + `vcrpy`                                                                                                    | latest              | E2E + mocked external calls                                                                  |
| **Add-on QA**         | `npm` scripts in `zotero-addon/`                                                                                                    | Node `>=20`         | Real package validation via `lint`, `build`, `typecheck`, and `test`                         |
| **Docs QA**           | `markdownlint-cli2`                                                                                                                 | `npx`               | Pragmatic Markdown linting for docs and agent instructions                                   |
| **Docs Build**        | `mkdocs-material`                                                                                                                   | latest              | Build a full navigable docs site directly from `docs/*.md`                                   |
| **Pre-commit**        | `pre-commit`                                                                                                                        | latest              | Fast commit-time hooks plus a pre-push gate that mirrors the full repo checks before CI      |
| **Extras**            | `tenacity`, `python-dotenv`, `redis` (later)                                                                                        | latest              | Rate guards, checkpoints                                                                     |

**Total dependencies for MVP:** ~18 packages (kept deliberately small).

## 2. One-Command Bootstrap (do this first)

```bash
# 1. Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create the project
uv init agt-zotero-agent --python 3.14
cd agt-zotero-agent

# 3. Add every package in one go (uv resolves everything instantly)
uv add \
    langgraph \
    semanticscholar \
    pyzotero \
    pydantic-settings \
    streamlit \
    httpx \
    structlog \
    langsmith \
    tenacity \
    pytest \
    responses \
    vcrpy \
    pre-commit

# 4. Add dev tools
uv add --dev ruff pyright pre-commit pytest mkdocs mkdocs-material

# 5. Create virtual env & lockfile (uv does this automatically)
uv sync
```

## 3. Project Structure (create these folders/files now)

```bash
agt-zotero-agent/
├── src/agt/
│   ├── __init__.py
│   ├── config.py          # Pydantic Settings + redaction
│   ├── models.py          # NormalizedPaper + AgentState
│   ├── tools/             # search_papers, zotero_upsert
│   ├── graph/             # LangGraph nodes & workflow
│   ├── zotero/            # wrapper + preflight
│   └── ui/                # Streamlit app
├── tests/
├── .python-version        # "3.14"
├── pyproject.toml         # (auto-generated + ruff config)
├── ruff.toml
├── pyrightconfig.json
├── .pre-commit-config.yaml
├── .env.example
├── Dockerfile
└── README.md
```

## 4. Essential Config Files (copy-paste)

**`ruff.toml`** (modern 2026 defaults)

```toml
target-version = "py314"
line-length = 100
select = ["E", "F", "I", "UP", "RUF", "PL", "SIM"]
fixable = ["ALL"]
ignore = ["E501"]  # let ruff handle line length

[format]
preview = true
```

**`pyrightconfig.json`**

```json
{
  "pythonVersion": "3.14",
  "typeCheckingMode": "strict",
  "reportMissingImports": true,
  "reportUnusedImport": true
}
```

**`.pre-commit-config.yaml`** (fast commit hooks plus full pre-push parity)

```yaml
default_install_hook_types:
  - pre-commit
  - pre-push

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.7
    hooks:
      - id: ruff
        stages: [pre-commit]
      - id: ruff-format
        stages: [pre-commit]
  - repo: local
    hooks:
      - id: pyright
        entry: uv run pyright
        language: system
        pass_filenames: false
        stages: [pre-commit]
      - id: markdownlint
        entry: npx --yes markdownlint-cli2 README.md docs/**/*.md examples/**/*.md .github/**/*.md zotero-addon/README.md
        language: system
        pass_filenames: false
        stages: [pre-commit]
      - id: python-quality-py313
        entry: sh -c 'uv run --isolated --python 3.13 ruff check . && uv run --isolated --python 3.13 ruff format --check . && uv run --isolated --python 3.13 pyright && uv run --isolated --python 3.13 pytest -q --vcr-record=none'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
      - id: python-quality-py314
        entry: sh -c 'uv run --isolated --python 3.14 ruff check . && uv run --isolated --python 3.14 ruff format --check . && uv run --isolated --python 3.14 pyright && uv run --isolated --python 3.14 pytest -q --vcr-record=none'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
      - id: zotero-addon-quality
        entry: sh -c 'cd zotero-addon && npm ci && npm run lint && npm run build && npm run typecheck && npm run test'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
      - id: docs-quality
        entry: sh -c 'npx --yes markdownlint-cli2 README.md docs/**/*.md examples/**/*.md .github/**/*.md zotero-addon/README.md && uv run mkdocs build --strict'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
```

Install hooks:

```bash
uv run pre-commit install
```

The config sets `default_install_hook_types` so plain `pre-commit install` wires both commit-time and push-time hooks.

## 5A. Repo Quality Gate

SciAgent now treats quality as a repo-wide contract, not a Python-only contract.

Run the backend gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none
```

Run the Zotero add-on gate against the real package in `zotero-addon/`:

```bash
cd zotero-addon
npm ci
npm run lint
npm run build
npm run typecheck
npm run test
```

Run the docs and agent-instructions gate:

```bash
npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" "examples/**/*.md" ".github/**/*.md" "zotero-addon/README.md"
uv run mkdocs build --strict
```

Commit-time hooks stay fast and catch the cheap failures early: `ruff`, `ruff format`, `pyright`, and Markdown linting. Push-time hooks run the full Python gate twice, once on Python 3.13 and once on Python 3.14, plus the Zotero add-on and docs gates locally before network push. The Python hooks use `uv run --isolated --python ...` so they mirror the CI version matrix without rewriting the project `.venv`; on a machine missing one of those interpreters, `uv` provisions it on first use.

## 5B. Modern Markdown Workspace

The workspace includes a Markdown-first authoring setup in `.vscode/`:

- autosave after a short delay so Markdown linting and preview refresh quickly
- recommended extensions for Prettier, Markdown Preview Enhanced, Mermaid rendering, Markdown All in One, and markdownlint
- tasks for `Docs: Lint`, `Docs: Build`, `Docs: Serve`, and `Docs: Full Check`
- MCP browser automation via the workspace Puppeteer server for validating the generated docs site

## 5. Quick Run Commands (after bootstrap)

```bash
# 1. Copy example env
cp .env.example .env

# 2. Run preflight + Streamlit prototype
uv run streamlit run src/agt/ui/app.py

# 3. Run full LangGraph CLI test (for debugging)
uv run python -m src.agt.graph.cli

# 4. Run tests (happy path + mocks)
uv run pytest -q --vcr-record=none
```

## 6. Dockerfile (for Production v1+)

```dockerfile
FROM python:3.14-slim

RUN pip install --no-cache-dir uv
COPY . .
RUN uv sync --frozen

CMD ["uv", "run", "streamlit", "run", "src/agt/ui/app.py", "--server.port=8501"]
```

## 7. Recommended VS Code / Cursor Settings (settings.json snippet)

```json
{
  "python.defaultInterpreterPath": ".venv",
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "charliermarsh.ruff",
  "[python]": {
    "editor.codeActionsOnSave": { "source.fixAll.ruff": "explicit" }
  },
  "python.analysis.typeCheckingMode": "strict"
}
```

## 8. Next Steps After Bootstrap (links to epics)

1. Run `uv sync` → open in editor → you already have a working repo.
2. Implement **AGT-0** (config.py) first – 15 minutes.
3. Then **AGT-14** (models.py + AgentState) – another 20 minutes.
4. Paste the LangGraph skeleton from earlier responses → you have a running agent.

You now have:

- The exact stack from all AGT epics
- Modern tooling (uv + ruff + pyright)
- Zero-config start
- Ready for Docker, CI, and scaling to Redis checkpointers

**Just run the bootstrap block above and you’re literally 30 seconds away from typing your first natural-language paper search.**

## Reproducibility Contract

- Runtime configuration must be loaded through `pydantic-settings` only.
- Startup must fail fast when required settings are missing or invalid.
- Secrets must never appear in logs; all structured and plain logs are redacted.
- CI and local execution should use the same explicit repo gates:
  - Python backend: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run pytest -q --vcr-record=none`
  - Zotero add-on: `cd zotero-addon && npm ci && npm run lint && npm run build && npm run typecheck && npm run test`
  - Docs and agent instructions: `npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" "examples/**/*.md" ".github/**/*.md" "zotero-addon/README.md"` and `uv run mkdocs build --strict`
- `pre-commit install` wires both `pre-commit` and `pre-push` hooks via `default_install_hook_types`.
- Commit-time hooks run `ruff`, `ruff format`, `pyright`, and Markdown linting.
- Push-time hooks run the full Python, Zotero add-on, and docs gates before code leaves the machine.

## Provider Swap Contract

- Internal model calls must use the `LLMProvider` protocol in `src/agt/providers/protocol.py`.
- Provider construction is centralized in `src/agt/providers/router.py`.
- Runtime provider behavior is fully controlled by settings:
  - `AGT_LLM_PROVIDER` or `LLM_PROVIDER`
  - `AGT_MODEL_NAME`
  - `AGT_TIMEOUT_SECONDS`
  - `AGT_RETRIES`
  - `AGT_TEMPERATURE`
  - `AGT_ENV` + `AGT_ENV_OVERRIDES` for environment-specific overrides
- If `AGT_LLM_PROVIDER` is unset, runtime auto-selects the first configured provider key in this order: OpenAI, Anthropic, xAI, Groq.
- The current built-in adapters are OpenAI, Anthropic, and xAI via `src/agt/providers/router.py`; Groq remains config-recognized but not yet implemented.
- Provider-specific missing-key errors must name the selected provider and every accepted env-var alias.

## M5 Provider Routing Policy (AGT-22)

- Primary provider selection remains config-driven via `AGT_LLM_PROVIDER`; if unset, runtime resolves a provider from configured keys.
- Optional fallback provider can be configured via `AGT_LLM_FALLBACK_PROVIDER`.
- Failover policy is explicit and independently toggled:
  - `AGT_LLM_FAILOVER_ON_TIMEOUT=true|false`
  - `AGT_LLM_FAILOVER_ON_RATE_LIMIT=true|false`
- Failover is applied only for timeout and rate-limit failures; non-retryable provider errors are surfaced directly.

## M5 Backend Security (AGT-21)

Per-user API key authentication with GCP Secret Manager storage.

| Variable | Default | Description |
|---|---|---|
| `AGT_GCP_PROJECT` | *(unset)* | GCP project ID. When set, enables Secret Manager auth mode. |
| `AGT_GCP_SECRET_NAME` | `agt-user-registry` | Secret Manager secret name for the user registry JSON. |
| `AGT_SECRET_CACHE_TTL_SECONDS` | `60` | Cache TTL for user registry reads (range: 5–3600). |
| `AGT_SHARED_LLM_BUDGET_PER_USER_USD` | `2.00` | Default per-user shared LLM budget in USD. |
| `AGT_BACKEND_API_KEY` | *(unset)* | Fallback single-key mode when `AGT_GCP_PROJECT` is not set. |

- When `AGT_GCP_PROJECT` is set, per-user keys are read from Secret Manager. Each user has a unique key (`agt_{slug}_{hex}`), budget, and admin flag.
- When `AGT_GCP_PROJECT` is not set, falls back to `AGT_BACKEND_API_KEY` (single-key mode, slug `"default"`, admin).
- `X-AGT-Client-ID` header is no longer used; run ownership uses the authenticated slug.
- Admin endpoints (`/admin/*`) require `is_admin=true` in the user registry.
- Shared LLM budget tracking is per-user and in-memory (resets on restart). Users providing their own `X-LLM-API-Key` bypass shared budget tracking.
