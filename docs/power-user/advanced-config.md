# Advanced Configuration

Nothing on this page is required to start using SciAgent. The defaults work for most researchers.
Come here when you want to tune performance, add privacy layers, or deploy for a team.

All settings are loaded from environment variables (or a `.env` file in the repo root) via
`pydantic-settings`. The canonical reference for every variable is [Settings](../reference/settings.md).

---

## Provider Tuning

### LLM provider selection

`AGT_LLM_PROVIDER` — override the auto-detected LLM provider.
Accepted values: `openai`, `anthropic`, `xai`, `groq`, `ollama`, `openai-compatible`.

If this variable is unset, SciAgent inspects your API keys in priority order
(OpenAI → Anthropic → xAI → Groq) and uses the first one found.

```ini
AGT_LLM_PROVIDER=anthropic
```

### Default model override

`AGT_MODEL_NAME` — override the default model for the chosen provider.
Also accepted as `AGT_LLM_MODEL`.

```ini
AGT_MODEL_NAME=claude-opus-4-6
```

### Custom OpenAI-compatible endpoint

Set these three variables together to route inference through any OpenAI-compatible API
(DeepSeek, Together AI, LM Studio, local vLLM, etc.):

- `AGT_LLM_BASE_URL` — base URL of the compatible endpoint
- `AGT_LLM_API_KEY` — API key for that endpoint
- `AGT_LLM_MODEL` — model name to request

```ini
AGT_LLM_PROVIDER=openai-compatible
AGT_LLM_BASE_URL=https://api.deepseek.com/v1
AGT_LLM_API_KEY=your-key-here
AGT_LLM_MODEL=deepseek-chat
```

For a fully offline setup with Ollama (no API key required):

```ini
AGT_LLM_PROVIDER=ollama
AGT_LLM_MODEL=llama3.2
```

### Provider fallback

`AGT_LLM_FALLBACK_PROVIDER` — secondary provider used when the primary fails.

`AGT_LLM_FAILOVER_ON_TIMEOUT` — fail over to the fallback on request timeout
(default `true`).

`AGT_LLM_FAILOVER_ON_RATE_LIMIT` — fail over to the fallback on rate-limit errors
(default `true`).

### Disabling academic sources

`AGT_DISABLED_PROVIDERS` — JSON array of academic source names to skip regardless of key
availability.

```ini
AGT_DISABLED_PROVIDERS=["google_scholar","core"]
```

Valid source names match the provider identifiers used internally: `openalex`, `crossref`,
`semantic_scholar`, `pubmed`, `arxiv`, `europe_pmc`, `base`, `opencitations`, `core`,
`dimensions`, `google_scholar`.

---

## Search Behaviour

`AGT_TIMEOUT_SECONDS` — per-request HTTP timeout in seconds (default `30`, range 1–300).

`AGT_RETRIES` — HTTP retry count on transient failures (default `3`, range 0–10).

`AGT_MAILTO` — email address for the polite-pool access offered by OpenAlex, Crossref, and
DOAJ. Providing a real address typically doubles the rate limit you receive from those
services. See [docs/reference/settings.md](../reference/settings.md) for details.

```ini
AGT_MAILTO=your-email@example.com
```

### Search depth and pagination

`AGT_SEARCH_DEPTH` — controls how many providers are queried and how aggressively results
are fetched. Accepted values: `quick`, `balanced` (default), `deep`.

`AGT_SEARCH_MAX_PAGES` — maximum result pages fetched per provider (default `1`, range 1–5).

### Summarization

`AGT_SUMMARIZATION_USE_LLM` — use the configured LLM for abstract summarization
(default `true`). Set to `false` to use the extractive fallback without consuming LLM tokens.

`AGT_SUMMARIZATION_MAX_SENTENCES` — sentence limit for summaries (default `4`, range 3–4).

### Keyword extraction and spell check

`AGT_USE_KEYBERT` — enable KeyBERT-based keyword extraction to expand queries
(default `false`; requires the `keybert` optional dependency).

`AGT_USE_SPELL_CHECK` — enable query spell correction before dispatch (default `false`).

### Reranking

`AGT_USE_RERANKER` — enable cross-encoder reranking of the merged result set
(default `false`; requires the `sentence-transformers` optional dependency).

`AGT_ENABLE_FALLBACK_RETRIEVAL` — fall back to broader keyword search when the primary
query returns fewer than the minimum expected results (default `false`).

### Per-provider rate limits

Each academic provider has an independent rate-limit knob (requests per minute):

