# Epic: AGT-1 — Platform foundation
- Type: Epic
- Priority: P0
- Estimate: 3.25d
- Dependencies: None
- Goal: Establish secure configuration, provider boundaries, operational visibility, and typed settings.

## Story: AGT-0 — Pydantic settings model & .env foundation
- Type: Story
- Parent: AGT-1 — Platform foundation
- Priority: P0
- Estimate: 0.25d
- Dependencies: None
- Acceptance Criteria:
  - All credentials and config use `pydantic-settings` with strict validation.
  - Startup fails fast with clear, actionable errors when required secrets are missing.
  - No secret values ever appear in logs (redaction filter applied).
  - Library type configurable as `user` or `group`; provider timeouts and environments override cleanly via `Settings` model.

## Story: AGT-1 — Secrets and environment configuration
- Type: Story
- Parent: AGT-1 — Platform foundation
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-0
- Acceptance Criteria:
  - Startup fails fast when required credentials are missing.
  - No secret values are logged.
  - Library type is configurable as `user` or `group`.
  - Different environments can override provider and timeout settings cleanly.

## Story: AGT-2 — Zotero permission preflight
- Type: Story
- Parent: AGT-1 — Platform foundation
- Priority: P0
- Estimate: 0.5d
- Dependencies: AGT-1
- Acceptance Criteria:
  - System verifies library access and write capability on startup.
  - Clear error message shown when API key lacks write permission.
  - Preflight result exposed in health/status output and traces.

## Story: AGT-3 — LLM provider adapter
- Type: Story
- Parent: AGT-1 — Platform foundation
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-0
- Acceptance Criteria:
  - Single internal `LLMProvider` Protocol exists (invoke / ainvoke + tools support).
  - xAI implementation isolated behind the adapter.
  - Timeout, retries, model name, and temperature are fully config-driven.
  - Easy swap path documented for Anthropic / Groq / OpenAI.

## Story: AGT-4 — Observability and tracing
- Type: Story
- Parent: AGT-1 — Platform foundation
- Priority: P0 (upgraded from P1)
- Estimate: 0.5d
- Dependencies: AGT-1, AGT-3
- Acceptance Criteria:
  - Every workflow has request ID and thread ID (LangSmith or OpenTelemetry native).
  - Search, approval, and Zotero write steps are separately traceable with full spans.
  - Logs are structured (`structlog` / `loguru`) and secrets fully redacted.
  - Human-approval checkpoints visible in trace viewer.

# Epic: AGT-2 — Academic retrieval and ranking
- Type: Epic
- Priority: P0
- Estimate: 8.5d
- Dependencies: AGT-1 — Platform foundation
- Goal: Retrieve relevant papers through a keyless-first federated discovery layer, enforce deterministic query constraints, and normalize everything into one stable internal model.

## Story: AGT-5 — Keyless-first academic retrieval baseline
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P0
- Estimate: 1.5d
- Dependencies: AGT-1
- Acceptance Criteria:
  - Default retrieval works without search-engine API keys using open/easy-access sources first: OpenAlex, Crossref, Semantic Scholar no-key mode, PubMed, Europe PMC, arXiv, BASE, and OpenCitations enrichment where available.
  - Search-engine services that require keys or paid accounts, including CORE, Dimensions, and SerpAPI/Google Scholar, are opt-in enrichment or fallback sources only.
  - Missing optional search-engine keys never block startup, never fail a normal search, and are reported as skipped source metadata.
  - Every source wrapper returns only `NormalizedPaper` Pydantic objects.
  - Requested fields are explicit and minimal.
  - Timeout, retry, rate-limit, and malformed-response handling are covered per source.

