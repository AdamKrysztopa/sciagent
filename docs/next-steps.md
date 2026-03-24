# SciAgent — Next Steps & Remaining Work

**Generated:** 2026-03-22
**Baseline:** All quality gates clean — ruff 0 errors, pyright 0 errors, 132 tests passing.

---

## Completion Summary

| Milestone | Status | Stories |
|-----------|--------|---------|
| **M1** Foundation & Observability | **Done** | AGT-0, AGT-1, AGT-2, AGT-3, AGT-4 |
| **M2** Retrieval & Ranking | **Done** | AGT-5, AGT-6, AGT-7, AGT-27 |
| **M2.5** Retrieval Quality | **Done** | 12 sources, constraint parsing, metadata |
| **M2.6** Fallback Retrieval | **Done** | AGT-8 |
| **M3** Write Correctness | **Done** | AGT-9, AGT-10, AGT-11, AGT-12 |
| **M4** Approval Workflow & MVP | **Done** | AGT-14, AGT-15, AGT-17, AGT-19 |
| **M5** Production Hardening | **Done** | AGT-16, AGT-18, AGT-20*, AGT-21*, AGT-22* |
| **M6** Zotero Native Add-on | **Not started** | ZAP-0 through ZAP-11 |
| **M7** Pluggability & Infrastructure | **Not started** | AGT-23, AGT-24, AGT-25, AGT-26 |

\* = partial gaps noted below.

---

## Stories With Gaps (Marked Complete but Incomplete)

### AGT-20 — Edge-Case and Failure-Path Tests (Partial)

**What's done:** Broad failure-path coverage exists and retry-safe write outcomes are modeled.

**What's missing:**

- [ ] Workflow/API terminal status must not report `completed` when all Zotero writes fail
- [ ] Add tests for full write failure, partial write failure, and retry-after-failure semantics
- [ ] Replace broad exception swallowing in retrieval/write orchestration with typed failures and structured metadata where feasible

**Effort:** 1d

### AGT-21 — Security Hardening (Partial)

**What's done:** Secret redaction in logs, API key guard on backend endpoints, client ID owner isolation.

**What's missing:**

- [ ] Security checklist document for pre-production review
- [ ] Future multi-user delegated-auth path documented (OAuth2/OIDC direction)
- [ ] Require authentication outside explicit local-dev mode instead of silently allowing anonymous access
- [ ] Reject missing `X-AGT-Client-ID` outside local-dev mode, or derive ownership from authenticated claims

**Effort:** 1d (docs + small API hardening changes)

### AGT-22 — Universal LLM Interface (Partial)

**What's done:** `RoutedProvider` with failover, pluggable builder registry, xAI adapter.

**What's missing:**

- [ ] OpenAI adapter implementing `LLMProvider` protocol
- [ ] Anthropic adapter implementing `LLMProvider` protocol
- [ ] Groq adapter implementing `LLMProvider` protocol (optional)
- [ ] Startup/preflight validation so configured but unimplemented providers fail before first request
- [ ] Shared contract test suite validating all adapters

**Effort:** 2.5d (adapters + startup validation + shared contract test suite)

---

## Remaining Backend Stories (M7)

### AGT-23 — Unified Retrieval Registry

**Priority:** P1
**Dependencies:** AGT-5 ✅, AGT-6 ✅
**Effort:** 2d

Current state: `_RetrievalProvider` dataclass and `_build_retrieval_registry()` exist inside `search_papers.py` but are not a formal Protocol.

- [ ] Extract `RetrievalProvider` Protocol to `src/agt/tools/retrieval_protocol.py`
- [ ] Create `src/agt/tools/retrieval_registry.py` with provider registration and lookup
- [ ] Refactor each client (Semantic Scholar, OpenAlex, Crossref, PubMed, etc.) to implement the Protocol
- [ ] Simplify `search_papers.py` to iterate over registry entries
- [ ] Split `search_papers.py` orchestration into stage modules during the registry extraction (`query normalization`, `rewrite`, `federation`, `enrichment`, `ranking`, `metadata assembly`)
- [ ] Add contract tests: new provider requires zero orchestrator edits
- [ ] Add federated merge test across registered providers
- [ ] Define cache boundaries and invalidation rules for normalized retrieval results if backend caching is added later

### AGT-24 — Durable Distributed Checkpointing

**Priority:** P0
**Dependencies:** AGT-16 ✅, AGT-18 ✅
**Effort:** 1.5d

