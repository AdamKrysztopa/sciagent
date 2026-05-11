# SciAgent — Claude Code

## Source of Truth

- `docs/core.md` — backlog, stories, execution order, and acceptance criteria (highest authority)
- `docs/settings.md` — runtime stack, Python version policy, quality tooling, and dev setup
- `docs/zotero.md` — Zotero add-on roadmap, native integration plan, and milestone targets

## Project Overview

SciAgent federates academic paper search across OpenAlex, Semantic Scholar, Crossref, PubMed,
arXiv, Europe PMC, BASE, and OpenCitations. A LangGraph workflow orchestrates retrieval, ranking,
and reranking; FastAPI exposes the run/resume/status API. A Zotero TypeScript + React WebExtension
sidebar presents results and routes approved items to the Zotero library via an idempotent upsert.

**Stack:** Python ≥3.13 (3.14 preferred) · uv · FastAPI · LangGraph · pydantic-settings ·
httpx · structlog · pyright/ruff · pytest/vcrpy · TypeScript · React · WebExtension

**Source layout:**

```
src/agt/          Python backend (config, models, graph, tools, providers, zotero, api, ui)
tests/            pytest suite (use _env_file=None in all fixture settings)
zotero-addon/     TypeScript + React WebExtension sidebar
docs/             Markdown source for MkDocs Material site
.github/agents/   Specialist agent definitions (Copilot; also used as subagent context)
```

## Quality Gates

Never mark a change done without running the applicable gates first.

**Python** (always):

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none
```

**Zotero add-on** (when `zotero-addon/` or its tooling changes):

```bash
cd zotero-addon && npm ci && npm run lint && npm run build && npm run typecheck && npm run test
```

**Docs** (when any `.md` file or agent/instruction file changes):

```bash
npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" "examples/**/*.md" ".github/**/*.md" "zotero-addon/README.md"
uv run mkdocs build --strict
```

## MCP Tools

| Server | When to use |
|---|---|
| `context7` | **Before coding against any library.** Fetch current docs for FastAPI, LangGraph, Pydantic v2, httpx, tenacity, React, Zotero extension APIs. Do not rely on training-data memory for these. |
| `sequential-thinking` | When a task spans 3+ files, epics, or agent handoffs. Reason through the decomposition before starting. |
| `fetch` | When implementing or updating a provider adapter — retrieve current OpenAlex, Semantic Scholar, CrossRef, PubMed, or Zotero Web API schemas. |
| `git` | Structured git history, blame, or log when code context requires it. |
| `puppeteer` | Validating Streamlit UI or Zotero add-on rendering in a browser. |
| `github` | Checking CI status, PR state, or issue context. Requires `GITHUB_TOKEN` env var. |

## Specialist Context

Use these role descriptions when spawning subagents (Agent tool) for delegated work.
For single-domain tasks, execute directly without delegating.

| Role | File | Domain |
|---|---|---|
| `sciagent-orchestrator` | `.github/agents/sciagent-orchestrator.agent.md` | Lead coordinator. Multi-domain decomposition and stage-gate verification. Never writes code. |
| `core-planner` | `.github/agents/core-planner.agent.md` | Backlog mapping, story sequencing, acceptance checks against `docs/core.md`. |
| `python-backend-engineer` | `.github/agents/python-backend-engineer.agent.md` | All Python: `src/agt/**`, `tests/**`, FastAPI, LangGraph, providers, retrieval, ranking, Zotero write paths. |
| `settings-bootstrap` | `.github/agents/settings-bootstrap.agent.md` | Environment, uv, ruff, pyright/ty, CI, Docker, repo-wide quality gates (`docs/settings.md`). |
| `zotero-addon` | `.github/agents/zotero-addon.agent.md` | Zotero 9 add-on architecture, backend contracts, approval/write-path scoping. |
| `zotero-frontend` | `.github/agents/zotero-frontend.agent.md` | TypeScript, React, WebExtension, sidebar UI, hooks, typed clients, host adapters. |

**Routing heuristic:**

- `src/agt/**` or `tests/**` → `python-backend-engineer`
- Story scope, acceptance criteria, dependency mapping → `core-planner`
- Tooling, CI, environment, Python version → `settings-bootstrap`
- Zotero plugin architecture, write-path contracts → `zotero-addon`
- TypeScript, React, sidebar, hooks, manifest → `zotero-frontend`
- Multi-domain or risk screen needed → `sciagent-orchestrator` first

## Execution Policy

1. Execute work directly using local file and terminal tools. Do not delegate single-domain tasks to subagents.
2. For multi-domain work, use the Agent tool with a prompt that includes exact file paths, acceptance criteria, and the invariants that apply.
3. Use `sequential-thinking` MCP before starting any task that touches 3+ files or stages.
4. Use `context7` MCP before writing against any library where the current API matters.
5. Build and validate real implementations. Do not ship stub-only or mock-only code unless the user explicitly requests a demo/mock.
6. Keep outputs implementation-ready: start with a short plan, provide file-level changes, include validation steps, call out risks.

## Critical Invariants

These are enforced across all changes. Never violate them.

- **Idempotency:** Zotero write path (upsert logic) must be safe to replay without side effects.
- **Approval gate:** Every Zotero write goes through the approval gate — no silent writes.
- **Preflight:** `src/agt/zotero/preflight.py` must pass before any write operation is attempted.
- **Provider protocol:** All provider adapters must satisfy `ProviderProtocol` — no duck-typed shortcuts.
- **Typed graph state:** LangGraph workflow state transitions must be typed — no untyped `dict` state blobs.
- **Zero pyright errors:** `pyright` / `ty` must pass at zero errors for every changed file.
- **No raw Any:** `httpx.Response.json()` parsed as `object`, narrowed via `isinstance` / `cast` — never raw `Any`.
- **Strict settings:** `pydantic-settings` with `extra='forbid'`. Add typed optional fields for new env vars; never relax validation.
- **Test isolation:** All tests instantiate settings with `_env_file=None` for deterministic isolation.
- **No new deps without approval:** No new runtime dependencies added to the core package without explicit user approval.

## Frontend Rules (TypeScript / React / WebExtension)

1. Function components and hooks only — no class components.
2. Hooks at the top level only — no conditional hooks, no hooks in loops or after early returns.
3. Use `useEffectEvent` when an Effect needs the latest prop/state without re-subscribing on every render.
4. Keep `useEffect` for synchronization with external systems, not for derived state computed during render.
5. Isolate `Zotero.*` host APIs in adapter modules — not in leaf UI components.
6. Keep network calls in typed client modules with explicit loading/partial-success/failure states.
7. Design for sidebar constraints: predictable density, keyboard access, no hidden failure state.
8. Validate: `npm run lint && npm run build && npm run typecheck && npm run test` from `zotero-addon/`.

## Settings Contract

- All settings live in `src/agt/config.py` via `pydantic-settings`. No loose `os.environ` reads in app code.
- See `.env.example` for all supported environment variables.
- Use `_env_file=None` in all test fixtures to prevent environment bleed.
- `AGT_LLM_PROVIDER` auto-detects from available API keys if unset (OpenAI → Anthropic → xAI → Groq).
