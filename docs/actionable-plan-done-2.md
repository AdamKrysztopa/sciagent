# SciAgent Prioritized Action Plan — P8

> **Last audit: 2026-05-13** — All P0–P7 milestones complete. All OPN-01 through OPN-17 done.
> This plan covers **P8: Baseline Search + Provider Capability**.
>
> Canonical execution tracker. Update done / not done state here first.
> See [docs/manual.md](manual.md) for configuration & usage.

## Design Philosophy

**No-key baseline.** Baseline academic search works out-of-the-box with zero provider API keys.
Hosted LLM providers still require an LLM key, while Ollama can run locally without a hosted key.
The six keyless academic sources — OpenAlex, Semantic Scholar (keyless path), Crossref, arXiv,
Europe PMC, DOAJ — are the permanent default. Optional keyed providers (CORE full, Dimensions,
SerpAPI) auto-activate when a key is set, visible in the sidebar as upgrade options.

**Optional provider** unlocks:

`AGT_SEMANTIC_SCHOLAR_API_KEY` - higher authenticated Semantic Scholar throughput
`AGT_NCBI_API_KEY` - higher PubMed request limits
`AGT_CORE_API_KEY` - CORE full-text / OA repository provider
`AGT_SERPAPI_KEY` - Google Scholar via SerpAPI
`AGT_DIMENSIONS_KEY` - Dimensions paid/institutional metadata

**The infrastructure for this already exists:** `_build_retrieval_registry` in
`src/agt/tools/search_papers.py` checks `settings.core_api_key`, `settings.dimensions_key`,
`settings.serpapi_key` and creates disabled `_RetrievalProvider` entries with
`skip_reason="no_key"`. `SourceTerminalState.skipped_no_key` already surfaces in
`SearchMetadata.source_states` and `SearchCoveragePanel`. What's missing is richer capability
metadata, a formal provider protocol, field-level merge provenance, and the BYOK hint UI.

**Guiding principle (from external review):**

> Deterministic, auditable, Zotero-native research intake from question to curated collection.
>
> No LLM in the citation path. Every field on every result must be traceable to a provider.
> Zotero writes stay approval-gated.

---

## Release Readiness

**Release gate:** when the P8 acceptance checks pass, SciAgent is releasable with an LLM-only
minimum setup for baseline search and review. Users do not need academic provider keys to get a
useful default experience.

The launch baseline runs through keyless or public provider paths where available: OpenAlex,
Semantic Scholar keyless search, Crossref, arXiv, Europe PMC, and DOAJ. Optional provider keys
must unlock additional capability rather than block release. When an optional key is absent, the
provider should either run in its keyless mode or appear as skipped/missing-key in coverage
metadata, with no silent failure.

Zotero credentials are write-path specific, not academic-search launch blockers. Native Zotero
writes remain approval-gated, and any Web API write path still follows the preflight and
idempotent upsert rules.

### Optional Provider Unlocks

| Optional setting               | Provider                   | Unlocks                                                                                                                                                   |
| ------------------------------ | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AGT_SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar           | Higher authenticated throughput and more reliable access for citation-heavy or recommendation-heavy queries; keyless search remains part of the baseline. |
| `AGT_NCBI_API_KEY`             | NCBI/PubMed                | Higher PubMed request limits for biomedical retrieval; PubMed remains usable without a key at lower public limits.                                        |
| `AGT_CORE_API_KEY`             | CORE                       | Activates the CORE full-text/open-access repository provider and OA URL backfill path when available.                                                     |
| `AGT_SERPAPI_KEY`              | Google Scholar via SerpAPI | Adds the paid SerpAPI-backed Google Scholar provider for Scholar-specific ranking and grey-literature coverage.                                           |
| `AGT_DIMENSIONS_KEY`           | Dimensions                 | Adds the Dimensions provider for paid/institutional research metadata, citation, funding, patent, or clinical-trial context where available.              |

LLM setup remains the only hard credential requirement for the AI workflow: built-in providers use
`AGT_OPENAI_API_KEY`, `AGT_ANTHROPIC_API_KEY`, `AGT_XAI_API_KEY`, or `AGT_GROQ_API_KEY`; custom
OpenAI-compatible providers use `AGT_LLM_API_KEY` plus `AGT_LLM_BASE_URL`; Ollama mode can run
locally with `AGT_LLM_PROVIDER=ollama` and no hosted LLM key.

---

## Execution Tracker

### Current Status

- All P0–P7 milestones complete as of 2026-05-12.
- Current status: **P8.14 complete — `AGT_DISABLED_PROVIDERS` config + disabled-by-config provider state; `.env.example` updated; 6-query P8 benchmark panel extension (P8-OA-01 through P8-CONF-01); `docs/benchmark.md` P8 section; 2 new orchestrator tests. 563 Python / 103 frontend tests green. All P8 stories complete.**
- Next target: **P9** (or backlog review).

### Recent Progress

- ✅ OPN-06 complete (2026-05-12): External baseline comparison. See `docs/benchmark.md`.
- ✅ OPN-07 complete (2026-05-12): `search_depth=deep` mitigates TS-02/BIO-04; BIO-01 confirmed API coverage gap.
- ✅ OPN-08 complete (2026-05-12): `docs/api.md` full rewrite — all 20+ endpoints accurate.
- ✅ FirstRunDialog complete (2026-05-12): binary-missing download UI wired.
- ✅ All P7 items (OPN-01–OPN-17) complete 2026-05-12.
- ✅ P8.1 complete (2026-05-13): `capabilities.py`, `provider_base.py`, `GET /providers`, BYOK hint chip.
- ✅ P8.2 complete (2026-05-13): DOAJ provider, provider audit (UA/retry/429), `SearchRunResult`, `baseline_mode` badge, baseline regression test. 455 tests green.
- ✅ P8.3 complete (2026-05-13): `NormalizedAuthor`, `ProvenanceField`, extended `NormalizedPaper`, all providers migrated to emit `NormalizedAuthor`. 455 tests green.
- ✅ P8.4 complete (2026-05-13): field-level merge + `FieldConflict` model + `merge.py` wired. 473 tests green.
- ✅ P8.5 complete (2026-05-13): `DEPTH_PROFILES`, `select_providers_for_depth`, `DepthPlanPreview` in sidebar. 498 Python / 82 frontend tests green.
- ✅ P8.6 complete (2026-05-13): `explain_missing.py` with 5 reason codes, missing-field tooltips in result cards. All gates green.
- ✅ P8.7 complete (2026-05-14): `_profile_skipped` + `annotate_missing` loop wired into `run_search_phase`; provenance source chips, conflict dot + approval-card warning, `/providers` capability matrix in sidebar. 506 Python / 94 frontend tests green.
- ✅ P8.8 complete (2026-05-14): `author_resolver.py` (`resolve_author` across OpenAlex + S2, ORCID dedup); `HardFilters.author_ids` + post-merge author-ID filter; author chips (OpenAlex/ORCID links) in result cards. All gates green.
- ✅ P8.9 complete (2026-05-14): `SearchPlan.seed_dois`; `citation_expander.py` (`expand_citations` via OpenCitations + OpenAlex, tagged with `citation_relation`); directional citation badge (`↓ ref` / `↑ cites`) in result cards. 531 Python / 103 frontend tests green.
- ✅ P8.10 complete (2026-05-14): `key_validator.py` with SSRF-safe allowlist; `POST /keys/validate` endpoint; `ProviderKeyRow` key entry panel in ConfigPanel with per-provider validate-on-demand UI; `validateKey` in controller hook. All gates green.
- ✅ P8.11 complete (2026-05-14): 9-step provider onboarding checklist appended to `docs/providers.md`; `scripts/new_provider.py` scaffold generator (CamelCase → snake_case, emits `SearchProviderBase` skeleton + `anyio` test stub, skip-if-exists guard); `pyrightconfig.json` extended with `scripts/`. All gates green.
- ✅ P8.12 complete (2026-05-14): P8.12-A already done (44 tests in `test_provider_snapshots.py`); `test_merge.py` (12 tests), `test_capabilities.py` (14 tests), `test_explain_missing.py` (8 tests), `test_search_orchestrator.py` (5 tests); `live_api` + `regression_gate` markers in conftest.py; `test_zero_key_smoke.py` (1 test), `test_regression_gate.py` (4 tests); CI benchmark regression gate step in `ci.yml`. 561 Python tests green (+30).
- ✅ P8.13 complete (2026-05-14): `AGT_DISABLED_PROVIDERS` field added to `Settings` (pydantic-settings `list[str]`, JSON array format); disabled-by-config pass wired into `_build_retrieval_registry` — any named provider gets `enabled=False, skip_reason="disabled"` regardless of key availability; `.env.example` updated with `AGT_MAILTO` and `AGT_DISABLED_PROVIDERS` entries; 2 new tests in `test_search_orchestrator.py` (keyless + keyed provider disable). 563 Python tests green.
- ✅ P8.14 complete (2026-05-14): 6 new PanelEntry objects added to benchmark panel (P8-OA-01, P8-CITE-01, P8-DEPTH-01, P8-MULTI-01, P8-YEAR-01, P8-CONF-01); `_MIN_MUST_FIND_TARGETS` updated from 12 to 15; `docs/benchmark.md` P8 Benchmark Update section appended with per-query table, rationale, and updated panel statistics (22→28 queries). Docs gate (markdownlint + mkdocs strict) green.

### P8 Status

