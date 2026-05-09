# SciAgent REST API Reference

The SciAgent backend exposes a FastAPI REST API for programmatic access and as the backend for the Zotero add-on.

## Base URL

```text
http://localhost:8000
```

## Authentication

All endpoints support optional authentication via headers:

| Header            | Required | Description                                                     |
| ----------------- | -------- | --------------------------------------------------------------- |
| `X-AGT-API-Key`   | Optional | Backend API key (required if `AGT_BACKEND_API_KEY` set)         |
| `X-AGT-Client-ID` | Optional | Client identifier for multi-user isolation (default: anonymous) |

When `AGT_BACKEND_API_KEY` is configured, all requests must include a matching `X-AGT-API-Key` header.

Client isolation: workflows are scoped by `X-AGT-Client-ID`. Each client can only access their own runs.

## Endpoints

### `GET /health`

Check system health, Zotero connectivity, and provider status.

**Request:**

```bash
curl http://localhost:8000/health
```

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
  "provider": "xai",
  "fallback_provider": null,
  "api_contract_version": "2026-05"
}
```

**Response Fields:**

- `ok`: Overall health status (boolean)
- `message`: Human-readable status message
- `preflight.ok`: Whether Zotero library access is functional
- `preflight.can_read`: Zotero read permission verified
- `preflight.can_write`: Zotero write permission verified
- `preflight.key_valid`: Zotero API key is valid
- `preflight.message`: Human-readable status message
- `provider`: Current LLM provider name
- `fallback_provider`: Optional fallback LLM provider name (null if not configured)
- `api_contract_version`: Backend contract version string (format: `YYYY-MM`) for client compatibility checks

---

### `POST /run`

Start a new search workflow. Returns when papers are ready at the approval checkpoint.

**Request:**

```json
{
  "query": "retrieval augmented generation",
  "collection_name": "RAG Papers",
  "thread_id": "optional-thread-id",
  "filter_edit": null
}
```

**Request Fields:**

| Field             | Type                       | Required | Description                                                 |
| ----------------- | -------------------------- | -------- | ----------------------------------------------------------- |
| `query`           | string                     | Yes      | Natural-language search query (min 1 character)             |
| `collection_name` | string                     | Yes      | Target Zotero collection name (min 1 character)             |
| `thread_id`       | string \| null             | No       | Optional thread ID for resumption/context                   |
| `filter_edit`     | FilterEditContract \| null | No       | Optional filter edits for re-runs with modified search plan |

**FilterEditContract Schema:**

When provided, allows editing the backend's parsed search plan before re-running.

```json
{
  "original_query": "retrieval augmented generation",
  "min_year": 2020,
  "max_year": null,
  "open_access": null,
  "exclude_terms": ["healthcare"],
  "source_policy": "default",
  "soft_preferences": {
    "most_cited": false,
    "recent": false
  }
}
```

**Filter Edit Rules:**

- `filter_edit.original_query` must match `query` exactly
- Backend validates filter constraints before execution
- Hard filters (`min_year`, `exclude_terms`) are respected strictly
- Soft preferences (`most_cited`, `recent`) adjust ranking but don't exclude results

**Response:**

```json
{
  "run_id": "abc-123",
  "thread_id": "thread-456",
  "status": "awaiting_approval"
}
```

**Response Fields:**

- `run_id`: Unique workflow run identifier
- `thread_id`: Thread ID for state continuity
- `status`: Current workflow status (see Status Values)

**Example with Authentication:**

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -H "X-AGT-API-Key: my-secret-backend-key" \
  -H "X-AGT-Client-ID: user-1" \
  -d '{
    "query": "retrieval augmented generation",
    "collection_name": "RAG Papers"
  }'
```

**Example with Filter Edit:**

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -H "X-AGT-API-Key: my-secret-backend-key" \
  -H "X-AGT-Client-ID: user-1" \
  -d '{
    "query": "retrieval augmented generation",
    "collection_name": "RAG Papers",
    "filter_edit": {
      "original_query": "retrieval augmented generation",
      "min_year": 2020,
      "max_year": null,
      "open_access": null,
      "exclude_terms": ["healthcare"],
      "source_policy": "default",
      "soft_preferences": {
        "most_cited": false,
        "recent": false
      }
    }
  }'
