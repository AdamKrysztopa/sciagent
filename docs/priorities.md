# SciAgent Priorities

**Generated:** 2026-03-24
**Purpose:** Canonical priority map tying reviewer findings to existing story IDs in `docs/core.md` and the current backlog in `docs/next-steps.md`.

## Scope

This file converts the reviewer recommendations in [docs/reviewer/sciagent-review-fixes.md](docs/reviewer/sciagent-review-fixes.md) and [docs/reviewer/sciagent-review-improvements.md](docs/reviewer/sciagent-review-improvements.md) into an implementation order that preserves the dependency chain from [docs/core.md](docs/core.md).

Recommended interpretation for ambiguous items:

- Retrieval quality work that reduces search-engine API-key dependence belongs to AGT-28 and AGT-29 before broader AGT-23 refactoring.
- Deterministic query filters are product contracts, not UI-only affordances; backend, Streamlit, API, and Zotero surfaces must all expose the same filter model.
- Retrieval refactor work stays under AGT-23 unless it changes workflow semantics.
- CI and resilience gating stays under AGT-20 unless it is provider-specific, in which case it also touches AGT-22 or AGT-23.
- Deployment split and container hardening stay under AGT-26, with AGT-18 treated as already-completed API separation.
- Backend result caching is deferred and folded into AGT-23 as a retrieval-layer concern.

## Priority Order