## Story: AGT-6 — Deterministic constraints, ranking, and deduplication
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P0
- Estimate: 1.5d
- Dependencies: AGT-5
- Acceptance Criteria:
  - Natural-language constraints are parsed into a deterministic structure before source queries run.
  - Supported hard filters include minimum year, maximum year, date ranges, include terms, exclude terms, open-access preference, citation thresholds, source allowlist/blocklist, and document type where source metadata supports it.
  - Hard filters are pushed down to source APIs when supported and re-applied after merge/dedup.
  - LLM query rewriting may improve topic terms but cannot remove, weaken, or reinterpret hard filters.
  - Duplicate results collapsed before display using DOI + title hash.
  - “Recent papers” queries apply year-aware ranking with an explicit formula that uses the current calendar year dynamically rather than a hardcoded year.
  - Missing fields do not break output.
  - Output always contains stable result indices (0-based).

## Story: AGT-7 — Result summarization and selection model
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-5, AGT-6, AGT-28, AGT-3
- Acceptance Criteria:
  - Presentation uses only internal `NormalizedPaper` models.
  - Each result has stable index and source label.
  - Presentation shows the deterministic search plan and filters that produced the result set.
  - Result summaries cannot hide hard-filter violations; filtered-out papers are excluded before summarization.
  - Summary generation bounded and deterministic (LLM call limited to 3–4 sentences).

## Story: AGT-8 — Optional API-key and fallback retrieval
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P1
- Estimate: 2d
- Dependencies: AGT-5, AGT-6, AGT-23
- Acceptance Criteria:
  - Fallback is feature-flagged and disabled by default.
  - Optional search-engine key sources are used only when configured and explicitly enabled by settings or request policy.
  - Default quality targets must be achievable without CORE, Dimensions, SerpAPI, or any other paid/search-key provider.
  - Source provenance preserved in every `NormalizedPaper`.
  - Cross-source duplicates merged correctly via unified registry.

## Story: AGT-28 — Search plan and deterministic filter contract
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P0
- Estimate: 1.5d
- Dependencies: AGT-5, AGT-6
- Acceptance Criteria:
  - Every query produces a typed `SearchPlan` before retrieval with `original_query`, `topic_query`, `rewritten_queries`, `hard_filters`, `soft_preferences`, `source_policy`, and `source_capabilities`.
  - Example query `time-series forecasting methods selection based on the data itself, not older than 2024` maps to topic terms about method/model selection from data characteristics and a hard `min_year=2024` filter.
  - `SearchPlan` is returned through CLI/API/UI metadata so users can inspect what the system actually searched and filtered.
  - The execution layer records which filters were pushed down per source and which were enforced after merge.
  - Tests prove that no result violating a hard year or exclusion filter survives ranking.

## Story: AGT-29 — Retrieval quality benchmark against standalone LLM search
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-28
- Acceptance Criteria:
  - Curated evaluation panel covers at least 20 realistic research requests across AI, time-series, biomedicine, social science, and interdisciplinary topics.
  - Panel includes freshness and hard-filter cases, including papers not older than 2024 and source-specific domains such as arXiv-heavy CS and PubMed-heavy biomedical queries.
  - For each query, record expected must-find papers, acceptable alternate papers, constraint compliance, freshness, source coverage, and ranking quality.
  - Compare SciAgent results against a manually reviewed standalone LLM/web-search baseline and require SciAgent to match or exceed the baseline on constraint compliance and must-find recall before release promotion.
  - Benchmark output is deterministic, versioned, and runnable without paid/search-engine API keys; optional keyed sources may be reported separately as enrichment.

# Epic: AGT-3 — Zotero write pipeline
- Type: Epic
- Priority: P0
- Estimate: 5.5d
- Dependencies: AGT-1 — Platform foundation
- Goal: Make writes correct, resumable, and idempotent.

## Story: AGT-9 — Collection resolver
- Type: Story
- Parent: AGT-3 — Zotero write pipeline
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-2
- Acceptance Criteria:
  - Existing collection name matches reused by canonicalized name (case-insensitive + trimmed).
  - Parent collection support exists.
  - Resolver returns stable internal `CollectionResult` object.