| ID      | Story                                            | Effort | Status  |
| ------- | ------------------------------------------------ | ------ | ------- |
| P8.0-A  | Provider inventory table (`docs/providers.md`)   | ~0.25d | done    |
| P8.0-B  | Snapshot VCR tests                               | ~0.5d  | done    |
| P8.0-C  | Cassette hygiene + `provider_snapshot` marker    | ~0.25d | done    |
| P8.1-A  | `capabilities.py` — capability + health model    | ~0.5d  | done    |
| P8.1-B  | `provider_base.py` — protocol + base class       | ~0.5d  | done    |
| P8.1-C  | `GET /providers` endpoint                        | ~0.25d | done    |
| P8.1-D  | Sidebar BYOK hint chip                           | ~0.25d | done    |
| P8.2-A  | DOAJ provider (`src/agt/tools/doaj.py`)          | ~0.5d  | done    |
| P8.2-B  | Provider audit (User-Agent, retry, 429)          | ~0.5d  | done    |
| P8.2-C  | `SearchRunResult` dataclass                      | ~0.25d | done    |
| P8.2-D  | `SearchMetadata.baseline_mode` + badge           | ~0.25d | done    |
| P8.2-E  | Baseline regression test (zero-key)              | ~0.25d | done    |
| P8.3-A  | `NormalizedAuthor` Pydantic model                | ~0.25d | done    |
| P8.3-B  | `ProvenanceField` Pydantic model                 | ~0.1d  | done    |
| P8.3-C  | Extend `NormalizedPaper` with new fields         | ~0.5d  | done    |
| P8.3-D  | Update all providers to emit `NormalizedAuthor`  | ~0.5d  | done    |
| P8.4-A  | `src/agt/tools/merge.py`                         | ~1d    | done    |
| P8.4-B  | Field-selection rules                            | ~0.5d  | done    |
| P8.4-C  | `FieldConflict` model                            | ~0.25d | done    |
| P8.4-D  | Wire merge into `run_search_phase`               | ~0.25d | done    |
| P8.5-A  | `DEPTH_PROFILES` + `select_providers_for_depth`  | ~0.25d | done    |
| P8.5-B  | Depth plan preview in sidebar                    | ~0.25d | done    |
| P8.6-A  | `src/agt/tools/explain_missing.py`               | ~0.25d | done    |
| P8.6-B  | Result card missing-field tooltip                | ~0.25d | done    |
| P8.7-A  | Merge + explain_missing in `run_search_phase`    | ~0.5d  | done    |
| P8.7-B  | Provenance chips in `ResultsList.tsx`            | ~0.25d | done    |
| P8.7-C  | Conflict warnings in approval dialog             | ~0.25d | done    |
| P8.7-D  | `/providers` surface in sidebar                  | ~0.25d | done    |
| P8.8-A  | Author resolver tool                             | ~0.75d | done    |
| P8.8-B  | `HardFilters.author_ids`                         | ~0.5d  | done    |
| P8.8-C  | Author chips in `ResultsList.tsx`                | ~0.5d  | done    |
| P8.9-A  | `SearchPlan.seed_dois`                           | ~0.25d | done    |
| P8.9-B  | Citation expansion tool                          | ~1d    | done    |
| P8.9-C  | Directional citation badge                       | ~0.25d | done    |
| P8.10-A | `POST /keys/validate`                            | ~0.5d  | done    |
| P8.10-B | Key entry panel in `ConfigPanel.tsx`             | ~1d    | done    |
| P8.10-C | Preference store bridging                        | ~0.5d  | done    |
| P8.11-A | `docs/providers.md` onboarding checklist         | ~0.25d | done    |
| P8.11-B | `scripts/new_provider.py` scaffold               | ~0.5d  | done    |
| P8.12-A | VCR cassettes (44 total, 11 providers × 4 cases) | ~0.25d | done    |
| P8.12-B | `tests/test_merge.py`                            | ~0.25d | done    |
| P8.12-C | `tests/test_capabilities.py`                     | ~0.1d  | done    |
| P8.12-D | `tests/test_explain_missing.py`                  | ~0.1d  | done    |
| P8.12-E | `tests/test_search_orchestrator.py`              | ~0.1d  | done    |
| P8.12-F | Zero-key smoke test (`@pytest.mark.live_api`)    | ~0.1d  | done    |
| P8.12-G | Regression gate in CI (≥ 19/22 benchmark)        | ~0.25d | done    |
| P8.13-A | New config fields (`AGT_MAILTO`, etc.)           | ~0.25d | ✅ done |
| P8.13-B | Disabled-by-config provider state                | ~0.25d | ✅ done |
| P8.13-C | `.env.example` update                            | ~0.1d  | ✅ done |
| P8.14-A | New 6-query benchmark panel                      | ~0.5d  | ✅ done |
| P8.14-B | `docs/benchmark.md` P8 update                    | ~0.1d  | ✅ done |

**All P8 stories complete as of 2026-05-14.**

---

## P8 Milestones

### P8.0 — Snapshot Safety Net _(½ day)_

> Source: reviewer Phase 0. Must land first — later phases refactor the provider layer.

**Goal:** Pin current provider output so any behavioral change in P8.1+ is intentional and
detectable.

**What already exists:** VCR cassettes exist for several providers under `tests/cassettes/`.
`--vcr-record=none` is already the CI default (confirmed in `CLAUDE.md` quality gates). The
`tests/cassettes/.gitignore` rules need audit.

| ID     | Story                                                                                                                                                                                                                                                                                                                                                                                                                   | Effort |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.0-A | **Provider inventory table** — document in `docs/providers.md`: each of `OpenAlexClient`, `CrossrefClient`, `ArxivClient`, `EuropePMCClient`, `PubMedClient`, `BaseSearchClient` (BASE SRU), `SemanticScholarClient`, `OpenCitationsClient`, `CoreClient`, `DimensionsClient`, `GoogleScholarClient`: base URL, auth model (keyless / key-required), fields populated today, retry/timeout wiring (tenacity or manual). | ~0.25d |
| P8.0-B | **Snapshot VCR tests** — add `tests/test_provider_snapshots.py` with one VCR cassette per provider covering: happy path (5+ results), empty results, 5xx, and 429. Must pass with `--vcr-record=none` throughout P8.                                                                                                                                                                                                    | ~0.5d  |
| P8.0-C | **Cassette hygiene** — verify `tests/cassettes/.gitignore` excludes no committed cassettes; add rule if missing. Add `conftest.py` marker `@pytest.mark.provider_snapshot` so snapshots can be run selectively.                                                                                                                                                                                                         | ~0.25d |

**Acceptance:** `pytest -m provider_snapshot --vcr-record=none` is green. Inventory table exists in `docs/providers.md`. No behavior changes.

---

### P8.1 — Provider Capability + Health Model _(1 day)_

> Source: reviewer Phase 1, corrected to actual codebase names.

**Goal:** Every search provider declares what it _can_ return and its current runtime state.
No search behavior changes — pure infrastructure that P8.2–P8.7 build on.

**Two-layer design (explicit):** `SearchProviderCapabilities.fields` is a
`dict[ProviderField, FieldSupport]` — a static, immutable declaration of what a provider _can_
return, independent of any particular query. `ProviderHealth` is the mutable runtime view,
updated on every search call. The `/providers` endpoint returns both layers keyed by provider
name. Keeping them distinct is what makes "why is the abstract empty?" answerable (P8.6).

**What already exists:** `SourceCapability` in `src/agt/models.py` has only `name`, `tier`,
`enabled`, `supports_year_filter`, `supports_open_access_filter`. `SourceTerminalState`
(terminal states per run) exists but is distinct from per-provider health. No formal provider
protocol exists — each client (`OpenAlexClient`, etc.) has `async def search(query, *, limit)`
by convention only.

**Critical naming note:** `BaseSearchClient` in `src/agt/tools/base_search.py` is the
Bielefeld Academic Search Engine (BASE SRU) client — not a base class. New base
infrastructure goes in `src/agt/tools/provider_base.py` as `SearchProviderBase`.

| ID     | Story                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Effort |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.1-A | **`src/agt/tools/capabilities.py`** — add `ProviderField` enum (`TITLE`, `ABSTRACT`, `AUTHORS`, `DOI`, `YEAR`, `VENUE`, `CITATION_COUNT`, `OA_URL`, `REFERENCES`, `RELATED`); `FieldSupport` enum (`FULL`, `SHALLOW`, `NONE`); `SearchProviderCapabilities` frozen dataclass; `ProviderStatus` enum (`AVAILABLE`, `SHALLOW`, `DISABLED`, `MISSING_KEY`, `FAILED`, `RATE_LIMITED`); `ProviderHealth` Pydantic model. Canonical capability tables for all baseline providers. Replace minimal `SourceCapability` fields with reference to `SearchProviderCapabilities`. | ~0.5d  |
| P8.1-B | **`src/agt/tools/provider_base.py`** — `SearchProviderProtocol(Protocol)` (distinct from `LLMProvider`): requires `capabilities() -> SearchProviderCapabilities`, `health() -> ProviderHealth`, `async search(query, *, limit, author, year_from, year_to) -> list[NormalizedPaper]`. `SearchProviderBase` convenience class with retry + health bookkeeping. Adapt existing clients as wrappers.                                                                                                                                                                     | ~0.5d  |
| P8.1-C | **`/providers` API endpoint** — in `src/agt/api/app.py`, add `GET /providers` returning capability + health matrix keyed by provider name. Include `requires_key`, `key_env_var`, `key_upgrade_hint` for CORE/Dimensions/SerpAPI.                                                                                                                                                                                                                                                                                                                                     | ~0.25d |
| P8.1-D | **Sidebar BYOK hint** — in `zotero-addon/src/ui/components/SearchCoveragePanel.tsx`, render a muted chip for `skipped_no_key` sources showing the `key_upgrade_hint` on hover.                                                                                                                                                                                                                                                                                                                                                                                        | ~0.25d |

