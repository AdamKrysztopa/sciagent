# SciAgent Prioritized Action Plan

This document is synthesized from [docs/core.md](docs/core.md), [docs/settings.md](docs/settings.md), and [docs/zotero.md](docs/zotero.md) using role-specific subagent prioritization.

## Planning Rules

1. Prioritize write safety and approval-gate integrity over feature breadth.
2. Treat AGT-11 as a release gate for any workflow that writes to Zotero.
3. Keep reproducibility and deterministic CI behavior as mandatory constraints.
4. Use checklist execution and story IDs in every PR.
5. Treat multi-provider LLM support as a core requirement because provider keys are already present in local environment.

## Already Completed (Audit)

- [x] Repository bootstrap completed with uv, pyproject, lockfile, and package layout
- [x] Local quality gates wired: pre-commit with ruff and pyright
- [x] CI workflow created for lint, type-check, and tests
- [x] Core strategy docs moved to `docs/` and internal references updated
- [x] Prioritized milestone plan created from AGT and ZAP backlogs
- [x] Dependency plot added to this document
- [x] Multi-provider environment readiness detected (OPENAI_API_KEY, ANTHROPIC_API_KEY, XAI_API_KEY)

## Dependency Plot

```mermaid
flowchart LR
	AGT0[AGT-0] --> AGT1[AGT-1]
	AGT0 --> AGT3[AGT-3]
	AGT1 --> AGT2[AGT-2]
	AGT1 --> AGT4[AGT-4]
	AGT3 --> AGT4

	AGT1 --> AGT5[AGT-5]
	AGT5 --> AGT6[AGT-6]
	AGT5 --> AGT7[AGT-7]
	AGT6 --> AGT7
	AGT3 --> AGT7

	AGT2 --> AGT9[AGT-9]
	AGT2 --> AGT10[AGT-10]
	AGT5 --> AGT10
	AGT1 --> AGT14[AGT-14]
	AGT3 --> AGT14
	AGT5 --> AGT14
	AGT9 --> AGT11[AGT-11]
	AGT10 --> AGT11
	AGT14 --> AGT11
	AGT9 --> AGT12[AGT-12]
	AGT10 --> AGT12

	AGT7 --> AGT15[AGT-15]
	AGT9 --> AGT15
	AGT10 --> AGT15
	AGT14 --> AGT15
	AGT15 --> AGT16[AGT-16]
	AGT15 --> AGT17[AGT-17]
	AGT17 --> AGT19[AGT-19]
	AGT15 --> AGT19
	AGT19 --> AGT20[AGT-20]
	AGT12 --> AGT20
	AGT16 --> AGT20

	AGT15 --> AGT18[AGT-18]
	AGT16 --> AGT18
	AGT17 --> AGT18
	AGT1 --> AGT21[AGT-21]
	AGT2 --> AGT21
	AGT18 --> AGT21

	AGT3 --> AGT27[AGT-27]
	AGT5 --> AGT27
	AGT3 --> AGT22[AGT-22]
	AGT20 --> AGT22

	AGT11 --> ZAP0[ZAP-0..2]
	AGT15 --> ZAP3[ZAP-3..5]
	AGT16 --> ZAP6[ZAP-6..8]
	AGT19 --> ZAP9[ZAP-9..11]
	AGT21 --> ZAP9
```

## Critical Path

1. AGT-0 -> AGT-1 -> AGT-5 -> AGT-6 -> AGT-7 -> AGT-14 -> AGT-15 -> AGT-17 -> AGT-19 -> AGT-20 -> AGT-18 -> AGT-21
2. Parallel release-gate branch: AGT-2 -> AGT-9 + AGT-10 -> AGT-11
3. Risk gate: AGT-11 must be complete before shipping any approve-to-write flow.

## Milestone Plan

### M1 (Week 1-2): Foundation and Observability