| Variable | Default |
| ----------------------------------------- | ------- |
| `AGT_OPENALEX_RATE_LIMIT_PER_MINUTE` | `100` |
| `AGT_SEMANTIC_SCHOLAR_RATE_LIMIT_PER_MINUTE` | `55` |
| `AGT_CROSSREF_RATE_LIMIT_PER_MINUTE` | `80` |
| `AGT_PUBMED_RATE_LIMIT_PER_MINUTE` | `100` |
| `AGT_EUROPE_PMC_RATE_LIMIT_PER_MINUTE` | `100` |
| `AGT_ARXIV_RATE_LIMIT_PER_MINUTE` | `20` |
| `AGT_BASE_RATE_LIMIT_PER_MINUTE` | `40` |
| `AGT_OPENCITATIONS_RATE_LIMIT_PER_MINUTE` | `60` |
| `AGT_CORE_RATE_LIMIT_PER_MINUTE` | `60` |
| `AGT_DIMENSIONS_RATE_LIMIT_PER_MINUTE` | `40` |
| `AGT_GOOGLE_SCHOLAR_RATE_LIMIT_PER_MINUTE` | `20` |
| `AGT_LLM_RATE_LIMIT_PER_MINUTE` | `120` |
| `AGT_ZOTERO_RATE_LIMIT_PER_MINUTE` | `60` |

### Cost guard

`AGT_WORKFLOW_MAX_COST_USD` — abort a workflow run when estimated LLM spend exceeds this
threshold (default `0.50` USD).

---

## PDF Attachments

`AGT_ENABLE_PDF_ATTACHMENT` — when `true`, SciAgent downloads open-access PDFs and
attaches them to Zotero items as `imported_file` attachments (default `false`).

`AGT_PDF_DOWNLOAD_TIMEOUT` — HTTP timeout in seconds for each PDF download (default `60`,
range 5–300).

`AGT_PDF_DIR` — local directory used as a PDF cache (default `~/.sciagent/pdfs`).
Overrides the `pdfs/` subdirectory under `AGT_DATA_DIR`.

```ini
AGT_ENABLE_PDF_ATTACHMENT=true
AGT_PDF_DOWNLOAD_TIMEOUT=90
AGT_PDF_DIR=/data/sciagent/pdfs
```

---

## Data Directory

`AGT_DATA_DIR` — root directory where the embedded server stores all persistent data
(default `~/.sciagent`). Subdirectories `sessions/`, `cache/`, `watches/`, and `pdfs/`
are created automatically under this root unless individually overridden.

Individual overrides (each defaults to a subdirectory under `AGT_DATA_DIR`):

- `AGT_SESSION_DIR` — persistent session JSON files
- `AGT_CACHE_DIR` — SQLite result cache
- `AGT_WATCH_DIR` — persistent watch JSON files

`AGT_CACHE_TTL_SECONDS` — time-to-live for cached search results in seconds
(default `86400`, i.e. 24 hours; minimum 60).

```ini
AGT_DATA_DIR=/var/lib/sciagent
```

---

## Backend Security (Self-Hosters)

These settings apply when you expose the SciAgent REST API over a network rather than using
it purely locally. See [Deployment](deployment.md) for a full self-hosting guide.

`AGT_BACKEND_API_KEY` — shared secret required by all HTTP endpoints. Clients must send
the key as the `X-AGT-Api-Key` header. Leave unset for local-only use.

```ini
AGT_BACKEND_API_KEY=change-me-to-a-random-secret
```

`AGT_CORS_ALLOWED_ORIGINS` — JSON array of origins the API server will accept cross-origin
requests from (default `["*"]`). Restrict this in production.

```ini
AGT_CORS_ALLOWED_ORIGINS=["https://your-zotero-addon-origin"]
```

`AGT_API_RATE_LIMIT` — global rate limit per IP, expressed in
[slowapi](https://github.com/laurentS/slowapi) format (default `200/minute`).

```ini
AGT_API_RATE_LIMIT=60/minute
```

`AGT_ENV` — runtime environment tag; one of `local` (default), `staging`, `production`.
Used together with `AGT_ENV_OVERRIDES` to apply environment-specific LLM tuning.

`AGT_ENV_OVERRIDES` — JSON object mapping environment names to runtime parameter overrides.
Accepted keys per environment: `provider`, `model_name`, `timeout_seconds`, `retries`,
`temperature`.

```ini
AGT_ENV=production
AGT_ENV_OVERRIDES={"production": {"provider": "anthropic", "temperature": 0.1}}
```

---

## Logging

`AGT_LOG_LEVEL` — minimum log level emitted by the structured logger. Accepted values:
`DEBUG`, `INFO` (default), `WARNING`, `ERROR`.

All log output is JSON-structured via `structlog`. Sensitive values (API keys, tokens,
secrets) are automatically redacted before any log record is written.

```ini
AGT_LOG_LEVEL=DEBUG
```

---

## MCP Server

SciAgent exposes an MCP-compatible server that allows tool-use workflows to query the
academic search and Zotero write paths programmatically. See [API Reference](../reference/api.md) for
the full endpoint contract and authentication details.

---

## See Also

- [Settings](../reference/settings.md) — canonical reference for every environment variable and its
  validation rules
- [Deployment](deployment.md) — self-hosting, Docker, reverse-proxy, and team setup guide