## Story: AGT-10 — Zotero item mapping and validation
- Type: Story
- Parent: AGT-3 — Zotero write pipeline
- Priority: P0
- Estimate: 1.5d
- Dependencies: AGT-2, AGT-5
- Acceptance Criteria:
  - Supports at least `journalArticle` and `preprint` item types.
  - Creator mapping deterministic (name → creatorType).
  - Invalid fields detected and logged before any write call.

## Story: AGT-11 — Idempotent paper upsert
- Type: Story
- Parent: AGT-3 — Zotero write pipeline
- Priority: P0
- Estimate: 2.5d (increased)
- Dependencies: AGT-9, AGT-10, AGT-14
- Acceptance Criteria:
  - Re-running same approval never creates duplicates (DOI primary check + title+author hash fallback).
  - Partial success reported item-by-item.
  - Duplicate detection covered by unit + integration tests.

## Story: AGT-12 — Correct create response handling
- Type: Story
- Parent: AGT-3 — Zotero write pipeline
- Priority: P1
- Estimate: 0.5d
- Dependencies: AGT-9, AGT-10
- Acceptance Criteria:
  - Internal result object captures created / unchanged / failed outcomes.
  - UI can represent partial success cleanly.
  - Failures are retry-safe when appropriate.

## Story: AGT-13 — PDF attachment pipeline
- Type: Story
- Parent: AGT-3 — Zotero write pipeline
- Priority: P1 (upgraded from P2)
- Estimate: 2d
- Dependencies: AGT-11, AGT-25
- Acceptance Criteria:
  - PDF attachment feature-flagged and optional per workflow.
  - Downloads use `httpx` async + SHA256 checksum + cleanup.
  - Attachment failures never corrupt main item write flow.

# Epic: AGT-4 — Agent workflow with human approval
- Type: Epic
- Priority: P0
- Estimate: 4d
- Dependencies: AGT-1 — Platform foundation, AGT-2 — Academic retrieval and ranking, AGT-3 — Zotero write pipeline
- Goal: Implement the durable workflow, not a chat-script approximation.

## Story: AGT-14 — State schema and thread isolation
- Type: Story
- Parent: AGT-4 — Agent workflow with human approval
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-1, AGT-3, AGT-5
- Acceptance Criteria:
  - No global `last_search_results` style state.
  - Concurrent sessions cannot cross-contaminate (thread_id isolation).
  - Full state serializable and checkpoint-safe, including:
    ```python
    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]
        papers: list[NormalizedPaper]
        collection_name: str | None
        approved: bool
        write_result: dict | None
    ```

## Story: AGT-15 — LangGraph search → present → approve → write flow
- Type: Story
- Parent: AGT-4 — Agent workflow with human approval
- Priority: P0
- Estimate: 2d
- Dependencies: AGT-7, AGT-9, AGT-10, AGT-14
- Acceptance Criteria:
  - No write occurs before explicit human approval.
  - Reject path exits cleanly with zero side effects.
  - Edit / rename collection path fully supported.
  - Final graph state contains audit-friendly status.

## Story: AGT-16 — Resume, retry, and checkpoint restore
- Type: Story
- Parent: AGT-4 — Agent workflow with human approval
- Priority: P1
- Estimate: 1d
- Dependencies: AGT-15
- Acceptance Criteria:
  - Interrupted workflows resume from saved checkpoint.
  - Retrying from approval or post-search never duplicates writes.
  - Resume path fully test-covered.

# Epic: AGT-5 — UI and product delivery
- Type: Epic
- Priority: P1
- Estimate: 3.5d
- Dependencies: AGT-4 — Agent workflow with human approval
- Goal: Prototype fast without locking the final backend shape.