**`src/agt/tools/capabilities.py` (corrected snippet):**

```python
"""Provider capability declarations and runtime health model.

NOTE: Do not confuse SearchProviderBase (this module's base class)
with BaseSearchClient (src/agt/tools/base_search.py — the BASE SRU provider).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel


class ProviderField(str, Enum):
    """Fields any search provider may return."""
    TITLE = "title"
    ABSTRACT = "abstract"
    AUTHORS = "authors"
    DOI = "doi"
    YEAR = "year"
    VENUE = "venue"
    CITATION_COUNT = "citation_count"
    OA_URL = "oa_url"        # maps to NormalizedPaper.url
    REFERENCES = "references"
    RELATED = "related"


class FieldSupport(str, Enum):
    FULL = "full"
    SHALLOW = "shallow"
    NONE = "none"


@dataclass(frozen=True)
class SearchProviderCapabilities:
    name: str
    fields: dict[ProviderField, FieldSupport]
    requires_key: bool = False
    key_env_var: str | None = None
    key_upgrade_hint: str | None = None
    notes: str = ""

    def supports(self, f: ProviderField) -> FieldSupport:
        return self.fields.get(f, FieldSupport.NONE)


class ProviderStatus(str, Enum):
    AVAILABLE = "available"
    SHALLOW = "shallow"
    DISABLED = "disabled"
    MISSING_KEY = "missing_key"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class ProviderHealth(BaseModel):
    status: ProviderStatus = ProviderStatus.AVAILABLE
    reason: str = ""
    last_ok_at: float | None = None
    last_error_at: float | None = None
    consecutive_failures: int = 0
    retry_after: float | None = None


# ── Canonical capability tables ──────────────────────────────────────────────
# Static — describes the API contract, not any specific query result.
# ProviderHealth carries the runtime view.

OPENALEX_CAPS = SearchProviderCapabilities(
    name="openalex",
    requires_key=False,
    fields={
        ProviderField.TITLE: FieldSupport.FULL,
        ProviderField.ABSTRACT: FieldSupport.FULL,      # reconstructed from inverted index
        ProviderField.AUTHORS: FieldSupport.FULL,
        ProviderField.DOI: FieldSupport.FULL,
        ProviderField.YEAR: FieldSupport.FULL,
        ProviderField.VENUE: FieldSupport.FULL,
        ProviderField.CITATION_COUNT: FieldSupport.FULL,
        ProviderField.OA_URL: FieldSupport.FULL,
        ProviderField.REFERENCES: FieldSupport.SHALLOW,
        ProviderField.RELATED: FieldSupport.SHALLOW,
    },
    notes="Polite pool via AGT_MAILTO. No key required.",
)

CROSSREF_CAPS = SearchProviderCapabilities(
    name="crossref",
    requires_key=False,
    fields={
        ProviderField.TITLE: FieldSupport.FULL,
        ProviderField.ABSTRACT: FieldSupport.SHALLOW,   # JATS when present
        ProviderField.AUTHORS: FieldSupport.FULL,
        ProviderField.DOI: FieldSupport.FULL,
        ProviderField.YEAR: FieldSupport.FULL,
        ProviderField.VENUE: FieldSupport.FULL,
        ProviderField.CITATION_COUNT: FieldSupport.SHALLOW,
        ProviderField.OA_URL: FieldSupport.SHALLOW,
        ProviderField.REFERENCES: FieldSupport.SHALLOW,
        ProviderField.RELATED: FieldSupport.NONE,
    },
    notes="Authoritative for DOI + bibliographic metadata.",
)

ARXIV_CAPS = SearchProviderCapabilities(
    name="arxiv",
    requires_key=False,
    fields={
        ProviderField.TITLE: FieldSupport.FULL,
        ProviderField.ABSTRACT: FieldSupport.FULL,
        ProviderField.AUTHORS: FieldSupport.FULL,
        ProviderField.DOI: FieldSupport.SHALLOW,        # only when author supplies it
        ProviderField.YEAR: FieldSupport.FULL,
        ProviderField.VENUE: FieldSupport.NONE,
        ProviderField.CITATION_COUNT: FieldSupport.NONE,
        ProviderField.OA_URL: FieldSupport.FULL,        # PDF always available
        ProviderField.REFERENCES: FieldSupport.NONE,
        ProviderField.RELATED: FieldSupport.NONE,
    },
    notes="1 req/3 s per arXiv guidance. No key required.",
)

EUROPE_PMC_CAPS = SearchProviderCapabilities(
    name="europe_pmc",
    requires_key=False,
    fields={
        ProviderField.TITLE: FieldSupport.FULL,
        ProviderField.ABSTRACT: FieldSupport.FULL,
        ProviderField.AUTHORS: FieldSupport.FULL,
        ProviderField.DOI: FieldSupport.FULL,
        ProviderField.YEAR: FieldSupport.FULL,
        ProviderField.VENUE: FieldSupport.FULL,
        ProviderField.CITATION_COUNT: FieldSupport.FULL,
        ProviderField.OA_URL: FieldSupport.FULL,
        ProviderField.REFERENCES: FieldSupport.FULL,    # separate endpoint
        ProviderField.RELATED: FieldSupport.SHALLOW,
    },
    notes="Life-science focus. Excellent OA full-text coverage.",
)

DOAJ_CAPS = SearchProviderCapabilities(
    name="doaj",
    requires_key=False,
    fields={
        ProviderField.TITLE: FieldSupport.FULL,
        ProviderField.ABSTRACT: FieldSupport.FULL,
        ProviderField.AUTHORS: FieldSupport.FULL,
        ProviderField.DOI: FieldSupport.FULL,
        ProviderField.YEAR: FieldSupport.FULL,
        ProviderField.VENUE: FieldSupport.FULL,
        ProviderField.CITATION_COUNT: FieldSupport.NONE,
        ProviderField.OA_URL: FieldSupport.FULL,
        ProviderField.REFERENCES: FieldSupport.NONE,
        ProviderField.RELATED: FieldSupport.NONE,
    },
    notes="Open-access journal articles only. Strong OA URL coverage.",
)

SEMANTIC_SCHOLAR_CAPS = SearchProviderCapabilities(
    name="semantic_scholar",
    requires_key=False,    # key strongly recommended; keyless path is rate-limited
    fields={
        ProviderField.TITLE: FieldSupport.FULL,
        ProviderField.ABSTRACT: FieldSupport.FULL,
        ProviderField.AUTHORS: FieldSupport.FULL,
        ProviderField.DOI: FieldSupport.FULL,
        ProviderField.YEAR: FieldSupport.FULL,
        ProviderField.VENUE: FieldSupport.FULL,
        ProviderField.CITATION_COUNT: FieldSupport.FULL,
        ProviderField.OA_URL: FieldSupport.FULL,
        ProviderField.REFERENCES: FieldSupport.FULL,
        ProviderField.RELATED: FieldSupport.FULL,
    },
    key_env_var="AGT_SEMANTIC_SCHOLAR_API_KEY",
    key_upgrade_hint="Add AGT_SEMANTIC_SCHOLAR_API_KEY to remove rate limits.",
    notes="Keyless calls work but are aggressively rate-limited.",
)

CORE_PUBLIC_CAPS = SearchProviderCapabilities(
    name="core",
    requires_key=True,
    key_env_var="AGT_CORE_API_KEY",
    key_upgrade_hint="Add AGT_CORE_API_KEY to unlock CORE full-text indexing.",
    fields={
        ProviderField.TITLE: FieldSupport.FULL,
        ProviderField.ABSTRACT: FieldSupport.SHALLOW,
        ProviderField.AUTHORS: FieldSupport.SHALLOW,
        ProviderField.DOI: FieldSupport.SHALLOW,
        ProviderField.YEAR: FieldSupport.SHALLOW,
        ProviderField.VENUE: FieldSupport.NONE,
        ProviderField.CITATION_COUNT: FieldSupport.NONE,
        ProviderField.OA_URL: FieldSupport.FULL,
        ProviderField.REFERENCES: FieldSupport.NONE,
        ProviderField.RELATED: FieldSupport.NONE,
    },
    notes="Full API requires key. Use primarily for OA-URL backfill.",
)
```

**`src/agt/tools/provider_base.py` (corrected snippet):**