- [x] Baseline repo bootstrap with uv, ruff, pyright, pytest, pre-commit, CI
- [x] AGT-0: Strict settings model and typed env aliases in [src/agt/config.py](src/agt/config.py)
- [x] AGT-1: Fail-fast startup for required secrets and env profile overrides
- [x] AGT-2: Real Zotero read/write preflight exposed in status output
- [x] AGT-3: LLMProvider protocol with provider-agnostic interface and xAI baseline adapter
- [x] Multi-provider config base: normalize provider key ingestion from AGT_* and plain key aliases
- [x] AGT-4: Request/thread IDs and span-level tracing for search/approve/write
- [x] Docs: add reproducibility contract in [docs/settings.md](docs/settings.md)

### M2 (Week 2-3): Retrieval and Ranking Core

- [x] AGT-5: Semantic Scholar wrapper returns only NormalizedPaper models
- [x] AGT-6: Ranking + dedup engine with formula and stable index guarantees
- [x] AGT-7: Deterministic bounded summarization for presentation layer
- [x] AGT-27: Rate-limit and cost guardrails integrated into retrieval/provider paths

#### M2 Add-ons (Completed)

- [x] M2 example switched to live-search only mode in [examples/m2_retrieval_demo.py](../examples/m2_retrieval_demo.py) (fixture/mock fallback removed).
- [x] Live-search runtime handles API-limit and malformed-response failures with user-readable output (no traceback) in [examples/m2_retrieval_demo.py](../examples/m2_retrieval_demo.py).
- [x] Retrieval expanded beyond Semantic Scholar using additional live sources:
	OpenAlex client in [src/agt/tools/openalex.py](../src/agt/tools/openalex.py),
	Crossref client in [src/agt/tools/crossref.py](../src/agt/tools/crossref.py),
	and merged search orchestration in [src/agt/tools/search_papers.py](../src/agt/tools/search_papers.py).
- [x] Query tightening added with validated constraint parsing/filtering and keyword-focused retrieval query handling in [src/agt/tools/query_constraints.py](../src/agt/tools/query_constraints.py) and [src/agt/tools/search_papers.py](../src/agt/tools/search_papers.py).
- [x] Citation and arXiv metadata now propagate in normalized retrieval models and ranking dedup fallbacks in [src/agt/models.py](../src/agt/models.py), [src/agt/tools/semantic_scholar.py](../src/agt/tools/semantic_scholar.py), and [src/agt/tools/ranking.py](../src/agt/tools/ranking.py).
- [x] Project runtime moved off LangChain bridge to a native xAI HTTP adapter (Pydantic v2-only runtime path) in [src/agt/providers/xai.py](../src/agt/providers/xai.py) and dependency updates in [pyproject.toml](../pyproject.toml).
- [x] CI quality gates validated after these changes (`ruff`, `pyright`, `pytest`) with updated retrieval/ranking coverage in [tests/test_search_papers.py](../tests/test_search_papers.py), [tests/test_query_constraints.py](../tests/test_query_constraints.py), [tests/test_semantic_scholar.py](../tests/test_semantic_scholar.py), and [tests/test_ranking.py](../tests/test_ranking.py).

#### M2 Retrieval Quality Fixes (Completed)

Root cause: keyword extraction polluted API queries with constraint words (e.g. "cited newer timeseries" instead of "timeseries"), and post-filtering was over-aggressive.