## Story: AGT-17 — Streamlit prototype chat UI
- Type: Story
- Parent: AGT-5 — UI and product delivery
- Priority: P1
- Estimate: 1d
- Dependencies: AGT-15
- Acceptance Criteria:
  - User can search, review, select, approve, and see final status.
  - `st.experimental_fragment` used for approval buttons (no full rerun).
  - Per-item outcome displayed; error messages readable and actionable.

## Story: AGT-18 — Backend/API separation for production
- Type: Story
- Parent: AGT-5 — UI and product delivery
- Priority: P1
- Estimate: 2.5d
- Dependencies: AGT-15, AGT-16, AGT-17
- Acceptance Criteria:
  - Backend exposes health, run, resume, and status endpoints (LangGraph + FastAPI).
  - UI never stores secrets in browser/session.
  - Dockerized deployment ready out of the box.

# Epic: AGT-6 — Reliability, security, and testing
- Type: Epic
- Priority: P0
- Estimate: 4d
- Dependencies: AGT-1 — Platform foundation, AGT-4 — Agent workflow with human approval, AGT-5 — UI and product delivery
- Goal: Make the system safe under real-world failure modes.

## Story: AGT-19 — End-to-end happy-path tests
- Type: Story
- Parent: AGT-6 — Reliability, security, and testing
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-15, AGT-17
- Acceptance Criteria:
  - One green E2E test covers full workflow.
  - CI uses mocked external services (`responses` + `vcrpy`).
  - Verifies collection resolution and exact item counts.

## Story: AGT-20 — Edge-case and failure-path tests
- Type: Story
- Parent: AGT-6 — Reliability, security, and testing
- Priority: P1
- Estimate: 1.5d
- Dependencies: AGT-19, AGT-12, AGT-16
- Acceptance Criteria:
  - Every major failure mode has deterministic user-facing outcome.
  - Retries bounded and logged.
  - Partial failures never misreported as success.

## Story: AGT-21 — Security hardening and auth direction
- Type: Story
- Parent: AGT-6 — Reliability, security, and testing
- Priority: P1
- Estimate: 1d
- Dependencies: AGT-1, AGT-2, AGT-18
- Acceptance Criteria:
  - Secrets redacted everywhere.
  - Per-user/thread isolation validated.
  - Security checklist exists for pre-production review.
  - Future multi-user delegated-auth path documented.

## Story: AGT-27 — Rate-limit & quota guardrails
- Type: Story
- Parent: AGT-6 — Reliability, security, and testing
- Priority: P1
- Estimate: 0.5d
- Dependencies: AGT-5, AGT-3
- Acceptance Criteria:
  - Default keyless retrieval source limits, optional keyed search-source limits, Zotero limits, and LLM limits are enforced via `tenacity` + token bucket per thread_id.
  - Optional paid/keyed search providers have independent quotas and can be disabled without affecting keyless search.
  - Cost guard (max $0.50 per workflow) configurable.
  - Backoff and user-friendly “try again later” messages.

# Epic: AGT-7 — Multi-provider abstraction
- Type: Epic
- Priority: P1
- Estimate: 4d
- Dependencies: AGT-1 — Platform foundation, AGT-2 — Academic retrieval and ranking
- Goal: Avoid vendor lock-in for both LLMs and retrieval.

## Story: AGT-22 — Universal LLM interface and routing
- Type: Story
- Parent: AGT-7 — Multi-provider abstraction
- Priority: P1
- Estimate: 2d
- Dependencies: AGT-3, AGT-20
- Acceptance Criteria:
  - One config switch changes LLM provider.
  - Tool schemas compile through shared abstraction layer.
  - Fallback provider invoked on primary 429/timeout.
  - Provider selection and failover logged.