```python
"""SearchProviderProtocol and SearchProviderBase.

WARNING: Do not confuse with BaseSearchClient (src/agt/tools/base_search.py)
which is the Bielefeld Academic Search Engine (BASE SRU) provider.
"""
from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

import httpx

from agt.models import NormalizedPaper
from agt.tools.capabilities import (
    ProviderHealth,
    ProviderStatus,
    SearchProviderCapabilities,
)


@runtime_checkable
class SearchProviderProtocol(Protocol):
    """All search backends implement this. Distinct from LLMProvider."""

    def capabilities(self) -> SearchProviderCapabilities: ...
    def health(self) -> ProviderHealth: ...

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]: ...


class SearchProviderBase:
    """Convenience base with retry and health bookkeeping.

    Subclasses implement _search_impl and set capabilities_ at class level.
    Use self._client for HTTP calls.
    """

    capabilities_: SearchProviderCapabilities  # subclass sets this

    def __init__(
        self,
        *,
        mailto: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._mailto = mailto
        self._health = ProviderHealth()
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": self._user_agent(),
                "Accept": "application/json",
            },
        )

    def _user_agent(self) -> str:
        ua = "SciAgent/0.1 (https://github.com/AdamKrysztopa/sciagent)"
        if self._mailto:
            ua += f" mailto:{self._mailto}"
        return ua

    def capabilities(self) -> SearchProviderCapabilities:
        return self.capabilities_

    def health(self) -> ProviderHealth:
        return self._health

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]:
        try:
            results = await self._search_impl(
                query, limit=limit, author=author,
                year_from=year_from, year_to=year_to,
            )
        except httpx.HTTPStatusError as e:
            self._record_failure(e)
            raise
        except httpx.HTTPError as e:
            self._record_failure(e)
            raise
        else:
            self._record_success()
            return results

    def _record_success(self) -> None:
        self._health.status = ProviderStatus.AVAILABLE
        self._health.last_ok_at = time.time()
        self._health.consecutive_failures = 0
        self._health.reason = ""

    def _record_failure(self, exc: Exception) -> None:
        self._health.last_error_at = time.time()
        self._health.consecutive_failures += 1
        self._health.reason = f"{type(exc).__name__}: {exc}"
        if self._health.status != ProviderStatus.RATE_LIMITED:
            self._health.status = ProviderStatus.FAILED

    async def _search_impl(
        self,
        query: str,
        *,
        limit: int,
        author: str | None,
        year_from: int | None,
        year_to: int | None,
    ) -> list[NormalizedPaper]:
        raise NotImplementedError

    async def aclose(self) -> None:
        await self._client.aclose()
```

**Acceptance:** `GET /providers` returns capability + health per provider. `SearchProviderProtocol` passes `isinstance` checks. `SourceCapability` in `SearchPlan.source_policy` references `SearchProviderCapabilities`. `pyright` 0, all tests green.

---

### P8.2 — Baseline Providers Complete _(2 days)_

> Source: reviewer Phase 2 + my earlier P8.2. DOAJ is new; others need audit + `SearchProviderBase` adaptation.

**Goal:** The six keyless baseline providers return useful results on a fresh clone with no
secrets set. Each fails closed (`ProviderStatus.FAILED`), never crashing the run.

**What already exists:** `OpenAlexClient`, `CrossrefClient`, `ArxivClient`, `EuropePMCClient`,
`PubMedClient`, `SemanticScholarClient` all exist and return `list[NormalizedPaper]`. They
use per-client retry logic. `_RetrievalProvider` dataclass in `search_papers.py` handles
skip/enable decisions. DOAJ does **not** exist.

| ID     | Story                                                                                                                                                                                                                                                                                                                                      | Effort |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ |
| P8.2-A | **DOAJ provider** — `src/agt/tools/doaj.py`: `DOAJClient` subclassing `SearchProviderBase` with `capabilities_ = DOAJ_CAPS`. `GET https://doaj.org/api/v3/search/articles/{query}?pageSize=N`. Parse into `NormalizedPaper` (url = OA link, open_access=True always). Wire into `_build_retrieval_registry` as keyless primary.            | ~0.5d  |
| P8.2-B | **Provider audit** — verify each existing client: (1) sets `User-Agent` with `AGT_MAILTO` from settings; (2) has tenacity retry on 5xx; (3) surfaces 429 as `ProviderStatus.RATE_LIMITED` rather than crashing; (4) returns empty list on empty API response, not raising. Fix gaps.                                                       | ~0.5d  |
| P8.2-C | **`SearchRunResult`** — new `@dataclass` in `src/agt/tools/search_papers.py`: `per_provider: dict[str, list[NormalizedPaper]]`, `errors: dict[str, str]`, `health: dict[str, ProviderHealth]`. The parallel fan-out (`asyncio.gather(return_exceptions=True)`) already exists in `_fetch_sources`; wrap its output into `SearchRunResult`. | ~0.25d |
| P8.2-D | **`SearchMetadata.baseline_mode: bool`** — set `True` when `source_states` contains no `"queried"` entries from key-gated providers. Surfaces in `/status/{id}` response and as a "Baseline (6 sources)" badge in `SearchCoveragePanel.tsx`.                                                                                               | ~0.25d |
| P8.2-E | **Baseline regression test** — `tests/test_baseline_providers.py`: using `_env_file=None`, confirm all six baseline providers produce a non-empty `_RetrievalProvider` entry with `skip_reason=None`.                                                                                                                                      | ~0.25d |

**DOAJ provider sketch:**

```python
"""DOAJ v3 API wrapper returning NormalizedPaper models."""
from __future__ import annotations

from agt.models import NormalizedPaper
from agt.tools.capabilities import DOAJ_CAPS
from agt.tools.provider_base import SearchProviderBase

DOAJ_SEARCH = "https://doaj.org/api/v3/search/articles/"


class DOAJResponseError(RuntimeError):
    """Raised when DOAJ payload is malformed."""


class DOAJClient(SearchProviderBase):
    capabilities_ = DOAJ_CAPS

    async def _search_impl(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]:
        params: dict[str, str | int] = {"pageSize": min(limit, 100)}
        if year_from or year_to:
            yr_f = year_from or 1900
            yr_t = year_to or 2100
            params["query.bibjson.year"] = f"[{yr_f} TO {yr_t}]"

        r = await self._client.get(f"{DOAJ_SEARCH}{query}", params=params)
        r.raise_for_status()
        data: object = r.json()
        if not isinstance(data, dict):
            raise DOAJResponseError("DOAJ response is not a dict")
        results = data.get("results") or []
        papers: list[NormalizedPaper] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            bib = item.get("bibjson") or {}
            title = (bib.get("title") or "").strip()
            if not title:
                continue
            authors = [
                a.get("name", "")
                for a in (bib.get("author") or [])
                if isinstance(a, dict) and a.get("name")
            ]
            year_raw = (bib.get("year") or "").strip()
            year = int(year_raw) if year_raw.isdigit() else None
            doi: str | None = None
            for id_entry in bib.get("identifier") or []:
                if isinstance(id_entry, dict) and id_entry.get("type") == "doi":
                    doi = (id_entry.get("id") or "").strip() or None
                    break
            journal = bib.get("journal") or {}
            venue = (journal.get("title") or "").strip() or None
            link_url: str | None = None
            for lnk in item.get("link") or []:
                if isinstance(lnk, dict) and lnk.get("type") == "fulltext":
                    link_url = (lnk.get("url") or "").strip() or None
                    break
            papers.append(NormalizedPaper(
                title=title,
                abstract=(bib.get("abstract") or "").strip() or None,
                authors=authors,
                doi=doi,
                year=year,
                venue=venue,
                url=link_url,
                open_access=True,   # DOAJ only indexes OA journals
                source="doaj",
            ))
        return papers
```

**Acceptance:** `uv run pytest -q --vcr-record=none` green. DOAJ appears in `_build_retrieval_registry` as keyless primary. `SearchMetadata.baseline_mode` present in API response. Baseline regression test confirms 6 providers enabled with no keys.

---

### P8.3 — `NormalizedAuthor` + `ProvenanceField` Models _(1 day)_

> Source: reviewer Phase 3, corrected to Pydantic v2 (not dataclass) to match existing `models.py`.

**Goal:** Authors are first-class objects — searchable, mergeable, with ORCID/OpenAlex IDs.
Every field on a merged `NormalizedPaper` is traceable to a provider.

**What already exists:** `NormalizedPaper.authors: list[str]` (plain strings). No
`NormalizedAuthor` model exists anywhere in the codebase. No `ProvenanceField` model exists.
`AgentState["papers"]` is `list[dict[str, Any]]` serialized via `_serialize_papers` /
`_deserialize_papers` in `workflow.py` — both need updating for new fields.

| ID     | Story                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Effort |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.3-A | **`NormalizedAuthor` model** — add to `src/agt/models.py`: `NormalizedAuthor(BaseModel)` with `name: str`, `family: str \| None`, `given: str \| None`, `orcid: str \| None`, `openalex_id: str \| None`, `s2_author_id: str \| None`, `affiliation: str \| None`, `source: str = ""`. Add `normalized_last()` method.                                                                                                                                                                                                                                                                    | ~0.25d |
| P8.3-B | **`ProvenanceField` model** — add to `src/agt/models.py`: `ProvenanceField(BaseModel)` with `provider: str`, `raw: object = None`, `note: str \| None = None`.                                                                                                                                                                                                                                                                                                                                                                                                                            | ~0.1d  |
| P8.3-C | **Extend `NormalizedPaper`** — add to `NormalizedPaper`: `authors: list[NormalizedAuthor]` (replaces `list[str]`); `oa_url: str \| None` (explicit OA URL, separate from general `url`); `references: list[str]` (DOI/ID list); `external_ids: dict[str, str]` (provider IDs, e.g. `{"openalex": "W123"}`); `missing_reasons: dict[str, str]`; `sources: list[str]` (all contributing providers after merge, vs singular `source`); `provenance: dict[str, ProvenanceField]`. All default to empty. Mark `authors` migration-safe (accept `list[str \| NormalizedAuthor]` via validator). | ~0.5d  |
| P8.3-D | **Update all providers** — migrate each existing provider's `_normalize_item` / `_parse` to emit `list[NormalizedAuthor]` instead of `list[str]`. OpenAlex has ORCID + IDs; Crossref has family/given; arXiv is name-only (use `xml.etree.ElementTree`, already the pattern in `arxiv_api.py` — do not add feedparser); Europe PMC has affiliations.                                                                                                                                                                                                                                      | ~0.5d  |