- [x] **Constraint stripping** — new `strip_constraints()` function removes year patterns, limit phrases, and quality phrases before keyword extraction, ensuring only content words reach the API ([src/agt/tools/query_constraints.py](../src/agt/tools/query_constraints.py)).
- [x] **Expanded stopwords** — ~60+ stopwords covering constraint/intensity words (cited, newer, older, advanced, trending, etc.) prevent leakage into retrieval queries.
- [x] **Year "YYYY and newer" pattern** — added regex recognition for "2020 and newer/later" as a year constraint.
- [x] **Lowered citation thresholds** — made realistic for recent papers: "most cited" 50→10, "game changers" 100→20, "trending" 20→5, community perception 50→10.
- [x] **Removed keyword post-filter** — deleted `_keyword_match` from `apply_query_constraints`; keyword relevance is now fully delegated to API-level search, preventing false-negative rejection of relevant results.
- [x] **Over-fetching** — search fetches 3× the requested limit (capped at 30) per source to compensate for post-filtering attrition ([src/agt/tools/search_papers.py](../src/agt/tools/search_papers.py)).
- [x] **OpenAlex year filter** — year constraint pushed to API `filter=publication_year:>` parameter for server-side filtering ([src/agt/tools/openalex.py](../src/agt/tools/openalex.py)).
- [x] **HTML tag stripping** — OpenAlex titles cleaned of markup tags before normalization.
- [x] CI gates re-validated: `ruff` 0 errors, `pyright` 0 errors, `pytest` 34/34 pass.

**Validation results** (7 queries tested):
| Query | Results | Quality |
|-------|---------|---------|
| most cited 2020+ timeseries | 5 | Anomaly detection, XAI survey, conditional GAN, outlier detection, Pyleoclim |
| RAG 2026 game changers | 1 | RAG for AI-Generated Content survey (22 citations, 2026) |
| retrieval augmented generation | 5 | Top RAG surveys (605, 287, 282 citations) |
| transformer NLP after 2022 | 5 | UNETR (2620), Efficient Transformers (895), GPT review (482) |
| deep RL robotics 2023+ | 5 | Robotic manipulation (189), multi-agent (146), agile soccer (138) |
| trending 2026 timeseries (typo) | 0 | Expected: "trandign" misspelling prevents API match |
| RAG 2026 community perception | 1 | Same RAG survey (only 2026 paper matching constraints) |

**Known limitation**: The pipeline does not correct spelling errors in queries. A future enhancement could add fuzzy keyword matching or LLM-based query rewriting.

#### M2 LLM-Enhanced Semantic Search (Completed)

Problem: regex-based keyword extraction produced poor retrieval queries for natural-language requests.
Example: "nutrition in sport" → keywords "nutrition sport" → API returned papers about AI nursing, corporate governance, etc.

Solution: LLM-powered query rewriting, semantic validation, and iterative refinement.

- [x] **LLM query rewriter** — new module [src/agt/tools/query_rewriter.py](../src/agt/tools/query_rewriter.py) uses the configured LLM provider to translate natural-language requests into optimized academic search queries (e.g. "nutrition in sport" → "sports nutrition"). Few-shot prompted with 3 examples.
- [x] **Semantic result validation** — after initial retrieval the LLM checks whether returned papers are relevant to the original topic. If irrelevant, it suggests an improved search query for automatic retry.
- [x] **Iterative refinement loop** — [src/agt/tools/search_papers.py](../src/agt/tools/search_papers.py) performs up to one LLM-guided retry when validation rejects results. Falls back to regex-based keywords if LLM is unavailable or fails.
- [x] **Robust JSON extraction** — `extract_json()` handles raw JSON, markdown code blocks, and embedded objects from LLM output.
- [x] **Constraint parser fixes** — "not older than 2024" now correctly sets min_year (previously set max_year); "highest/most quoted" recognized as citation indicators.
- [x] **Provider auto-detection in demo** — [examples/m2_retrieval_demo.py](../examples/m2_retrieval_demo.py) builds an LLM provider when a real xAI API key is available; gracefully degrades to regex-only mode otherwise.
- [x] CI gates re-validated: `ruff` 0 errors, `pyright` 0 errors, `pytest` 46/46 pass.

**Architecture flow:**
1. User query → LLM rewrite → optimized academic search query + topic
2. Multi-source search (Semantic Scholar + OpenAlex + Crossref) with optimized query
3. Rank + constraint filter
4. LLM validation → if irrelevant, retry with LLM-suggested alternative query
5. Regex keyword fallback if LLM unavailable or all LLM paths fail