```

---

### `GET /status/{run_id}`

Retrieve the current state of a workflow run.

**Request:**

```bash
curl http://localhost:8000/status/abc-123 \
  -H "X-AGT-API-Key: my-secret-backend-key" \
  -H "X-AGT-Client-ID: user-1"
```

**Response:**

```json
{
  "run_id": "abc-123",
  "thread_id": "thread-456",
  "status": "awaiting_approval",
  "state": {
    "query": "retrieval augmented generation",
    "collection_name": "RAG Papers",
    "papers": [
      {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "authors": ["Patrick Lewis", "Ethan Perez", "et al."],
        "year": 2020,
        "doi": "10.48550/arXiv.2005.11401",
        "arxiv_id": "2005.11401",
        "summary": "RAG models combine pre-trained parametric and non-parametric memory...",
        "citations": 1234,
        "source": "arxiv"
      }
    ],
    "search_plan": {
      "topic": "retrieval augmented generation",
      "min_year": null,
      "max_year": null,
      "open_access": null,
      "exclude_terms": [],
      "source_policy": "default",
      "soft_preferences": {
        "most_cited": false,
        "recent": false
      }
    },
    "write_results": null,
    "error": null
  },
  "error": null
}
```

**Response Fields:**

- `run_id`: Workflow run identifier
- `thread_id`: Thread ID for continuity
- `status`: Current workflow status
- `state`: Full workflow state including papers, search plan, and write results (if available)
- `error`: Error message if workflow failed

**State Schema:**

The `state` object contains:

- `query`: Original search query
- `collection_name`: Target collection name
- `papers`: Array of normalized paper objects
- `search_plan`: Parsed filter contract showing backend's search constraints
- `write_results`: Array of write outcomes (available after approval)
- `error`: Error message if any step failed

**Paper Object Schema:**

```json
{
  "title": "string",
  "authors": ["string"],
  "year": 2020,
  "doi": "string | null",
  "arxiv_id": "string | null",
  "summary": "string",
  "citations": 1234,
  "influential_citations": 56,
  "source": "arxiv",
  "url": "https://...",
  "is_open_access": true,
  "venue": "NeurIPS 2020"
}
```

**Search Plan Schema:**

```json
{
  "topic": "retrieval augmented generation",
  "min_year": 2020,
  "max_year": null,
  "open_access": null,
  "exclude_terms": ["healthcare"],
  "source_policy": "default",
  "soft_preferences": {
    "most_cited": false,
    "recent": true
  }
}
```

---

### `POST /resume`

Approve or reject a workflow at the approval checkpoint. On approval, writes selected papers to Zotero.

**Request (Approve):**

```json
{
  "run_id": "abc-123",
  "approved": true,
  "collection_name": "RAG Papers",
  "selected_indices": [0, 2, 4]
}
```

**Request (Reject):**

```json
{
  "run_id": "abc-123",
  "approved": false
}
```

**Request Fields:**

| Field              | Type           | Required | Description                                               |
| ------------------ | -------------- | -------- | --------------------------------------------------------- |
| `run_id`           | string         | Yes      | Workflow run identifier from `/run` response              |
| `approved`         | boolean        | Yes      | `true` to write to Zotero, `false` to discard             |
| `collection_name`  | string \| null | No       | Override collection name (uses original if not provided)  |
| `selected_indices` | int[] \| null  | No       | Array of paper indices to write (defaults to all if null) |

**Response:**

```json
{
  "run_id": "abc-123",
  "thread_id": "thread-456",
  "status": "completed"
}
```

**Status on Approval:**

- `completed`: All selected papers written successfully
- `failed`: Write operation encountered errors

**Status on Rejection:**

- `rejected`: Workflow discarded without writes

**Example with Selection:**

```bash
curl -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -H "X-AGT-API-Key: my-secret-backend-key" \
  -H "X-AGT-Client-ID: user-1" \
  -d '{
    "run_id": "abc-123",
    "approved": true,
    "selected_indices": [0, 2, 4],
    "collection_name": "My RAG Collection"
  }'
