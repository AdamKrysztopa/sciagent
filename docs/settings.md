# AGT Quick-Start: Full Technical Stack & Bootstrap Guide (2026 Edition)

**Target:** Zero-to-MVP in <30 minutes for a solo dev or small team.
**Python requirement:** `>= 3.13` (recommended: **3.14** – released Oct 2025, fully stable in March 2026).
**Package manager:** `uv` (Astral) – 10–20× faster than pip/poetry.
**Lint / Format / Type-check:** `ruff` + `pyright` (the modern “ty” stack – blazing fast, zero config bloat).

This document is **copy-paste ready**. Follow the steps in order and you will have a clean, production-grade repo with the exact stack from the AGT epics.

## 1. Core Stack Summary

| Layer                  | Tool / Library                              | Version Pin (uv)          | Reason |
|------------------------|---------------------------------------------|---------------------------|--------|
| **Runtime**            | Python                                      | `>=3.13` (use 3.14)       | Free-threaded GIL optional + better error messages |
| **Project Mgmt**       | `uv`                                        | latest (via curl)         | Replaces poetry/pip + venv in one binary |
| **Agent Framework**    | `langgraph` + `langchain-core`              | `>=0.2.0`                 | Stateful graphs + native checkpoints |
| **LLM**                | `langchain-xai`                             | latest                    | Official xAI Grok tool-calling support |
| **Academic Search**    | `semanticscholar`                           | latest                    | Natural-language + rich metadata |
| **Zotero**             | `pyzotero`                                  | latest                    | Full v3 Web API (create, upsert, attachments) |
| **Settings**           | `pydantic-settings`                         | `>=2.6`                   | Typed, validated, secret-redacted config |
| **UI**                 | `streamlit`                                 | `>=1.40`                  | Instant chat + fragments for approval buttons |
| **Async / HTTP**       | `httpx` + `anyio`                           | latest                    | PDF downloads, rate-limit backoff |
| **Logging / Tracing**  | `structlog` + `langsmith` (optional)        | latest                    | Structured logs + full LangGraph traces |
| **Lint / Format**      | `ruff`                                      | latest                    | One tool for formatting + linting (replaces black/flake8/isort) |
| **Type Checking**      | `pyright`                                   | latest                    | Fastest “ty” checker – works perfectly with ruff |
| **Testing**            | `pytest` + `responses` + `vcrpy`            | latest                    | E2E + mocked external calls |
| **Pre-commit**         | `pre-commit`                                | latest                    | Hooks for ruff + pyright |
| **Extras**             | `tenacity`, `python-dotenv`, `redis` (later) | latest                 | Rate guards, checkpoints |

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
    langchain-xai \
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
uv add --dev ruff pyright pre-commit pytest

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

**`.pre-commit-config.yaml`**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/RobertCraigie/pyright-pre-commit
    rev: v1.1.390
    hooks:
      - id: pyright
```

Install hooks:
```bash
uv run pre-commit install
```

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
- CI and local execution should run through `uv` with identical commands:
  - `uv run ruff check`
  - `uv run pytest -q`

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
- Current default implementation is xAI via `src/agt/providers/xai.py`.
- OpenAI/Anthropic/Groq adapters should implement the same protocol and be added only in the router, with no workflow-level changes.