## Story: AGT-23 — Unified retrieval registry
- Type: Story
- Parent: AGT-7 — Multi-provider abstraction
- Priority: P1
- Estimate: 2d
- Dependencies: AGT-5, AGT-6
- Acceptance Criteria:
  - Adding new provider requires only one interface implementation.
  - All map into same `NormalizedPaper` model.
  - Federated queries merge via shared dedup logic.
  - Registry records each source capability: requires API key, default enabled, supports year pushdown, supports open-access filtering, supports full text/snippets, supports citations, rate-limit policy, and failure behavior.
  - Default registry order prioritizes no-key/easy-access sources over keyed or paid search engines.

# Epic: AGT-8 — Elastic infrastructure and scaling
- Type: Epic
- Priority: P1
- Estimate: 6d
- Dependencies: AGT-4 — Agent workflow with human approval, AGT-5 — UI and product delivery, AGT-7 — Multi-provider abstraction
- Goal: Survive concurrency, long-running tasks, and multi-container deployment.

## Story: AGT-24 — Durable distributed checkpointing
- Type: Story
- Parent: AGT-8 — Elastic infrastructure and scaling
- Priority: P0
- Estimate: 1.5d
- Dependencies: AGT-16, AGT-18
- Acceptance Criteria:
  - Workflow state stored in Redis/Postgres (LangGraph native checkpointer).
  - Containers fully stateless.
  - Workflow paused on one container resumes on another.

## Story: AGT-25 — Asynchronous task queue for long-running work
- Type: Story
- Parent: AGT-8 — Elastic infrastructure and scaling
- Priority: P1
- Estimate: 2d
- Dependencies: AGT-18, AGT-24
- Acceptance Criteria:
  - API returns `task_id` immediately.
  - Worker processes execute outside request lifecycle (Celery/Dramatiq).
  - UI can poll or subscribe for updates.

## Story: AGT-26 — Cloud-agnostic infrastructure as code
- Type: Story
- Parent: AGT-8 — Elastic infrastructure and scaling
- Priority: P2
- Estimate: 2.5d
- Dependencies: AGT-24, AGT-25, AGT-21
- Acceptance Criteria:
  - IaC modules for compute, persistence, queue, networking.
  - Secret injection via managed store (non-local).
  - CI/CD deploys full stack automatically.

# Release: MVP
- Type: Release
- Priority: P0
- Estimate: 13.5d
- Dependencies: AGT-0–AGT-3, AGT-5–AGT-7, AGT-9–AGT-11, AGT-14–AGT-15, AGT-17, AGT-19, AGT-27–AGT-29
- Acceptance Criteria:
  - User can search papers in natural language.
  - Default search works without search-engine API keys beyond the configured LLM provider and Zotero credentials.
  - Natural-language constraints are visible as deterministic filters, including year constraints such as `year >= 2024`.
  - User can review shortlisted papers before any write occurs.
  - User can approve creation or reuse of a Zotero collection.
  - Selected items added idempotently (DOI protection).
  - One end-to-end happy-path test is green.
  - Secrets, preflight, tracing, and rate guards in place.

# Release: Production v1
- Type: Release
- Priority: P1
- Estimate: 6d
- Dependencies: AGT-4, AGT-12, AGT-16, AGT-18, AGT-20, AGT-21
- Acceptance Criteria:
  - Workflow resume fully supported.
  - Backend and UI cleanly separated.
  - All failure paths covered by tests.
  - Security review and redaction rules complete.

# Release: Production v2
- Type: Release
- Priority: P1
- Estimate: 9d
- Dependencies: AGT-22, AGT-23, AGT-24, AGT-25
- Acceptance Criteria:
  - LLM provider swappable by configuration.
  - Retrieval providers pluggable, federated, capability-described, and keyless-first by default.
  - Workflow state persists across containers.
  - Long-running execution handled asynchronously.

# Release: Later / SaaS phase
- Type: Release
- Priority: P2
- Estimate: 6d
- Dependencies: AGT-8, AGT-13, AGT-26
- Acceptance Criteria:
  - Optional fallback retrieval supported.
  - Optional PDF attachment pipeline supported.
  - Full infrastructure deployable via IaC in managed cloud.