- [ ] Add Redis or Postgres LangGraph checkpointer backend
- [ ] Add `AGT_CHECKPOINT_BACKEND` and `AGT_CHECKPOINT_URL` settings fields
- [ ] Migrate workflow state from in-memory to persisted checkpoint store
- [ ] Add a temporary in-process concurrency guard if the in-memory store remains available for local-dev fallback
- [ ] Add migration/bootstrap script for checkpoint backend initialization
- [ ] Integration test: pause on instance A, resume on instance B
- [ ] Integration test: process restart preserves in-progress workflow state
- [ ] Smoke test: checkpoint backend unavailable produces actionable error
- [ ] Replay test: approval resume semantics stay idempotent across persisted checkpoints

### AGT-25 — Asynchronous Task Queue

**Priority:** P1
**Dependencies:** AGT-18 ✅, AGT-24 ❌ (blocked)
**Effort:** 2d

- [ ] Add Celery or Dramatiq worker for workflow execution
- [ ] Refactor `POST /run` to return `task_id` immediately
- [ ] Add task state transitions: queued → running → completed/failed
- [ ] Ensure worker uses same checkpointer and idempotency guardrails
- [ ] Add cancellation/retry policy with bounded retries
- [ ] Integration tests for async lifecycle

### AGT-26 — Cloud-Agnostic IaC

**Priority:** P2
**Dependencies:** AGT-24 ❌, AGT-25 ❌ (blocked)
**Effort:** 2d

- [ ] Create IaC modules (Terraform/Pulumi) for compute, persistence, queue
- [ ] Separate local-dev deployment from production deployment topology (dedicated backend/UI images or services)
- [ ] Add container hardening baseline: non-root runtime, healthchecks, explicit environment profiles
- [ ] Define managed secret injection contract
- [ ] Add CI/CD pipeline for plan/apply/deploy
- [ ] Add staging environment template
- [ ] Add rollback and drift-detection procedures

### AGT-13 — PDF Attachment Pipeline

**Priority:** P1
**Dependencies:** AGT-11 ✅, AGT-25 ❌ (partially blocked)
**Effort:** 2d

- [ ] Create `src/agt/tools/pdf_attach.py` with download + SHA256 checksum
- [ ] Add `AGT_ENABLE_PDF_ATTACHMENT` feature flag
- [ ] Integrate with upsert pipeline (attach after item creation)
- [ ] Store checksum in Zotero extra field
- [ ] Ensure attachment failures never corrupt item write flow
- [ ] Tests for download, checksum verification, and failure isolation

---

## Zotero Native Add-on (M6) — Full Scope

**Overall status:** Not started (zero TypeScript/React files exist).
**Backend readiness:** All required API endpoints are available (`/health`, `/run`, `/resume`, `/status/{run_id}`).

**Contract note:** Older planning text in `docs/zotero.md` still mentions `/search` and `/run-workflow`; the implemented backend contract for add-on planning is `/run`, `/resume`, and `/status/{run_id}`.

### Phase 1: Plugin Foundation (ZAP-0, ZAP-1, ZAP-2) — ~2d

| Story | Task | Status |
|-------|------|--------|
| ZAP-0 | Clone `zotero-addon-template`, configure TypeScript + esbuild | Not started |
| ZAP-0 | Generate `manifest.json` + `bootstrap.js` with plugin ID `agt@yourdomain.org` | Not started |
| ZAP-0 | Plugin loads in Zotero 7+ with "AGT" menu item and empty sidebar | Not started |
| ZAP-1 | Extension proxy file for loading from source | Not started |
| ZAP-1 | `npm run build` → `.xpi` auto-generated | Not started |
| ZAP-1 | `zotero-types` package installed for full autocomplete | Not started |
| ZAP-2 | Configurable backend URL (default `http://localhost:8000`) | Not started |
| ZAP-2 | `fetch` wrapper with auth (API key from `Zotero.Prefs`) | Not started |
| ZAP-2 | Health check on plugin load (green/red status in sidebar) | Not started |

### Phase 2: Native Sidebar UI (ZAP-3, ZAP-4, ZAP-5) — ~3.5d

| Story | Task | Status |
|-------|------|--------|
| ZAP-3 | Register custom pane via `Zotero.ItemPaneManager.registerSection` | Not started |
| ZAP-3 | Collapsible sidebar with AGT icon | Not started |
| ZAP-3 | Chat-like React + Tailwind interface | Not started |
| ZAP-4 | Input box + Search button → calls `/run` endpoint | Not started |
| ZAP-4 | Render paper card list with indices, summaries, checkboxes | Not started |
| ZAP-5 | "Create Collection" field with auto-suggest | Not started |
| ZAP-5 | Approve / Reject / Edit buttons → calls `/resume` | Not started |
| ZAP-5 | Progress spinner + per-item green checkmarks | Not started |

### Phase 3: Zotero Write Integration (ZAP-6, ZAP-7, ZAP-8) — ~3d

**Architecture decision required:** Native Zotero JS writes vs. backend-delegated writes.