**`src/agt/models.py` additions (corrected):**

```python
class NormalizedAuthor(BaseModel):
    """Structured author record with optional cross-provider identifiers."""
    name: str                     # display form, e.g. "Jane Q. Doe"
    family: str | None = None
    given: str | None = None
    orcid: str | None = None
    openalex_id: str | None = None
    s2_author_id: str | None = None
    affiliation: str | None = None
    source: str = ""              # provider that supplied this record

    def normalized_last(self) -> str:
        last = self.family or (self.name.split()[-1] if self.name else "")
        return last.lower().strip()


class ProvenanceField(BaseModel):
    """Records which provider supplied a value and what the raw form was."""
    provider: str
    raw: object = None
    note: str | None = None
```

**Acceptance:** `NormalizedPaper.authors` accepts both `list[str]` (backward compat) and
`list[NormalizedAuthor]`. `_serialize_papers` / `_deserialize_papers` round-trip correctly.
`pyright` 0. All 386+ tests green.

---

### P8.4 — Field-Level Merge with Provenance _(1–2 days)_

> Source: reviewer Phase 4, corrected to use `NormalizedPaper`, `NormalizedAuthor`, Pydantic v2.

**Goal:** Merge results from multiple providers without losing the audit trail. Every selected
value on a merged record knows which provider supplied it. Conflicts are stored, not hidden.

**What already exists:** `rank_and_index_papers` in `src/agt/tools/ranking.py` deduplicates by
DOI + title similarity. The dedup logic is ad-hoc (not field-level). No provenance is tracked.

| ID     | Story                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Effort |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.4-A | **`src/agt/tools/merge.py`** — `cluster(papers: list[NormalizedPaper]) -> list[list[NormalizedPaper]]`: DOI-exact first pass, then normalized-title + year + shared-author-last second pass. `merge_cluster(cluster) -> NormalizedPaper`: field-selection rules below. `merge(papers) -> list[NormalizedPaper]`: calls both.                                                                                                                                              | ~1d    |
| P8.4-B | **Field-selection rules** — DOI: first non-null, record conflict if multiple distinct values. Title: longest non-truncated; conflict if Jaccard < 0.8 vs runner-up. Year: agreement check; take highest-priority provider on disagreement. Abstract: longest. Citation count: max. `url` / `oa_url`: first non-null preferring `FieldSupport.FULL` providers. Venue: first non-null from `FULL` provider. Authors: union by `(orcid OR normalized_last + given_initial)`. | ~0.5d  |
| P8.4-C | **`FieldConflict` model + `NormalizedPaper.conflicts`** — add `FieldConflict(BaseModel)` to `models.py`: `field: str`, `values: list[tuple[str, object]]`. Add `conflicts: list[FieldConflict]` to `NormalizedPaper`. Prefer this over the `external_ids["_conflicts"]` string-blob approach suggested in the review.                                                                                                                                                     | ~0.25d |
| P8.4-D | **Wire into `run_search_phase`** — in `src/agt/graph/workflow.py`: after existing `search_papers()` call, pass the flat paper list through `merge.merge()`. The existing `rank_and_index_papers` dedup can be simplified to skip its own title-match logic once merge handles it.                                                                                                                                                                                         | ~0.25d |

**`src/agt/tools/merge.py` (corrected):**

```python
"""Field-level merge with provenance preservation.

When in doubt: keep both values and flag a conflict rather than
silently picking one. The Zotero sidebar surfaces conflicts on approve.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from agt.models import FieldConflict, NormalizedAuthor, NormalizedPaper, ProvenanceField

PROVIDER_PRIORITY = [
    "crossref",       # authoritative for DOI/title/year
    "openalex",
    "europe_pmc",
    "pubmed",
    "doaj",
    "semantic_scholar",
    "arxiv",
    "core",
    "base",
]

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def _priority(name: str) -> int:
    try:
        return PROVIDER_PRIORITY.index(name)
    except ValueError:
        return 99


def _norm_title(t: str) -> str:
    return _WS.sub(" ", _PUNCT.sub(" ", t.lower())).strip()


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def cluster(papers: list[NormalizedPaper]) -> list[list[NormalizedPaper]]:
    by_doi: dict[str, list[NormalizedPaper]] = defaultdict(list)
    no_doi: list[NormalizedPaper] = []
    for p in papers:
        (by_doi[p.doi].append(p) if p.doi else no_doi.append(p))

    groups: list[list[NormalizedPaper]] = list(by_doi.values())

    while no_doi:
        seed = no_doi.pop()
        bucket = [seed]
        seed_t = _norm_title(seed.title)
        seed_authors = {a.normalized_last() for a in seed.authors
                        if isinstance(a, NormalizedAuthor)}
        remaining: list[NormalizedPaper] = []
        for p in no_doi:
            if _jaccard(seed_t, _norm_title(p.title)) < 0.85:
                remaining.append(p)
                continue
            if seed.year and p.year and abs(seed.year - p.year) > 1:
                remaining.append(p)
                continue
            p_authors = {a.normalized_last() for a in p.authors
                         if isinstance(a, NormalizedAuthor)}
            if seed_authors and p_authors and not (seed_authors & p_authors):
                remaining.append(p)
                continue
            bucket.append(p)
        groups.append(bucket)
        no_doi = remaining
    return groups


def merge_cluster(papers: list[NormalizedPaper]) -> NormalizedPaper:
    if len(papers) == 1:
        p = papers[0]
        return p.model_copy(update={"sources": [p.source] if p.source else []})

    papers = sorted(papers, key=lambda p: _priority(p.source))
    out = NormalizedPaper(title="")
    conflicts: list[FieldConflict] = []
    all_sources: list[str] = []

    # DOI
    dois = {p.doi: p.source for p in papers if p.doi}
    if dois:
        out = out.model_copy(update={"doi": next(iter(dois))})
        if len(dois) > 1:
            conflicts.append(FieldConflict(
                field="doi",
                values=[(src, d) for d, src in dois.items()],
            ))

    # Title — longest; conflict if Jaccard < 0.8
    titled = sorted([p for p in papers if p.title], key=lambda p: len(p.title), reverse=True)
    if titled:
        out = out.model_copy(update={"title": titled[0].title})
        for other in titled[1:]:
            if _jaccard(_norm_title(out.title), _norm_title(other.title)) < 0.8:
                conflicts.append(FieldConflict(
                    field="title",
                    values=[(titled[0].source, out.title), (other.source, other.title)],
                ))

    # Year — pick highest-priority; conflict on disagreement
    years = [(p.year, p.source) for p in papers if p.year is not None]
    unique_years = {y for y, _ in years}
    if unique_years:
        out = out.model_copy(update={"year": years[0][0]})
        if len(unique_years) > 1:
            conflicts.append(FieldConflict(field="year", values=list(years)))

    # Abstract — longest
    abstracts = sorted([p for p in papers if p.abstract],
                       key=lambda p: len(p.abstract or ""), reverse=True)
    if abstracts:
        out = out.model_copy(update={"abstract": abstracts[0].abstract})

    # Citation count — max
    cites = [(p.citation_count, p.source) for p in papers if p.citation_count]
    if cites:
        out = out.model_copy(update={"citation_count": max(c for c, _ in cites)})

    # Venue / url / oa_url — first non-null by priority
    for attr in ("venue", "url", "oa_url"):
        val = next((getattr(p, attr) for p in papers if getattr(p, attr)), None)
        if val is not None:
            out = out.model_copy(update={attr: val})

    # Authors — union by ORCID then normalized_last + given_initial
    seen: dict[str, NormalizedAuthor] = {}
    for p in papers:
        for a in p.authors:
            if isinstance(a, str):
                key = a.lower().strip()
                if key not in seen:
                    seen[key] = NormalizedAuthor(name=a)
                continue
            key = a.orcid or f"{a.normalized_last()}|{(a.given or '')[:1].lower()}"
            if key in seen:
                existing = seen[key]
                existing.orcid = existing.orcid or a.orcid
                existing.openalex_id = existing.openalex_id or a.openalex_id
                existing.s2_author_id = existing.s2_author_id or a.s2_author_id
                existing.affiliation = existing.affiliation or a.affiliation
            else:
                seen[key] = a
    out = out.model_copy(update={"authors": list(seen.values())})

    # External IDs + references — union
    ext: dict[str, str] = {}
    refs: list[str] = []
    for p in papers:
        ext.update(p.external_ids)
        for ref in p.references:
            if ref not in refs:
                refs.append(ref)
        if p.source:
            all_sources.append(p.source)

    out = out.model_copy(update={
        "external_ids": ext,
        "references": refs,
        "sources": sorted(set(all_sources)),
        "conflicts": conflicts,
        "source": papers[0].source,  # primary source
    })
    return out


def merge(papers: list[NormalizedPaper]) -> list[NormalizedPaper]:
    return [merge_cluster(c) for c in cluster(papers)]
```

**Acceptance:** `tests/test_merge.py` covers DOI dedup across 3 providers, year conflict,
title Jaccard < 0.8 flag, author union by ORCID. `FieldConflict` surfaces in `NormalizedPaper.conflicts`.
`pyright` 0. All existing tests green.

---

