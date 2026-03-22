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
- Estimate: 6d
- Dependencies: AGT-1 — Platform foundation
- Goal: Retrieve relevant papers and normalize them into one stable internal model.

## Story: AGT-5 — Semantic Scholar client wrapper
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-1
- Acceptance Criteria:
  - Wrapper returns only `NormalizedPaper` Pydantic objects.
  - Requested fields are explicit and minimal.
  - Timeout, retry, and malformed-response handling fully covered.

## Story: AGT-6 — Ranking, filtering, and deduplication
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P0
- Estimate: 1.5d
- Dependencies: AGT-5
- Acceptance Criteria:
  - Duplicate results collapsed before display using DOI + title hash.
  - “Recent papers” queries apply year-aware ranking with explicit formula:  
    `score = semantic_score * 0.7 + (2026 - year) * -0.3 + (open_access ? 0.2 : 0)`.
  - Missing fields do not break output.
  - Output always contains stable result indices (0-based).

## Story: AGT-7 — Result summarization and selection model
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P0
- Estimate: 1d
- Dependencies: AGT-5, AGT-6, AGT-3
- Acceptance Criteria:
  - Presentation uses only internal `NormalizedPaper` models.
  - Each result has stable index and source label.
  - Summary generation bounded and deterministic (LLM call limited to 3–4 sentences).

## Story: AGT-8 — Optional recommendation and fallback retrieval
- Type: Story
- Parent: AGT-2 — Academic retrieval and ranking
- Priority: P2
- Estimate: 2d
- Dependencies: AGT-5, AGT-6, AGT-23
- Acceptance Criteria:
  - Fallback is feature-flagged.
  - Source provenance preserved in every `NormalizedPaper`.
  - Cross-source duplicates merged correctly via unified registry.

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
  - Semantic Scholar (100 req/min), Zotero (60 req/min), and LLM rate limits enforced via `tenacity` + token bucket per thread_id.
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
- Estimate: 11d (optimized from original 13.5d)
- Dependencies: AGT-0–AGT-3, AGT-5–AGT-7, AGT-9–AGT-11, AGT-14–AGT-15, AGT-17, AGT-19, AGT-27
- Acceptance Criteria:
  - User can search papers in natural language.
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
  - Retrieval providers pluggable and federated.
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