```

**Example Rejection:**

```bash
curl -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -H "X-AGT-API-Key: my-secret-backend-key" \
  -H "X-AGT-Client-ID: user-1" \
  -d '{
    "run_id": "abc-123",
    "approved": false
  }'
```

---

## Status Values

| Status              | Description                                                       |
| ------------------- | ----------------------------------------------------------------- |
| `awaiting_approval` | Papers ready for review; workflow paused at approval checkpoint   |
| `completed`         | Workflow finished successfully; selected papers written to Zotero |
| `rejected`          | User rejected the workflow; no writes performed                   |
| `failed`            | Workflow encountered an error                                     |

---

## Error Responses

### 401 Unauthorized

Returned when `AGT_BACKEND_API_KEY` is set but the provided `X-AGT-API-Key` header is missing or invalid.

```json
{
  "detail": "invalid_api_key"
}
```

### 404 Not Found

Returned when requesting status for a run ID that doesn't exist or belongs to a different client.

```json
{
  "detail": "run_id_not_found"
}
```

### 422 Validation Error

Returned when request payload fails validation.

```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Contract Versioning

The current API is **v0.1.0** and follows these stability rules:

1. Endpoint paths (`/health`, `/run`, `/status/{run_id}`, `/resume`) are stable
2. Required request fields will not be removed in minor versions
3. Optional fields may be added to requests/responses in minor versions
4. Breaking changes (removing fields, changing field types) require a major version bump
5. The `FilterEditContract` schema is considered stable for M6; extensions planned for M7

Future compatibility:

- M7 may introduce `/v1/` prefixed endpoints with enhanced multi-user isolation
- M7 may add async job polling for long-running workflows
- M7 may introduce webhook support for approval notifications

---

## Client Implementation Notes

### Zotero Add-on Integration

The Zotero 9 add-on uses this API with the following flow:

1. **Health Check**: `GET /health` on startup to verify backend connectivity
2. **Run Search**: `POST /run` with query and collection name
3. **Poll Status**: `GET /status/{run_id}` to retrieve papers and search plan
4. **Display Filters**: Render parsed search plan for user review/edit
5. **Re-run with Edits**: `POST /run` with `filter_edit` payload if user modifies filters
6. **Approve/Reject**: `POST /resume` with selection and approval decision

### Error Handling

Clients should implement:

- Retry logic for transient errors (network, timeout)
- Exponential backoff for rate limit errors
- Clear error messages for authentication failures
- Graceful degradation when backend is unreachable

### Performance

- `/run` typically completes in 5-15 seconds for 10-20 sources
- `/status/{run_id}` response size varies with paper count (typically 10-50 KB)
- `/resume` with approval may take 2-5 seconds per paper for Zotero writes
- No built-in pagination yet; large result sets may exceed client memory

---

## Development and Testing

### Local Backend Setup

```bash
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
```

### Testing Authentication

```bash
# Set backend API key in environment
export AGT_BACKEND_API_KEY=test-key-123

# Start backend
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000

# Test with valid key
curl http://localhost:8000/health \
  -H "X-AGT-API-Key: test-key-123"

# Test with missing/invalid key (should return 401)
curl http://localhost:8000/health
```

### Testing Client Isolation

```bash
# Client 1 creates a run
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -H "X-AGT-Client-ID: client-1" \
  -d '{"query": "test", "collection_name": "Test"}'

# Client 2 cannot access client-1's run
curl http://localhost:8000/status/abc-123 \
  -H "X-AGT-Client-ID: client-2"
```

### API Documentation

FastAPI auto-generates interactive docs:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

---

## See Also

- [Configuration & Usage Manual](manual.md) — End-to-end setup and configuration
- [Deployment Guide](deployment.md) — Local, Docker, and SaaS deployment options
- [Zotero Add-on Roadmap](zotero.md) — Add-on architecture and roadmap