### P8.5 — Search Depth Formalization _(½ day)_

> Source: reviewer Phase 5. The depth knob (`AGT_SEARCH_DEPTH`) is **already done** (OPN-14).
> This phase adds formal `DEPTH_PROFILES` provider-per-depth selection on top of the existing
> `_depth_max_pages` page-count logic.

**What already exists:** `settings.search_depth: Literal["quick", "balanced", "deep"]`,
`_depth_max_pages()` returning page-count multiplier, `RunRequest.search_depth`. The depth
chip row is in `SourcePresets.tsx`.

| ID     | Story                                                                                                                                                                                                                                                                                                                                                                                                 | Effort |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.5-A | **`DEPTH_PROFILES` dict** — in `src/agt/tools/search_papers.py`, add `DEPTH_PROFILES: dict[Literal["quick","balanced","deep"], dict]` mapping depth to `{"providers": list[str], "limit_per_provider": int, "expand_refs": bool, "timeout": float}`. `select_providers_for_depth()` function takes the registry and depth, returns `list[_RetrievalProvider]`. Wire into `_build_retrieval_registry`. | ~0.25d |
| P8.5-B | **Plan preview shows depth + provider list** — `SearchCoveragePanel.tsx` shows which providers will be queried at the selected depth before the search starts (from `/capabilities` response).                                                                                                                                                                                                        | ~0.25d |

**Depth profiles:**

| Aspect              | Quick           | Balanced                             | Deep                                          |
| ------------------- | --------------- | ------------------------------------ | --------------------------------------------- |
| Providers           | OpenAlex, arXiv | + Crossref, Europe PMC, DOAJ, PubMed | + Semantic Scholar, CORE, BASE, OpenCitations |
| Results / provider  | 10              | 25                                   | 50                                            |
| Reference expansion | off             | off                                  | on (Phase 5b, optional)                       |
| Per-query timeout   | 5 s             | 15 s                                 | 30 s                                          |

**Acceptance:** `DEPTH_PROFILES` exists and `select_providers_for_depth` is importable. Sidebar shows provider list per depth. `pyright` 0.

---

### P8.6 — Missing Metadata Explanations _(½ day)_

> Source: reviewer Phase 6, corrected to use `NormalizedPaper`, `ProviderField`, `FieldSupport`, `ProviderStatus`.

**Goal:** Never leave the user wondering why a field is empty. `NormalizedPaper.missing_reasons`
explains every absent field after the merge.

| ID     | Story                                                                                                                                                                                                                                   | Effort |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.6-A | **`src/agt/tools/explain_missing.py`** — `annotate_missing(paper, *, queried, health, profile_skipped)` fills `paper.missing_reasons` for every null field using the five reason codes below. Called after merge in `run_search_phase`. | ~0.25d |
| P8.6-B | **Result card tooltip** — `ResultsList.tsx`: small "i" icon next to empty fields; `missing_reasons[field]` shown on hover. Maps reason codes to human-readable strings.                                                                 | ~0.25d |

**Reason codes:**

| Code                                    | Meaning                                                          |
| --------------------------------------- | ---------------------------------------------------------------- |
| `provider_did_not_return`               | Capable provider was queried but returned nothing for this field |
| `not_supported_by_any_queried_provider` | No queried provider declares support for this field              |
| `missing_key`                           | Only key-gated providers support this field; key not set         |
| `provider_failed`                       | Capable provider errored or was rate-limited                     |
| `not_requested_at_depth`                | Current depth profile skips this enrichment step                 |

**`src/agt/tools/explain_missing.py` (corrected):**

```python
from __future__ import annotations

from agt.models import NormalizedPaper
from agt.tools.capabilities import (
    FieldSupport,
    ProviderField,
    ProviderHealth,
    ProviderStatus,
    SearchProviderCapabilities,
)

FIELD_TO_ATTR: dict[ProviderField, str] = {
    ProviderField.TITLE: "title",
    ProviderField.ABSTRACT: "abstract",
    ProviderField.AUTHORS: "authors",
    ProviderField.DOI: "doi",
    ProviderField.YEAR: "year",
    ProviderField.VENUE: "venue",
    ProviderField.CITATION_COUNT: "citation_count",
    ProviderField.OA_URL: "oa_url",
    ProviderField.REFERENCES: "references",
}


def annotate_missing(
    paper: NormalizedPaper,
    *,
    queried: list[SearchProviderCapabilities],
    health: dict[str, ProviderHealth],
    profile_skipped: set[ProviderField] | None = None,
) -> None:
    skipped = profile_skipped or set()
    reasons: dict[str, str] = {}

    for field, attr in FIELD_TO_ATTR.items():
        value = getattr(paper, attr)
        present = bool(value) if not isinstance(value, int) else value > 0
        if present:
            continue

        if field in skipped:
            reasons[attr] = "not_requested_at_depth"
            continue

        any_shallow = any(p.supports(field) != FieldSupport.NONE for p in queried)
        if not any_shallow:
            reasons[attr] = "not_supported_by_any_queried_provider"
            continue

        capable = [p for p in queried if p.supports(field) != FieldSupport.NONE]
        statuses = {p.name: health.get(p.name) for p in capable}
        if any(s and s.status == ProviderStatus.MISSING_KEY
               for s in statuses.values()):
            reasons[attr] = "missing_key"
        elif any(s and s.status in (ProviderStatus.FAILED, ProviderStatus.RATE_LIMITED)
                 for s in statuses.values()):
            reasons[attr] = "provider_failed"
        else:
            reasons[attr] = "provider_did_not_return"

    paper.missing_reasons.update(reasons)
```

**Acceptance:** `tests/test_explain_missing.py` exercises all five reason-code branches. Sidebar tooltip renders for null fields. `pyright` 0.

---

### P8.7 — Wire into `AgentState` + Zotero Sidebar _(1 day)_

> Source: reviewer Phase 7, corrected to use `AgentState` (TypedDict), `run_search_phase` in `workflow.py`.

**Goal:** `run_search_phase` uses merge + explain_missing. Zotero sidebar shows provenance
chips, missing-field tooltips, and conflict warnings.

**What already exists:** `run_search_phase(state: AgentState) -> AgentState` in
`src/agt/graph/workflow.py`. It calls `search_papers()` and stores results via
`_serialize_papers()` into `state["papers"]`. `AgentState` is a TypedDict — no `.with_results()`
method; updates are dict spreads.

| ID     | Story                                                                                                                                                                                                                                                                                                                                                  | Effort |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ |
| P8.7-A | **Merge in `run_search_phase`** — after the `search_papers()` call, pass the flat paper list through `merge.merge()`. Pass `SearchRunResult.health` and `SearchProviderCapabilities` to `annotate_missing` for each merged paper. Return updated state via `{**state, "papers": _serialize_papers(merged), "search_metadata": metadata.model_dump()}`. | ~0.5d  |
| P8.7-B | **Provenance chips in `ResultsList.tsx`** — per result card, show `sources` list as small provider chips (e.g. `openalex • crossref`).                                                                                                                                                                                                                 | ~0.25d |
| P8.7-C | **Conflict warnings** — if `paper.conflicts` is non-empty, show a red dot on the result card. In the approval dialog, display each conflict and require explicit per-conflict confirmation before `NativeWrite`.                                                                                                                                       | ~0.25d |
| P8.7-D | **`/providers` surface in sidebar** — fetch `GET /providers` once at startup; populate `SearchCoveragePanel` with capability matrix (replaces the current hardcoded source list).                                                                                                                                                                      | ~0.25d |

**Graph node pseudocode (corrected):**

```python
# src/agt/graph/workflow.py — in run_search_phase
from agt.tools.merge import merge as merge_papers
from agt.tools.explain_missing import annotate_missing
from agt.tools.search_papers import DEPTH_PROFILES, select_providers_for_depth

async def run_search_phase(state: AgentState, ...) -> AgentState:
    # ... existing search_papers() call ...
    papers, search_metadata = await search_papers(query, ...)

    # New: merge + annotate
    merged = merge_papers(papers)
    depth = search_metadata.search_plan.hard_filters  # or state["search_plan"]["depth"]
    # annotate each merged paper
    for paper in merged:
        annotate_missing(
            paper,
            queried=queried_caps,
            health=run_result.health,
            profile_skipped=profile_skipped_fields,
        )

    return {
        **state,
        "papers": _serialize_papers(merged),
        "search_metadata": search_metadata.model_dump(),
    }
```

**Acceptance:** Provenance chips visible in Zotero sidebar. Conflict red-dot appears for papers with `conflicts`. Approval dialog shows conflicts. `AgentState` TypedDict passes `pyright`. All gates green.

---

### P8.8 — Author-Aware Search _(2 days)_

> Source: my earlier P8.5. Depends on P8.3 (`NormalizedAuthor`).

**Goal:** Queries like "papers by Karpathy 2023" produce results filtered to the resolved
author. Author chips in result cards trigger scoped searches.

| ID     | Story                                                                                                                                                                                                                                   | Effort |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.8-A | **Author resolver** — `src/agt/tools/author_resolver.py`: `resolve_author(name, settings) -> list[NormalizedAuthor]` queries OpenAlex `/authors?search=` and Semantic Scholar `/author/search`, deduplicates by ORCID.                  | ~0.75d |
| P8.8-B | **`HardFilters.author_ids: list[str] \| None`** — add to `HardFilters` in `models.py`. LLM planner detects author-intent queries and populates it. `apply_query_constraints` enforces it post-merge via `NormalizedAuthor` ID matching. | ~0.5d  |
| P8.8-C | **Author chips in `ResultsList.tsx`** — render authors with `openalex_id` or `s2_author_id` as tappable chips; tap triggers a new `HardFilters(author_ids=[id])` search.                                                                | ~0.5d  |