### M3 (Week 3-4): Write Correctness and Idempotency

- [ ] AGT-9: Collection resolver with canonicalized name matching and parent support
- [ ] AGT-10: Zotero item mapper with deterministic creator mapping and validation
- [ ] AGT-11: Idempotent upsert (DOI primary, title+author hash fallback)
- [ ] AGT-12: Write outcome schema created/unchanged/failed and retry-safe failures

### M4 (Week 4-5): Approval-Gated Workflow and MVP Demo

- [ ] AGT-14: Checkpoint-safe AgentState with thread isolation
- [ ] AGT-15: Search -> present -> approve -> write flow with explicit approval gate
- [ ] AGT-17: Streamlit UX for selection, approval, and per-item status
- [ ] AGT-19: Deterministic end-to-end happy path with mocked external services

### M5 (Week 6-8): Production v1 Hardening

- [ ] AGT-16: Resume/retry from checkpoints without duplicate writes
- [ ] AGT-20: Failure-path and partial-success deterministic test suite
- [ ] AGT-18: Backend/API separation with health/run/resume/status endpoints
- [ ] AGT-21: Security hardening and multi-user auth direction documentation
- [ ] AGT-22: Universal LLM interface routing with provider selection policy

### M6 (Parallel Track): Zotero Native Add-on

- [ ] ZAP-0 to ZAP-2: Plugin foundation, hot reload, backend connection layer
- [ ] ZAP-3 to ZAP-5: Sidebar UX for search and explicit approve/reject/edit actions
- [ ] ZAP-6 to ZAP-8: Native collection/item writes with idempotency and optional PDF
- [ ] ZAP-9 to ZAP-11: Preferences, offline/error handling, signing and release automation

## Runnable Examples Per Milestone

- [ ] M1 example: [examples/m1_foundation_demo.py](../examples/m1_foundation_demo.py)
- [x] M2 example: [examples/m2_retrieval_demo.py](../examples/m2_retrieval_demo.py)
- [ ] M3 example: [examples/m3_write_correctness_demo.py](../examples/m3_write_correctness_demo.py)
- [ ] M4 example: [examples/m4_approval_flow_demo.py](../examples/m4_approval_flow_demo.py)
- [ ] M5 example: [examples/m5_hardening_demo.py](../examples/m5_hardening_demo.py)
- [ ] M6 example: [examples/m6_zotero_addon_demo.py](../examples/m6_zotero_addon_demo.py)

### Example Run Commands

- M1: `source .venv/bin/activate && python examples/m1_foundation_demo.py`
- M2: `source .venv/bin/activate && python examples/m2_retrieval_demo.py --query "retrieval augmented generation"`
- M3: `source .venv/bin/activate && python examples/m3_write_correctness_demo.py`
- M4: `source .venv/bin/activate && python examples/m4_approval_flow_demo.py`
- M5: `source .venv/bin/activate && python examples/m5_hardening_demo.py`
- M6: `source .venv/bin/activate && python examples/m6_zotero_addon_demo.py`

### M2 Real-Search Rule

- M2 validation must use live Semantic Scholar + OpenAlex + Crossref results (no fixture or mock fallback).
- If live APIs are rate-limited, treat it as a test-environment issue and retry later; do not switch to mock data.

### M2 Validation Queries (Required — Verified)

- [x] `source .venv/bin/activate && python examples/m2_retrieval_demo.py --query "the most trandign 2026 timeseries papers - list 5" --limit 5`
  Result: 0 papers (expected — "trandign" is a misspelling; pipeline does not perform spelling correction).
- [x] `source .venv/bin/activate && python examples/m2_retrieval_demo.py --query "the most advanced RAG techniques in 2026 - game changers. Make sure the community perception is good!" --limit 5`
  Result: 1 paper (realistic — very few 2026 RAG papers exist yet with sufficient citations).

## Immediate Backlog (Checkbox-Ready)

