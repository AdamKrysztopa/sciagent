# SciAgent REST API Reference

The SciAgent backend exposes a FastAPI REST API as the contract behind the primary Zotero add-on
and as a developer/support interface for automation, debugging, and custom clients.

## Base URL

```text
http://localhost:8000
```

## Authentication

| Header            | Required | Description                                                     |
| ----------------- | -------- | --------------------------------------------------------------- |
| `X-AGT-API-Key`   | Optional | Backend API key (required if `AGT_BACKEND_API_KEY` set)         |
| `X-AGT-Client-ID` | Optional | Client identifier for per-user isolation (default: `anonymous`) |

When `AGT_BACKEND_API_KEY` is configured, all requests must include a matching `X-AGT-API-Key`
header. Workflows are scoped by `X-AGT-Client-ID` — each client can only access its own runs.

## Contract Versioning

The current API contract version is **`2026-05`**, returned by both `GET /health` and
`GET /capabilities` as `api_contract_version`. Clients should verify this value on startup
against `REQUIRED_API_CONTRACT_VERSION` in `contracts.ts`.

Stability rules:

1. Endpoint paths are stable within a contract version.
2. Required request fields will not be removed.
3. Optional fields may be added to requests and responses.
4. Breaking changes require a contract-version bump.

---

## Endpoints

### `GET /health`

Check system health, Zotero connectivity, and LLM provider status.

**Response:**

```json
{
  "ok": true,
  "message": "Library access verified",
  "preflight": {
    "ok": true,
    "can_read": true,
    "can_write": true,
    "key_valid": true,
    "message": "Library access verified"
  },
  "provider": "openai",
  "fallback_provider": null,
  "api_contract_version": "2026-05"
}
```

| Field                  | Type           | Description                                                      |
| ---------------------- | -------------- | ---------------------------------------------------------------- |
| `ok`                   | boolean        | Overall health — true only when Zotero write is accessible       |
| `message`              | string         | Human-readable status summary                                    |
| `preflight.ok`         | boolean        | Zotero library access functional                                 |
| `preflight.can_read`   | boolean        | Zotero read permission verified                                  |
| `preflight.can_write`  | boolean        | Zotero write permission verified                                 |
| `preflight.key_valid`  | boolean        | Zotero API key accepted                                          |
| `preflight.message`    | string         | Human-readable preflight detail                                  |
| `provider`             | string         | Active LLM provider name                                         |
| `fallback_provider`    | string \| null | Fallback LLM provider (null if not configured)                   |
| `api_contract_version` | string         | Backend contract version string (format: `YYYY-MM`)              |

---

### `GET /version`

Return the installed backend package version.

**Response:**

```json
{ "version": "0.1.0" }
```

---

### `GET /capabilities`

Return source policy, filter support, and provider availability. The Zotero add-on calls this
on startup to drive `SourceToggles`, the capability banner, and PDF import controls.

**Response:**

```json
{
  "api_contract_version": "2026-05",
  "source_policy": [
    {
      "name": "semantic_scholar",
      "tier": "primary",
      "enabled": true,
      "supports_year_filter": false,
      "supports_open_access_filter": false
    }
  ],
  "filter_support": {
    "year_filter": ["openalex", "pubmed"],
    "open_access_filter": ["openalex"]
  },
  "pdf_import_supported": true,
  "provider_availability": {
    "openai": true,
    "anthropic": false,
    "xai": false,
    "groq": false
  },
  "active_provider": "openai"
}
```

| Field                  | Type                          | Description                                          |
| ---------------------- | ----------------------------- | ---------------------------------------------------- |
| `api_contract_version` | string                        | Backend contract version                             |
| `source_policy`        | SourceCapability[]            | Per-source capabilities and tier                     |
| `filter_support`       | Record\<string, string[]\>    | Maps filter name to sources that enforce it API-side |
| `pdf_import_supported` | boolean                       | Backend supports PDF attachment via `pdf_url`        |
| `provider_availability`| Record\<string, boolean\>     | Whether each LLM provider has a key configured       |
| `active_provider`      | string                        | Currently active LLM provider                        |

---

### `POST /run`

Start a new search workflow. Blocks until papers are ready at the approval checkpoint.

**Request:**

```json
{
  "query": "retrieval augmented generation",
  "collection_name": "RAG Papers",
  "thread_id": null,
  "search_depth": "balanced",
  "filter_edit": null
}
```

