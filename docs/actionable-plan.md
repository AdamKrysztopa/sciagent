# SciAgent Actionable Plan

This plan is derived from `docs/core.md`, `docs/settings.md`, and `docs/zotero.md`.

## Phase 0: Baseline (Done)

1. Initialize Python project and toolchain with `uv`, `ruff`, `pyright`, and `pytest`.
2. Create starter package layout in `src/agt/` and quality gates in CI.
3. Configure local pre-commit hooks and GitHub Actions workflow.

## Phase 1: Platform Foundation (P0, AGT-0 to AGT-4)

### Sprint Goal

Deliver safe startup, typed settings, LLM provider boundary, and traceable execution.

### Action Items

1. AGT-0 + AGT-1: Harden `src/agt/config.py`.
- Add strict field constraints and explicit environment aliases.
- Add unit tests for missing required secrets and invalid library type.
- Enforce redaction for structured and exception logs.

2. AGT-2: Implement Zotero permission preflight in `src/agt/zotero/preflight.py`.
- Add startup check for read/write permission.
- Return machine-readable preflight status for UI/API health.

3. AGT-3: Add provider abstraction in `src/agt/providers/`.
- Define `LLMProvider` protocol (`invoke`, `ainvoke`, tool support).
- Implement xAI adapter and config-driven timeout/retry/model settings.

4. AGT-4: Add observability.
- Add request/thread IDs across graph execution.
- Instrument search, approval, and write nodes with spans.
- Add structured logging setup with per-step context.

### Exit Criteria

1. Startup fails fast on invalid config and missing secrets.
2. Preflight output is visible in health endpoint or CLI status.
3. LLM adapter can be swapped without graph-level changes.
4. Workflow traces show node-by-node execution.

## Phase 2: Retrieval + Ranking (P0, AGT-5 to AGT-7)

### Sprint Goal

Produce stable, ranked, deduplicated `NormalizedPaper` results.

### Action Items

1. AGT-5: Implement Semantic Scholar client wrapper in `src/agt/tools/search_papers.py`.
- Map responses to `NormalizedPaper` only.
- Handle timeout/retries/malformed payloads.

2. AGT-6: Implement rank/filter/dedup engine in new `src/agt/retrieval/ranking.py`.
- Add DOI + title-hash dedup.
- Implement explicit score formula from `docs/core.md`.

3. AGT-7: Implement summary + selection model.
- Keep summaries deterministic and bounded to 3-4 sentences.
- Preserve stable 0-based result indices for all views.

### Exit Criteria

1. Same query yields stable ordering with deterministic indices.
2. Duplicate papers collapse correctly.
3. Retrieval path fully covered with mocked tests.

## Phase 3: Approval-Gated Write Path (P0, AGT-9 to AGT-16)

### Sprint Goal

Guarantee idempotent Zotero writes behind explicit approval.

### Action Items

1. AGT-14: Replace placeholder `AgentState` with full checkpoint-safe workflow state.
2. AGT-15: Implement graph states for search -> present -> approve -> write.
3. AGT-9 + AGT-10: Add collection resolver and item mapping/validation modules.
4. AGT-11 + AGT-12: Add idempotent upsert and partial-success response handling.
5. AGT-16: Implement resume/retry from saved checkpoints.

### Exit Criteria

1. No write happens without explicit approve action.
2. Re-running same approval does not create duplicates.
3. Interrupted runs can resume from checkpoint safely.

## Phase 4: Product Delivery (AGT-17 to AGT-18)

### Sprint Goal

Deliver a usable Streamlit prototype while preserving backend separation.

### Action Items

1. Build approval-focused UI fragments in `src/agt/ui/app.py`.
2. Show per-item status: created, unchanged, failed.
3. Separate backend workflow API from UI rendering code.

### Exit Criteria

1. User can search, review, approve/reject, and inspect outcomes in one flow.
2. UI errors are actionable and tied to workflow step.

## Phase 5: Zotero Add-on Track (ZAP-0 to ZAP-11)

### Sprint Goal

Ship native Zotero plugin against backend contracts.

### Action Items

1. ZAP-0 to ZAP-2: bootstrap plugin template, hot reload, backend connection.
2. ZAP-3 to ZAP-5: sidebar UX with search + approval controls.
3. ZAP-6 to ZAP-8: native collection/item write path + optional PDF attach.
4. ZAP-9 to ZAP-11: preferences, error handling, packaging/release automation.

### Exit Criteria

1. Full native search -> approve -> write flow works from Zotero UI.
2. Plugin release can be produced from CI.

## Immediate Next 10 Tasks

1. Add `src/agt/providers/protocol.py` and xAI adapter.
2. Expand `Settings` tests for fail-fast validation and redaction.
3. Implement Semantic Scholar adapter with retries.
4. Add ranking/dedup module with formula tests.
5. Expand `AgentState` to checkpoint-safe schema from `docs/core.md`.
6. Implement explicit approval node and reject path.
7. Implement collection resolver with canonicalization tests.
8. Implement idempotent upsert (DOI then title+author hash) with integration tests.
9. Add trace IDs and structured logging middleware/helpers.
10. Add a workflow status endpoint or CLI status command exposing preflight + trace IDs.

## Tracking Rules

1. Every PR must cite story IDs (for example, AGT-11).
2. Every story implementation must include tests for its acceptance criteria.
3. All write-path stories must include idempotency and approval-gate checks.