**Acceptance:** Query "papers by Geoffrey Hinton 2022–2024" returns results with Hinton's
resolved IDs. Author chips appear and trigger scoped search. `HardFilters.author_ids`
round-trips through the API. `pyright` 0.

---

### P8.9 — Citation Graph Retrieval _(1.5 days)_

> Source: my earlier P8.6. Depends on P8.3 and P8.7.

**Goal:** "Papers citing X" and "papers cited by X" as first-class retrieval modes.

| ID     | Story                                                                                                                                                                                                                                                                                                                                                                | Effort |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.9-A | **`SearchPlan.seed_dois: list[str] \| None`** — LLM planner sets this when query contains DOIs or identifies a seed paper.                                                                                                                                                                                                                                           | ~0.25d |
| P8.9-B | **Citation expansion tool** — `src/agt/tools/citation_graph.py`: `expand_citations(seed_dois, direction: Literal["citing","cited_by"], settings) -> list[NormalizedPaper]` fans out to `OpenCitationsClient` (already exists) + Semantic Scholar `/paper/{id}/citations`. Tags `NormalizedPaper.source` as `"citation_graph_citing"` or `"citation_graph_cited_by"`. | ~1d    |
| P8.9-C | **Directional badge in `ResultsList.tsx`** — small "↑ cites this" / "↓ cited by this" badge when `source` is a citation-graph value.                                                                                                                                                                                                                                 | ~0.25d |

**Acceptance:** Query "papers citing Attention Is All You Need" returns citation-expanded results. Badge visible. `SearchCoveragePanel` shows `citation_graph` as a source. All gates pass.

---

### P8.10 — BYOK Provider Onboarding _(2 days)_

> Source: my earlier P8.3. Depends on P8.1 and P8.2.

**Goal:** User can enter a provider key in the sidebar, test it, and have it persist across
restarts without editing `.env`.

| ID      | Story                                                                                                                                                                                                                                                                                                        | Effort |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ |
| P8.10-A | **`POST /keys/validate`** — accept `{ provider: "core" \| "dimensions" \| "serpapi" \| "semantic_scholar", key: string }`, probe the provider with a lightweight query, return `{ valid: bool, provider_name: str, error?: str }`. Key is never persisted server-side.                                       | ~0.5d  |
| P8.10-B | **Key entry panel in `ConfigPanel.tsx`** — expandable section under "Search Sources" listing key-gated providers with their `key_upgrade_hint` from `/capabilities`. Each has an input + "Test key" button wired to `/keys/validate`. On success, updates `preferenceStore` and shows "Restart to activate". | ~1d    |
| P8.10-C | **Preference store bridging** — extend `preferenceStore` (already handles LLM keys via `collectProviderEnv`) to store `AGT_CORE_API_KEY`, `AGT_DIMENSIONS_KEY`, `AGT_SERPAPI_KEY`, `AGT_SEMANTIC_SCHOLAR_API_KEY` in Zotero prefs so they survive restart without an `.env` file.                            | ~0.5d  |

**Acceptance:** User enters CORE key in sidebar → "Test key" → green → restart → CORE appears as active in `SearchCoveragePanel`. Key never appears in server logs. All gates pass.

---

### P8.11 — Provider Expansion Protocol _(½ day)_

> Source: my earlier P8.7. Depends on P8.1.

**Goal:** Adding a new source in the future follows a documented, checklistable process.

| ID      | Story                                                                                                                                                                                                                                                                                                                                                                                                                                | Effort |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ |
| P8.11-A | **`docs/providers.md` checklist** — 7-step contract: (1) `SearchProviderProtocol` impl; (2) `SearchProviderCapabilities` entry in `capabilities.py` with `requires_key`/`key_env_var`/`key_upgrade_hint`; (3) VCR cassette fixtures; (4) `_build_retrieval_registry` entry with `skip_reason="no_key"` guard; (5) `/providers` payload update; (6) `SearchCoveragePanel` render path; (7) benchmark slot if must-find anchors exist. | ~0.25d |
| P8.11-B | **Provider scaffold script** — `scripts/new_provider.py`: generates boilerplate (protocol stub, capability entry, cassette dir, test file) from `--name` and `--key-env-var`. Output passes `pyright`.                                                                                                                                                                                                                               | ~0.5d  |

**Acceptance:** `docs/providers.md` exists. `python scripts/new_provider.py --name MySource --key-env-var MY_KEY` produces compilable stubs. `pyright` 0 on generated stubs.

---

### P8.12 — Tests + CI _(½ day)_

> Source: reviewer Phase 8.

| ID      | Story                                                                                                                                                                                                            | Effort |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.12-A | **VCR cassettes** — 4 cassettes per provider × {happy, empty, 5xx, 429} = 44 total (11 providers). Must pass `--vcr-record=none`.                                                                                | ~0.25d |
| P8.12-B | **`tests/test_merge.py`** — DOI dedup across 3 providers; year conflict; title Jaccard < 0.8; author union by ORCID; `FieldConflict` populated.                                                                  | ~0.25d |
| P8.12-C | **`tests/test_capabilities.py`** — every concrete provider declares a non-empty `SearchProviderCapabilities`; round-trip through `/providers` JSON.                                                              | ~0.1d  |
| P8.12-D | **`tests/test_explain_missing.py`** — each of the five reason-code branches exercised.                                                                                                                           | ~0.1d  |
| P8.12-E | **`tests/test_search_orchestrator.py`** — one provider raising does not abort the run; `SearchRunResult.errors` is populated.                                                                                    | ~0.1d  |
| P8.12-F | **Zero-key smoke test** — `@pytest.mark.live_api` test: bootstraps with `_env_file=None` (zero env vars), runs a search, asserts ≥ 1 provider returns ≥ 1 result. Skipped in offline CI; must pass in live mode. | ~0.1d  |
| P8.12-G | **Regression gate** — `test_p8_no_regression`: runs the 22-query benchmark panel with `AGT_SEARCH_DEPTH=balanced`, asserts `pass_rate >= 19/22`. Fails CI on any regression.                                     | ~0.25d |

---

### P8.13 — Settings Contract _(½ day)_

> Source: reviewer Phase 9, corrected to `AGT_*` naming convention.

| ID      | Story                                                                                                                                                                                                                                                                                                                     | Effort |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.13-A | **New config fields** — add to `src/agt/config.py` with strict pydantic-settings typing: `agt_mailto: str \| None` (polite pool for OpenAlex/Crossref `User-Agent`); `agt_providers_disabled: list[str]` (comma-separated, default empty). `AGT_SEMANTIC_SCHOLAR_API_KEY` already aliases via `semantic_scholar_api_key`. | ~0.25d |
| P8.13-B | **Disabled-by-config state** — providers in `agt_providers_disabled` get `ProviderStatus.DISABLED` with reason `"disabled in config"`. Surface in `/providers` response.                                                                                                                                                  | ~0.25d |
| P8.13-C | **`.env.example` update** — add `AGT_MAILTO`, `AGT_PROVIDERS_DISABLED`; document that `AGT_CORE_API_KEY`, `AGT_DIMENSIONS_KEY`, `AGT_SERPAPI_KEY`, `AGT_SEMANTIC_SCHOLAR_API_KEY` unlock premium/stable access.                                                                                                           | ~0.1d  |

**Acceptance:** Settings pass `pyright`. `extra='forbid'` still enforced. Disabled providers show `DISABLED` in `/providers`. `.env.example` is current.

---

### P8.14 — P8 Benchmark Slice _(½ day)_

> Source: my earlier P8.8.

| ID      | Story                                                                                                                                                                                                                                                                                        | Effort |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P8.14-A | **New query panel** — add 6 queries to the benchmark: 2 author-scoped (must-find specific papers by a named researcher), 2 citation-graph (must-find papers citing a well-known work), 2 DOAJ recall (papers likely in DOAJ but not in OpenAlex top results). Record as `m2.8-benchmark-v1`. | ~0.5d  |
| P8.14-B | **`docs/benchmark.md` update** — record P8 panel results, note which queries are new, confirm baseline 22-query pass rate is unchanged.                                                                                                                                                      | ~0.1d  |

---

## Execution Order

```
P8.0 ──▶ P8.1 ──▶ P8.2 ──▶ P8.4 ──▶ P8.7 ──▶ P8.12 ──▶ P8.14
               │              ▲
               └──▶ P8.3 ────┤
               └──▶ P8.5 ────┤
               └──▶ P8.6 ────┘
               └──▶ P8.13 (any time after P8.1)
               └──▶ P8.10 (any time after P8.1 + P8.2)

P8.3 ──▶ P8.8 ──▶ P8.9
P8.1 ──▶ P8.11
```

**Recommended linear order:** P8.0 → P8.1 → P8.2 → P8.3 → P8.4 → P8.5 → P8.6 → P8.7 → P8.8 → P8.9 → P8.10 → P8.11 → P8.12 → P8.13 → P8.14

---

## Open Items