| Lane | Story | Work Slice | Why Now | Canonical Backlog | Reviewer Source |
| ---- | ----- | ---------- | ------- | ----------------- | --------------- |
| P0 | AGT-28 | Search plan model, deterministic filter extraction, filter pushdown/post-filter enforcement | Prevents LLM semantic search from ignoring hard constraints such as `year >= 2024` | [docs/next-steps.md](docs/next-steps.md) | User discovery-quality request |
| P0 | AGT-29 | Keyless-first retrieval quality benchmark against standalone LLM/web-search baseline | Ensures SciAgent is not worse than asking a standalone LLM with web search | [docs/next-steps.md](docs/next-steps.md) | User discovery-quality request |
| P0 | ZAP-4A | Filter review/edit contract for app and Zotero add-on | Users need visible filters and toggles, not only a chat box | [docs/zotero.md](docs/zotero.md) | User discovery-quality request |
| P0 | AGT-20 | Truthful terminal write-failure status, typed failure handling, failure-path tests | Current workflow can report success-like completion for failed writes | [docs/next-steps.md](docs/next-steps.md#L28) | [docs/reviewer/sciagent-review-fixes.md](docs/reviewer/sciagent-review-fixes.md) |
| P0 | AGT-21 | Security checklist, non-anonymous auth defaults, delegated-auth direction | Current backend defaults are still local-safe rather than production-safe | [docs/next-steps.md](docs/next-steps.md#L40) | [docs/reviewer/sciagent-review-fixes.md](docs/reviewer/sciagent-review-fixes.md) |
| P0 | AGT-24 | Durable distributed checkpointing and replay-safe resume behavior | Process-local state blocks restart safety and multi-instance deployment | [docs/next-steps.md](docs/next-steps.md#L87) | [docs/reviewer/sciagent-review-fixes.md](docs/reviewer/sciagent-review-fixes.md) |
| P0 | ZAP-0, ZAP-1 | Add-on skeleton and hot-reload dev environment | Plugin work can start once backend contract is pinned | [docs/next-steps.md](docs/next-steps.md#L199) | [docs/zotero.md](docs/zotero.md#L13) |
| P1 | AGT-22 | OpenAI and Anthropic adapters, startup validation, provider contract tests | Provider abstraction exists; usefulness is capped by missing adapters | [docs/next-steps.md](docs/next-steps.md#L53) | [docs/reviewer/sciagent-review-improvements.md](docs/reviewer/sciagent-review-improvements.md) |
| P1 | AGT-23 | Retrieval protocol/registry extraction and `search_papers.py` stage split | Main retrieval orchestrator is the highest maintenance hotspot | [docs/next-steps.md](docs/next-steps.md#L72) | [docs/reviewer/sciagent-review-improvements.md](docs/reviewer/sciagent-review-improvements.md) |
| P1 | AGT-20 | Coverage, replay, contract, and resilience checks in CI | The next gain is stronger guarantees, not more surface area | [docs/next-steps.md](docs/next-steps.md#L28) | [docs/reviewer/sciagent-review-improvements.md](docs/reviewer/sciagent-review-improvements.md) |
| P1 | ZAP-2, ZAP-3, ZAP-4, ZAP-5 | Add-on backend connection layer and approval UI | Backend APIs are sufficient for sidebar UX work | [docs/next-steps.md](docs/next-steps.md#L151) | [docs/zotero.md](docs/zotero.md#L42) |
| P1 | AGT-13 | PDF attachment pipeline | Blocks ZAP-8 and keeps write-path feature scope incomplete | [docs/next-steps.md](docs/next-steps.md#L120) | [docs/core.md](docs/core.md#L168) |
| P1 | AGT-25 | Async task queue | Needed after durable checkpointing for long-running production workloads | [docs/next-steps.md](docs/next-steps.md#L101) | [docs/reviewer/sciagent-review-improvements.md](docs/reviewer/sciagent-review-improvements.md#L111) |
| P2 | ZAP-6, ZAP-7, ZAP-8 | Native Zotero writes | Requires a settled write-path decision and AGT-13 for PDF completeness | [docs/next-steps.md](docs/next-steps.md#L181) | [docs/next-steps.md](docs/next-steps.md#L175) |
| P2 | ZAP-9, ZAP-10, ZAP-11 | Preferences, fallback UX, release packaging | Release polish should follow backend hardening and plugin UX completion | [docs/next-steps.md](docs/next-steps.md#L188) | [docs/zotero.md](docs/zotero.md#L127) |
| P2 | AGT-26 | Production deployment split, container hardening, IaC | Reviewer deployment concerns fit best here, after queue and checkpoint work land | [docs/next-steps.md](docs/next-steps.md#L111) | [docs/reviewer/sciagent-review-improvements.md](docs/reviewer/sciagent-review-improvements.md) |

## Reviewer Mapping

| Reviewer Item | Recommended Story Mapping | Status in Backlog | Notes |
| ------------- | ------------------------- | ----------------- | ----- |
| Durable checkpoint store | AGT-24 | Explicit | Root production blocker |
| Truthful write-failure terminal state | AGT-20 | Explicit | Needed before broader use |
| Broad exception swallowing in retrieval/write flow | AGT-20 | Explicit | Tighten failure categories while preserving user-facing fallbacks |
| Auth defaults and owner isolation hardening | AGT-21 | Explicit | Current anonymous fallback should become local-dev-only |
| CI support claim vs Python 3.13 reality | AGT-20 | Explicit | Either add a 3.13 matrix or narrow README claim |
| Unsupported provider fails too late | AGT-22 | Explicit | Add startup/preflight validation |
| Temporary in-process concurrency guard | AGT-24 | Explicit | Interim only, not a substitute for persistence |
| Retrieval provider protocol and registry | AGT-23 | Explicit | Already called out in backlog |
| Split `search_papers.py` into stages | AGT-23 | Explicit | Added as part of registry extraction |
| Multi-provider completion | AGT-22 | Explicit | OpenAI/Anthropic first, Groq optional |
| Coverage, contract, resilience gates | AGT-20 plus AGT-22/23/24 | Explicit | CI additions should follow the canonical story boundary |
| Separate local-dev from production deployment | AGT-26 | Explicit | Treat as infra/deploy concern, not a reopened AGT-18 |
| Search/result caching | AGT-23 | Deferred | Alternative: split later into a dedicated performance story if scope grows |

## Implementation Steps

1. Land AGT-28 and AGT-29 before treating retrieval quality as done; this is a product trust gate, not an optional polish item.
2. Define ZAP-4A filter payload before building the Zotero sidebar so backend and add-on do not invent separate filter models.
3. Finish AGT-20 and AGT-21 follow-up before any production-facing release.
4. Land AGT-24 before AGT-25; do not start queue work on top of process-local state.
5. Run AGT-22 and AGT-23 in parallel only if the team can keep contract tests authoritative across both.
6. Start ZAP-0 and ZAP-1 once the backend contract remains `/health`, `/run`, `/resume`, `/status/{run_id}`; start ZAP-4A only after search-plan metadata is available.
7. Defer AGT-26 until checkpointing and async execution contracts are stable.

## Acceptance Criteria Check

- AGT-28 coverage: deterministic query parsing, filter enforcement, and search-plan metadata are now represented.
- AGT-29 coverage: keyless-first retrieval quality and standalone LLM/web-search comparison are now represented.
- ZAP-4A coverage: filter controls are now part of the Zotero/app delivery path.
- AGT-20 coverage: reviewer failure-path findings are now represented in backlog scope.
- AGT-21 coverage: both documentation and runtime-default hardening are represented.
- AGT-22 coverage: missing adapters and late-failure validation are both represented.
- AGT-23 coverage: protocol extraction and orchestrator decomposition are both represented.
- AGT-24 coverage: persistence, replay, and fallback concurrency guard are represented.
- AGT-26 coverage: reviewer deployment concerns are represented without reopening completed AGT-18 scope.

## Risks / Open Questions

- Search quality can look good if optional keyed sources are enabled, while the default product remains weak; AGT-29 must report keyless baseline and keyed enrichment separately.
- LLM query rewriting can improve recall but must never be the source of truth for hard filters; AGT-28 must preserve an auditable deterministic filter model.
- The backend caching recommendation is intentionally folded into AGT-23 for now; if it expands beyond retrieval-result caching, create a dedicated performance story instead of overloading AGT-23.
- Native Zotero writes remain an architecture decision, not just an implementation task; see [docs/next-steps.md](docs/next-steps.md#L178).
- The README/CI Python-version mismatch is still unresolved implementation work, not just a documentation nit.