- [x] Add provider protocol package and baseline xAI adapter implementation
- [ ] Add OpenAI adapter implementing the same LLMProvider contract
- [ ] Add Anthropic adapter implementing the same LLMProvider contract
- [x] Add provider router with explicit selection strategy (config default + per-request override)
- [ ] Add provider health/probe command and startup diagnostics for enabled providers
- [ ] Add model registry config (provider, model, timeout, retries, temperature) with strict validation
- [ ] Add fallback chain policy (primary, secondary, fail-fast) with explicit audit logging
- [x] Add strict config validation tests for missing/invalid secrets
- [x] Implement live Zotero preflight capability check on startup
- [x] Add trace/span helpers and propagate request/thread IDs through workflow state
- [x] Implement Semantic Scholar client with bounded retry and error normalization
- [x] Add multi-source retrieval fallback clients (OpenAlex + Crossref) and merge with shared dedup/rank pipeline
- [x] Add ranking and dedup module with formula tests for recency/open-access weighting
- [ ] Expand AgentState to include checkpoint versioning and audit-safe status fields
- [ ] Implement explicit approval node with guaranteed zero-side-effect reject path
- [ ] Implement collection resolver canonicalization tests (case/trim/parent)
- [ ] Implement item mapper validation tests for journalArticle and preprint
- [ ] Implement idempotent upsert integration tests for duplicate approval re-runs
- [ ] Implement partial-success response rendering in UI and API
- [ ] Add resume-from-checkpoint tests for interrupted post-search and post-approval paths
- [ ] Add CI smoke test for non-approval workflow execution via CLI
- [ ] Switch CI dependency sync to frozen mode and enforce format check parity
- [ ] Move test-only dependencies out of runtime dependency list
- [ ] Add deterministic CI test env vars (for example TZ and PYTHONHASHSEED)
- [ ] Add API contract tests for health/run/resume/status payload schemas
- [ ] Add security checklist section and release gate in documentation
- [ ] Add plugin-backend contract versioning before ZAP-3 implementation starts

## Multi-Provider Rollout Checklist

- [ ] Phase A: Provider abstraction locked and covered by unit tests
- [ ] Phase B: xAI + OpenAI + Anthropic adapters passing shared contract test suite
- [ ] Phase C: Routing policy enabled (single provider, pinned provider, fallback chain)
- [ ] Phase D: Tracing and cost telemetry include provider and model labels
- [ ] Phase E: Failure semantics standardized across providers for UI/API compatibility
- [ ] Phase F: Documentation updated with provider selection, env aliases, and safe defaults

## Backend Gates for ZAP Blocks

- [ ] Gate for ZAP-1 (foundation): AGT-0, AGT-1, AGT-2, AGT-4, AGT-18 done
- [ ] Gate for ZAP-2 (sidebar UX): AGT-5, AGT-6, AGT-7, AGT-15, AGT-27 done
- [ ] Gate for ZAP-3 (native write integration): AGT-10, AGT-11, AGT-12, AGT-14, AGT-16 done
- [ ] Gate for ZAP-3 optional PDF: AGT-13 done
- [ ] Gate for ZAP-4 (release): AGT-19, AGT-20, AGT-21 done

## Documentation Deliverables

- [ ] Keep [docs/core.md](docs/core.md) dependency edges updated when story dependencies change
- [ ] Keep [docs/settings.md](docs/settings.md) aligned with CI and pre-commit behavior
- [ ] Add endpoint contract section to [docs/core.md](docs/core.md) for AGT-18 and plugin usage
- [ ] Add release checklist document for MVP and Production v1 promotion criteria

## PR Checklist Template

- [ ] PR title includes story IDs (for example AGT-11)
- [ ] Acceptance criteria mapped in PR body
- [ ] Unit/integration/e2e tests included where applicable
- [ ] Idempotency checks included for any write-path change
- [ ] Approval-gate behavior validated for workflow changes
- [ ] Trace/log redaction verified for new logs