| ID      | Story                                           | Effort | Status |
| ------- | ----------------------------------------------- | ------ | ------ |
| P8.0-A  | Provider inventory table                        | ~0.25d | ✅ done |
| P8.0-B  | Snapshot VCR tests                              | ~0.5d  | ✅ done |
| P8.0-C  | Cassette hygiene                                | ~0.25d | ✅ done |
| P8.1-A  | `capabilities.py` — capability model            | ~0.5d  | ✅ done |
| P8.1-B  | `provider_base.py` — protocol + base class      | ~0.5d  | ✅ done |
| P8.1-C  | `GET /providers` endpoint                       | ~0.25d | ✅ done |
| P8.1-D  | Sidebar BYOK hint chip                          | ~0.25d | ✅ done |
| P8.2-A  | DOAJ provider                                   | ~0.5d  | ✅ done |
| P8.2-B  | Provider audit (User-Agent, retry, 429)         | ~0.5d  | ✅ done |
| P8.2-C  | `SearchRunResult` dataclass                     | ~0.25d | ✅ done |
| P8.2-D  | `SearchMetadata.baseline_mode` + badge          | ~0.25d | ✅ done |
| P8.2-E  | Baseline regression test                        | ~0.25d | ✅ done |
| P8.3-A  | `NormalizedAuthor` Pydantic model               | ~0.25d | ✅ done |
| P8.3-B  | `ProvenanceField` Pydantic model                | ~0.1d  | ✅ done |
| P8.3-C  | Extend `NormalizedPaper` with new fields        | ~0.5d  | ✅ done |
| P8.3-D  | Update all providers to emit `NormalizedAuthor` | ~0.5d  | ✅ done |
| P8.4-A  | `src/agt/tools/merge.py`                        | ~1d    | ✅ done |
| P8.4-B  | Field-selection rules                           | ~0.5d  | ✅ done |
| P8.4-C  | `FieldConflict` model                           | ~0.25d | ✅ done |
| P8.4-D  | Wire merge into `run_search_phase`              | ~0.25d | ✅ done |
| P8.5-A  | `DEPTH_PROFILES` + `select_providers_for_depth` | ~0.25d | ✅ done |
| P8.5-B  | Plan preview in sidebar                         | ~0.25d | ✅ done |
| P8.6-A  | `src/agt/tools/explain_missing.py`              | ~0.25d | ✅ done |
| P8.6-B  | Result card missing-field tooltip               | ~0.25d | ✅ done |
| P8.7-A  | Merge in `run_search_phase`                     | ~0.5d  | ✅ done |
| P8.7-B  | Provenance chips in `ResultsList.tsx`           | ~0.25d | ✅ done |
| P8.7-C  | Conflict warnings in approval dialog            | ~0.25d | ✅ done |
| P8.7-D  | `/providers` in sidebar                         | ~0.25d | ✅ done |
| P8.8-A  | Author resolver tool                            | ~0.75d | ✅ done |
| P8.8-B  | `HardFilters.author_ids`                        | ~0.5d  | ✅ done |
| P8.8-C  | Author chips in `ResultsList.tsx`               | ~0.5d  | ✅ done |
| P8.9-A  | `SearchPlan.seed_dois`                          | ~0.25d | ✅ done |
| P8.9-B  | Citation expansion tool                         | ~1d    | ✅ done |
| P8.9-C  | Directional badge                               | ~0.25d | ✅ done |
| P8.10-A | `POST /keys/validate`                           | ~0.5d  | ✅ done |
| P8.10-B | Key entry panel in `ConfigPanel.tsx`            | ~1d    | ✅ done |
| P8.10-C | Preference store bridging                       | ~0.5d  | ✅ done |
| P8.11-A | `docs/providers.md` checklist                   | ~0.25d | ✅ done |
| P8.11-B | `scripts/new_provider.py` scaffold              | ~0.5d  | ✅ done |
| P8.12-A | VCR cassettes (44 total)                        | ~0.25d | ✅ done |
| P8.12-B | `test_merge.py`                                 | ~0.25d | ✅ done |
| P8.12-C | `test_capabilities.py`                          | ~0.1d  | ✅ done |
| P8.12-D | `test_explain_missing.py`                       | ~0.1d  | ✅ done |
| P8.12-E | `test_search_orchestrator.py`                   | ~0.1d  | ✅ done |
| P8.12-F | Zero-key smoke test                             | ~0.1d  | ✅ done |
| P8.12-G | Regression gate in CI                           | ~0.25d | ✅ done |
| P8.13-A | New config fields (`AGT_MAILTO`, etc.)          | ~0.25d | ✅ done |
| P8.13-B | Disabled-by-config state                        | ~0.25d | ✅ done |
| P8.13-C | `.env.example` update                           | ~0.1d  | ✅ done |
| P8.14-A | New 6-query benchmark panel                     | ~0.5d  | ✅ done |
| P8.14-B | `docs/benchmark.md` update                      | ~0.1d  | ✅ done |

**All P8 stories complete. 563 Python / 103 frontend tests green.**

---

## Out of Scope

- LLM ranking, embeddings, "chat with PDFs" — SciAgent's edge is the deterministic, auditable intake layer.
- Full-text fetching pipelines — OA URL is enough; Zotero handles attachments.
- Author disambiguation beyond ORCID + last-name + given-initial — belongs in a future "author entity resolution" phase.
- **CORE keyless endpoint** — CORE without an API key is too rate-limited to provide reliable
  coverage. The keyed CORE provider (activated via `AGT_CORE_API_KEY`) covers the open-access
  backfill use case. Keyless CORE OA-URL backfill is intentionally excluded; this decision should
  not be revisited without a concrete throughput benchmark showing it improves recall over the
  six keyless baseline providers.

---

## Done Milestones (Archive)

- [x] M1 — Foundation and Observability
- [x] M2 — Retrieval and Ranking Core
- [x] M2.5 — Retrieval Quality & Coverage Improvements
- [x] M2.6 — Optional Recommendation and Fallback Retrieval
- [x] M2.7 — Discovery Quality, Keyless Baseline, and Filters
- [x] M3 — Write Correctness and Idempotency
- [x] M4 — Approval-Gated Workflow and MVP Demo
- [x] M5 — Production v1 Hardening
- [x] M6 — Zotero Native Add-on (all ZAP-0 through ZAP-11 complete)
- [x] M6.1 — Main-Window-First Plugin MVP (shipped as 0.1.2)
- [x] M6.1-D — Approval/write flow hardening and PDF attachment status
- [x] P0 — Product Truth and Trust
- [x] P1 — Evidence Before Expansion _(closed at 19/22 by product decision; 2026-05-11)_
- [x] P2 — Differentiating Core _(sessions, cache, export, capability endpoint, source presets)_
- [x] P3 — Zotero-Native Value _(collection-aware search, PDF attach, Library Doctor, Gap Finder)_
      — **Note:** The "re-running the same search produces zero new items" guarantee is an AGT-11
      upsert invariant, enforced by `tests/test_zotero_upsert.py`, not an acceptance criterion of the
      collection-aware search story itself. These are distinct: P3 delivered the collection context
      signal; the idempotency contract is owned by the write-path, not the search-path.
- [x] P4 — Retention and Recurring Workflows _(watch list CRUD, watch rerun, WatchList UI)_
- [x] P5 — Local-First Hardening _(CORS + slowapi, Groq adapter, Docker fix + compose, MCP)_
- [x] P6 — Provider Extensibility and Zero-Terminal Install
- [x] P7 — Validate, Sign, and Publish _(all OPN-01 through OPN-17 done; 2026-05-12)_

---

## Product Thesis _(Last reviewed: 2026-05-13)_

SciAgent is a **deterministic, auditable, Zotero-native research intake and discovery system.**

Core differentiators (in priority order):

1. **Search plan first** — user sees constraints before results; hard filters are not weakened.
2. **Source-aware retrieval** — user sees which source returned which item.
3. **Explainable ranking** — user sees why each paper appeared.
4. **Approval-gated Zotero writes** — no silent library pollution.
5. **Duplicate-safe collection building** — rerunning a search does not create mess.
6. **Reproducible sessions** — a search can be re-run and diffed.
7. **Watch lists** — saved search plans monitor new literature over time.
8. **Collection-aware intelligence** — improves existing Zotero collections, not just web search.
9. **Keyless baseline** — strong retrieval with zero API keys; premium sources auto-activate.

## Planning Rules

1. Prioritize write safety and approval-gate integrity over feature breadth.
2. Treat AGT-11 as a release gate for any workflow that writes to Zotero.
3. Keep reproducibility and deterministic CI behavior as mandatory constraints.
4. **Keyless baseline is a hard guarantee.** Never degrade the six keyless providers to add paid-source support.
5. Treat deterministic query filters as a product contract. LLM rewriting may improve topic phrasing but must not weaken hard filters.
6. **Progressive unlock pattern:** When a user provides a provider key, that provider activates automatically via `_build_retrieval_registry`. No user action beyond setting the key is required.
7. **No LLM in the citation path** — citation graph expansion, merge, and provenance are deterministic code only.
8. Feature flags without benchmark evidence are technical debt. Measure, then promote, retain as experimental, or remove.
9. The canonical product path is the Zotero add-on. CLI/REST/Streamlit are developer interfaces.
10. **`BaseSearchClient` is the BASE SRU provider** — never use this name for a base class. Use `SearchProviderBase` and `SearchProviderProtocol` for the protocol layer.
11. **Benchmark gate after retrieval changes.** Any change to retrieval, ranking, merge, or
    `SearchPlan` enforcement requires re-running `examples/m2_7_benchmark.py` and recording the
    updated must-find recall in the same PR. This is the single safeguard protecting benchmark-
    validated trust gains from silent regression across P8 iterations.