| Field             | Type                            | Required | Description                                                      |
| ----------------- | ------------------------------- | -------- | ---------------------------------------------------------------- |
| `query`           | string                          | Yes      | Natural-language search query (min 1 character)                  |
| `collection_name` | string \| null                  | No       | Target Zotero collection (defaults to `AGT_ZOTERO_COLLECTION`)   |
| `thread_id`       | string \| null                  | No       | Optional thread ID for resumption continuity                     |
| `search_depth`    | `"quick"` \| `"balanced"` \| `"deep"` \| null | No | Retrieval depth; `null` uses the backend default (`balanced`) |
| `filter_edit`     | [FilterEditContract](#filteredit-contract) \| null | No | Pre-search filter overrides; `original_query` must equal `query` |

**Response:**

```json
{
  "run_id": "abc-123",
  "thread_id": "thread-456",
  "status": "awaiting_approval"
}
```

---

### `POST /resume`

Approve or reject the workflow at the approval checkpoint. On approval, writes selected papers
to Zotero (or returns them for native add-on write when `native_write=true`).

**Request (approve):**

```json
{
  "run_id": "abc-123",
  "approved": true,
  "collection_name": "RAG Papers",
  "selected_indices": [0, 2, 4],
  "native_write": false,
  "enable_pdf_imports": false
}
```

**Request (reject):**

```json
{
  "run_id": "abc-123",
  "approved": false
}
```

| Field               | Type           | Required | Description                                                                              |
| ------------------- | -------------- | -------- | ---------------------------------------------------------------------------------------- |
| `run_id`            | string         | Yes      | Workflow run ID from `/run`                                                              |
| `approved`          | boolean        | Yes      | `true` to write, `false` to discard                                                      |
| `collection_name`   | string \| null | No       | Override target collection name                                                          |
| `selected_indices`  | int[] \| null  | No       | Indices of papers to write (defaults to all if null)                                     |
| `native_write`      | boolean        | No       | When `true`, skip pyzotero and return `approved_papers` for native JS write (ZAP-6/7/8) |
| `enable_pdf_imports`| boolean        | No       | When `true`, attach open-access PDF URLs to newly created Zotero items                   |

**Response:**

```json
{
  "run_id": "abc-123",
  "thread_id": "thread-456",
  "status": "completed",
  "approved_papers": null
}
```

`approved_papers` is populated only when `native_write=true` — it is the list of
[NormalizedPaper](#normalizedpaper) dicts for the add-on to write directly.

---

### `GET /status/{run_id}`

Retrieve the current state of a workflow run.

**Response:**

```json
{
  "run_id": "abc-123",
  "thread_id": "thread-456",
  "status": "awaiting_approval",
  "state": { },
  "error": null
}
```

| Field       | Type           | Description                              |
| ----------- | -------------- | ---------------------------------------- |
| `run_id`    | string         | Workflow run identifier                  |
| `thread_id` | string         | Thread ID for continuity                 |
| `status`    | RunStatus      | Current workflow status (see below)      |
| `state`     | AgentState \| null | Full workflow state (see below)      |
| `error`     | string \| null | Error message if workflow failed         |

**AgentState schema** (the `state` object):

| Field              | Type                           | Description                                              |
| ------------------ | ------------------------------ | -------------------------------------------------------- |
| `request_id`       | string                         | Internal request identifier                              |
| `thread_id`        | string                         | Thread ID                                                |
| `messages`         | string[]                       | LangGraph message log                                    |
| `papers`           | NormalizedPaper[]              | Retrieved and ranked papers                              |
| `collection_name`  | string \| null                 | Target Zotero collection name                            |
| `approved`         | boolean                        | Whether the workflow has been approved                   |
| `decision`         | `"approved"` \| `"rejected"` \| `"pending"` | Current decision state                  |
| `phase`            | `"search_complete"` \| `"awaiting_approval"` \| `"completed"` \| `"rejected"` \| `"failed"` | Workflow phase |
| `selected_indices` | int[]                          | Indices of papers selected for write                     |
| `preflight`        | PreflightStatus                | Zotero preflight result at run time                      |
| `write_result`     | WriteResult \| null            | Zotero write outcomes (after approval)                   |
| `search_metadata`  | [SearchMetadata](#searchmetadata) \| null | Retrieval execution metadata including `source_states` |

---

### `GET /status/{run_id}/export`

Export a run in Markdown, JSON, or CSV.

**Query parameters:**

| Parameter | Type                              | Default    | Description     |
| --------- | --------------------------------- | ---------- | --------------- |
| `format`  | `"markdown"` \| `"json"` \| `"csv"` | `markdown` | Export format |

Returns the export as `text/markdown`, `application/json`, or `text/csv` respectively.

---

### `GET /correct-query`

Spell-check a query string.

**Query parameters:** `?q=trandign+timeseries`

**Response:**

```json
{
  "original": "trandign timeseries",
  "corrected": "trending timeseries",
  "changed": true
}
```

---

### `POST /extract-keywords`

Extract structured filter parameters from a natural-language query using the LLM provider.

**Request:**

```json
{ "query": "recent transformers for NLP, not older than 2022, open access only" }
```

**Response:**

```json
{
  "include_keywords": ["transformers", "NLP"],
  "exclude_keywords": [],
  "collection_name": null,
  "min_year": 2022,
  "max_year": null,
  "min_citations": null,
  "max_citations": null,
  "open_access_only": true
}
```

---

### `POST /library-doctor`

Scan a Zotero collection for missing metadata (DOI, abstract, PDF) and duplicates.

**Request:** `{ "collection_name": "My Papers" }`

**Response:**

```json
{
  "collection_name": "My Papers",
  "total_items": 42,
  "issues": [
    {
      "item_key": "ABCD1234",
      "title": "Some Paper",
      "issue_types": ["missing_doi", "missing_abstract"],
      "duplicate_of": null
    }
  ],
  "duplicate_pairs": [["KEY1", "KEY2"]]
}
```

`issue_types` values: `"missing_doi"`, `"missing_abstract"`, `"missing_pdf"`, `"duplicate"`.

---

### `POST /gap-finder`

Ask the LLM to suggest papers missing from an existing Zotero collection.

**Request:** `{ "collection_name": "My Papers" }`

**Response:**

```json
{
  "reasoning": "The collection covers X well but lacks coverage of Y...",
  "papers": [ ]
}
```

`papers` is an array of [NormalizedPaper](#normalizedpaper) objects.

---

### Watch List Endpoints

Watches are saved searches that can be re-run to detect new papers since the last run.

#### `POST /watches`

Create a watch.

**Request:**

```json
{
  "name": "Weekly RAG digest",
  "query": "retrieval augmented generation",
  "collection_name": "RAG Papers",
  "filter_edit": null
}
```

Returns a `WatchSummary` object (see below) with HTTP 201.

#### `GET /watches`

List all watches. Returns `WatchSummary[]`.

#### `GET /watches/{watch_id}`

Get a single watch by ID. Returns `WatchSummary`.

#### `DELETE /watches/{watch_id}`

Delete a watch. Returns HTTP 204.

#### `POST /watches/{watch_id}/rerun`

Re-run a watch search and detect new papers since last run.

**Response:**

```json
{
  "watch_id": "watch-uuid",
  "run_id": "run-uuid",
  "thread_id": "thread-uuid",
  "status": "awaiting_approval",
  "new_count": 3,
  "total_count": 10
}
```

The resulting run enters the normal approval flow via `POST /resume`. Papers include a
`watch_status` field: `"new"` (not seen before) or `"seen"` (already in the seen fingerprint set).

**WatchSummary schema:**

| Field             | Type                  | Description                                           |
| ----------------- | --------------------- | ----------------------------------------------------- |
| `id`              | string                | Watch UUID                                            |
| `name`            | string                | Human-readable label                                  |
| `query`           | string                | Saved search query                                    |
| `collection_name` | string \| null        | Target collection (null uses backend default)         |
| `created_at`      | string (ISO 8601)     | Creation timestamp                                    |
| `last_run_at`     | string \| null        | Last rerun timestamp                                  |
| `seen_count`      | int                   | Number of paper fingerprints already seen             |
| `filter_edit`     | FilterEditContract \| null | Saved filter overrides                           |

---

### Session Endpoints

Sessions persist run state to disk for export and rerun after the in-memory store is cleared.

#### `GET /sessions`

List saved sessions. Returns a list of session summary dicts.

#### `GET /sessions/{session_id}`

Load a full session state dict.

#### `POST /sessions/{session_id}/rerun`

Re-run a saved session with the same query and filters. Returns `RunAcceptedResponse`.

---

### Cache Endpoints

#### `GET /cache/stats`

Return hit/miss/size statistics for the result cache.

#### `DELETE /cache/clear`

Clear the result cache.

**Query parameter:** `?expired_only=true` — only delete entries past their TTL (default: `false`).

**Response:** `{ "deleted": 12, "expired_only": false }`

---

## Shared Schemas

### FilterEditContract {#filteredit-contract}

Structured filter payload sent in `/run` and saved in watches. When provided, `original_query`
must exactly match the top-level `query` field.

```json
{
  "original_query": "retrieval augmented generation",
  "hard_filters": {
    "min_year": 2020,
    "max_year": null,
    "min_citations": 0,
    "max_citations": null,
    "open_access_only": false,
    "include_keywords": ["RAG"],
    "exclude_keywords": ["healthcare"]
  },
  "soft_preferences": {
    "require_positive_community_perception": false,
    "min_semantic_score": 0.0
  },
  "result_limit": 10
}
```

**HardFilters:**

| Field              | Type          | Description                                                     |
| ------------------ | ------------- | --------------------------------------------------------------- |
| `min_year`         | int \| null   | Reject papers published before this year                        |
| `max_year`         | int \| null   | Reject papers published after this year                         |
| `min_citations`    | int           | Reject papers with fewer citations (default: 0)                 |
| `max_citations`    | int \| null   | Reject papers with more citations                               |
| `open_access_only` | boolean       | Restrict to open-access papers (default: false)                 |
| `include_keywords` | string[]      | Papers must contain at least one of these terms                 |
| `exclude_keywords` | string[]      | Papers containing any of these terms are excluded               |

Hard filters are pushed down to source APIs where supported and re-applied post-merge.
LLM query rewriting cannot remove or weaken them.

**SoftPreferences:**

| Field                               | Type    | Description                                              |
| ----------------------------------- | ------- | -------------------------------------------------------- |
| `require_positive_community_perception` | boolean | Boost papers with high community engagement           |
| `min_semantic_score`                | float   | Minimum semantic relevance score (0.0–1.0, default 0.0) |

---

### NormalizedPaper

All endpoints that return papers use this schema.

| Field                        | Type           | Description                                              |
| ---------------------------- | -------------- | -------------------------------------------------------- |
| `title`                      | string         | Paper title                                              |
| `year`                       | int \| null    | Publication year                                         |
| `doi`                        | string \| null | DOI (normalized, without `https://doi.org/` prefix)      |
| `arxiv_id`                   | string \| null | arXiv ID (e.g. `2005.11401`)                             |
| `abstract`                   | string \| null | Paper abstract                                           |
| `authors`                    | string[]       | Author names                                             |
| `url`                        | string \| null | Landing page URL                                         |
| `pdf_url`                    | string \| null | Direct PDF URL (used for attachment)                     |
| `source`                     | string         | Source provider name (e.g. `semantic_scholar`, `openalex`) |
| `index`                      | int \| null    | Stable 0-based result index                              |
| `semantic_score`             | float          | Semantic relevance score (0.0–1.0)                       |
| `citation_count`             | int            | Total citations                                          |
| `influential_citation_count` | int            | Influential citations (Semantic Scholar signal)          |
| `open_access`                | boolean        | Whether a free version is available                      |
| `summary`                    | string \| null | LLM-generated 3–4 sentence summary                      |
| `score`                      | float          | Final ranking score (composite)                          |
| `explanation`                | string \| null | Human-readable ranking explanation                       |
| `library_status`             | `"new"` \| `"in_library"` \| `"possible_duplicate"` \| null | Zotero library match |
| `watch_status`               | `"new"` \| `"seen"` \| null | Watch rerun novelty tag                     |
| `venue`                      | string \| null | Journal, conference, or preprint server name             |
| `item_type`                  | `"journal_article"` \| `"preprint"` \| `"conference_paper"` \| `"book_chapter"` \| `"other"` \| null | Publication type |
| `volume`                     | string \| null | Journal volume                                           |
| `issue`                      | string \| null | Journal issue                                            |
| `pages`                      | string \| null | Page range                                               |

---

### SearchMetadata

Returned in `state.search_metadata` from `GET /status/{run_id}`.

| Field               | Type                                          | Description                                             |
| ------------------- | --------------------------------------------- | ------------------------------------------------------- |
| `original_query`    | string                                        | Query as submitted by the user                          |
| `rewritten_query`   | string \| null                                | LLM-rewritten query (null if regex mode)                |
| `regex_query`       | string                                        | Keyword query string used for retrieval                 |
| `sources_used`      | string[]                                      | Names of sources that returned results                  |
| `sources_failed`    | string[]                                      | Names of sources that encountered errors                |
| `source_states`     | Record\<string, [SourceTerminalState](#sourceterminalstate)\> | Per-source terminal state |
| `mode`              | `"llm_rewrite"` \| `"regex"`                  | Query mode used                                         |
| `retry_count`       | int                                           | Number of LLM-guided retries performed                  |
| `total_fetched`     | int                                           | Total papers fetched across all sources before filtering |
| `total_after_filter`| int                                           | Papers remaining after hard-filter enforcement          |
| `source_timings`    | Record\<string, float\>                       | Per-source wall-clock time in seconds                   |
| `search_plan`       | [SearchPlan](#searchplan) \| null             | Typed search plan produced before retrieval             |

---

### SearchPlan

The structured plan produced before retrieval runs. Returned in `search_metadata.search_plan`.

| Field                        | Type                  | Description                                                  |
| ---------------------------- | --------------------- | ------------------------------------------------------------ |
| `original_query`             | string                | Original user query                                          |
| `topic_query`                | string                | Cleaned topic string used as the retrieval seed              |
| `rewritten_queries`          | string[]              | LLM-generated query variants                                 |
| `hard_filters`               | HardFilters           | Parsed deterministic filter constraints                      |
| `soft_preferences`           | SoftPreferences       | Parsed ranking preferences                                   |
| `source_policy`              | SourceCapability[]    | Per-source policy at plan time                               |
| `filters_pushed_down`        | Record\<string, string[]\> | Filters applied at the source API level per source      |
| `filters_enforced_post_merge`| string[]              | Filters enforced after cross-source merge                    |

---

### SourceCapability

| Field                       | Type                      | Description                                          |
| --------------------------- | ------------------------- | ---------------------------------------------------- |
| `name`                      | string                    | Source identifier (e.g. `openalex`, `pubmed`)        |
| `tier`                      | `"primary"` \| `"fallback"` | Whether the source runs by default or as optional  |
| `enabled`                   | boolean                   | Whether the source is active for this run            |
| `supports_year_filter`      | boolean                   | Source API supports server-side year filtering       |
| `supports_open_access_filter` | boolean                 | Source API supports server-side OA filtering         |

---

### SourceTerminalState {#sourceterminalstate}

Every source that was considered for a run ends in exactly one of these states, reported in
`search_metadata.source_states` as `Record<string, SourceTerminalState>`.

| Value              | Meaning                                                              |
| ------------------ | -------------------------------------------------------------------- |
| `queried`          | Source was queried and returned at least one result                  |
| `zero_results`     | Source was queried but returned no results                           |
| `rate_limited`     | Source returned a rate-limit error                                   |
| `failed`           | Source encountered a non-rate-limit error                            |
| `skipped_no_key`   | Source requires an API key that is not configured (opt-in sources only) |
| `skipped_disabled` | Source was disabled by tier policy or depth setting for this run     |

---

## Status Values

| Value               | Description                                                       |
| ------------------- | ----------------------------------------------------------------- |
| `awaiting_approval` | Papers ready for review; workflow paused at the approval gate     |
| `completed`         | Workflow finished; selected papers written to Zotero              |
| `rejected`          | User rejected the workflow; no writes performed                   |
| `failed`            | Workflow encountered an unrecoverable error                       |

---

## Error Responses

### 401 Unauthorized

`AGT_BACKEND_API_KEY` is set but the `X-AGT-API-Key` header is missing or wrong.

```json
{ "detail": "invalid_api_key" }
```

### 403 Forbidden

Requesting a run that belongs to a different `X-AGT-Client-ID`.

```json
{ "detail": "run_forbidden" }
```

### 404 Not Found

```json
{ "detail": "run_not_found" }
```

Also returned as `"session_not_found"`, `"watch_not_found"` for those resources.

### 422 Validation Error

```json
{
  "detail": [
    { "loc": ["body", "query"], "msg": "field required", "type": "value_error.missing" }
  ]
}
```

### 429 Too Many Requests

Rate limit exceeded. Retry with exponential back-off.

---

## Client Integration Notes

### Zotero Add-on Flow

1. `GET /health` — verify backend and display `StatusPill`
2. `GET /capabilities` — drive `SourceToggles`, capability banner, and PDF controls
3. `POST /run` with optional `filter_edit` and `search_depth`
4. `GET /status/{run_id}` — retrieve `papers` and `search_metadata` for display
5. User reviews papers; `SearchCoveragePanel` uses `source_states` to show per-source outcomes
6. `POST /resume` with `approved=true`, `selected_indices`, and `native_write=true` for ZAP-6/7/8
7. Add-on writes papers via `approved_papers` array returned from step 6

### Development Setup

```bash
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
```

Interactive docs:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## See Also

- [Configuration & Usage Manual](manual.md)
- [Deployment Guide](deployment.md)
- [Zotero Add-on Roadmap](zotero.md)