| Story | Task | Status |
|-------|------|--------|
| ZAP-6 | Collection resolver via `Zotero.Collections` (native) | Not started |
| ZAP-7 | Idempotent item creation via `Zotero.Items` with DOI + hash dedup | Not started |
| ZAP-8 | PDF attachment via `Zotero.Attachments.importFromURL()` (feature-flagged) | Not started |

### Phase 4: Polish & Release (ZAP-9, ZAP-10, ZAP-11) — ~3d

| Story | Task | Status |
|-------|------|--------|
| ZAP-9 | Preferences pane (backend URL, API key, PDF toggle) | Not started |
| ZAP-10 | Graceful error fallback messages | Not started |
| ZAP-10 | Local cache of last search results | Not started |
| ZAP-11 | `npm run build` → signed `.xpi` | Not started |
| ZAP-11 | GitHub Actions workflow for auto-release | Not started |
| ZAP-11 | Listed on Zotero plugin directory + GitHub Releases | Not started |

---

## Immediate Backlog (Priority Order)

### P0 — Do First

1. **AGT-20 follow-up** — Truthful terminal status + typed failure handling/tests (1d)
2. **AGT-21 hardening** — Security checklist, auth defaults, delegated-auth direction (1d)
3. **AGT-24** — Distributed checkpointing with Redis/Postgres (1.5d)
4. **ZAP-0 + ZAP-1** — Plugin skeleton and dev environment (1d)

### P1 — Do Next

1. **AGT-22 adapters** — OpenAI and Anthropic provider adapters + startup validation (2.5d)
2. **ZAP-2** — Backend connection layer from plugin (0.5d)
3. **AGT-23** — Retrieval registry Protocol extraction (2d)
4. **AGT-20 CI gates** — Coverage, resilience, and replay checks in CI (1d)
5. **ZAP-3 + ZAP-4 + ZAP-5** — Full sidebar UI (3.5d)
6. **AGT-13** — PDF attachment pipeline (2d)
7. **AGT-25** — Async task queue (2d)

### P2 — Ship When Ready

1. **ZAP-6 + ZAP-7 + ZAP-8** — Native Zotero writes (3d)
2. **ZAP-9 + ZAP-10 + ZAP-11** — Preferences, error handling, release (3d)
3. **AGT-26** — Cloud IaC + production deployment split (2d)

---

## Unresolved Decisions

| Decision | Options | Impact |
|----------|---------|--------|
| **ZAP write path** | Native `Zotero.*` JS API vs. backend-delegated via `/resume` | Native = faster + offline-capable but duplicates dedup logic in TypeScript; Delegated = simpler plugin but requires backend for all writes |
| **Checkpoint backend** | Redis vs. Postgres | Redis = faster + simpler; Postgres = durable + query-friendly for analytics |
| **Task queue** | Celery vs. Dramatiq | Celery = mature ecosystem; Dramatiq = simpler API, fewer deps |
| **Provider priority** | OpenAI first vs. Anthropic first | Depends on team key availability and model preferences |

---

## Multi-Provider Rollout Checklist

- [ ] Phase A: Provider abstraction locked and covered by unit tests
- [ ] Phase B: xAI + OpenAI + Anthropic adapters passing shared contract test suite
- [ ] Phase C: Routing policy enabled (single, pinned, fallback chain)
- [ ] Phase D: Tracing and cost telemetry include provider/model labels
- [ ] Phase E: Failure semantics standardized across providers
- [ ] Phase F: Documentation updated with provider selection and env aliases

---

## Backend Gates for ZAP Blocks

| Gate | Required Stories | Met? |
|------|-----------------|------|
| Plugin foundation (ZAP-0 to ZAP-2) | AGT-0, AGT-1, AGT-2, AGT-4, AGT-18 | **Yes** |
| Sidebar UX (ZAP-3 to ZAP-5) | AGT-5, AGT-6, AGT-7, AGT-15, AGT-27 | **Yes** |
| Native writes (ZAP-6 to ZAP-8) | AGT-10, AGT-11, AGT-12, AGT-14, AGT-16 | **Yes** |
| PDF attachment (ZAP-8) | AGT-13 | **No** — AGT-13 not started |
| Release readiness (ZAP-9 to ZAP-11) | AGT-19, AGT-20, AGT-21 | **Partial** — AGT-20/21 follow-up work remains |

---

## CI & Quality Status

| Check | Result |
|-------|--------|
| `uv run ruff check .` | 0 errors |
| `uv run pyright` | 0 errors, 0 warnings |
| `uv run pytest --tb=short` | 132 passed |
| Test coverage areas | config, preflight, providers, guardrails, all retrieval clients, ranking, summarize, search orchestration, query constraints, query rewriter, zotero upsert, models, workflow, API |
