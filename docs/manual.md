# SciAgent — Configuration & Usage Manual

> One document covering installation, configuration, and every way to run SciAgent.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running SciAgent](#running-sciagent)
5. [API Reference](#api-reference)
6. [Retrieval Sources](#retrieval-sources)
7. [Advanced Configuration](#advanced-configuration)
8. [Troubleshooting](#troubleshooting)
9. [Development](#development)

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | >= 3.13 (recommended: 3.14) | Free-threaded GIL optional support |
| `uv` | latest | Package manager ([install](https://astral.sh/uv)) |
| Zotero account | — | With API key and library ID |
| xAI API key | — | Default LLM provider (or OpenAI/Anthropic) |

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/sciagent.git
cd sciagent

# 2. Install all dependencies
uv sync

# 3. Copy environment template
cp .env.example .env

# 4. Install pre-commit hooks (for development)
uv run pre-commit install
```

---

## Configuration

All configuration is loaded from environment variables via `pydantic-settings`. You can set values in a `.env` file or export them directly.

### Required Variables

These **must** be set — the application will fail fast with an actionable error if they are missing.

| Variable | Description | Example |
|----------|-------------|---------|
| `AGT_XAI_API_KEY` | xAI (Grok) API key | `xai-abc123...` |
| `AGT_ZOTERO_API_KEY` | Zotero API key ([get one here](https://www.zotero.org/settings/keys)) | `AbCdEf12345...` |
| `AGT_ZOTERO_LIBRARY_ID` | Your Zotero library ID (numeric) | `12345678` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGT_ZOTERO_LIBRARY_TYPE` | `user` | `user` or `group` |
| `AGT_LLM_PROVIDER` | `xai` | LLM provider: `xai`, `openai`, `anthropic`, `groq` |
| `AGT_MODEL_NAME` | `grok-4` | Model name for the selected provider |
| `AGT_TIMEOUT_SECONDS` | `30` | LLM call timeout (1–300) |
| `AGT_RETRIES` | `3` | LLM retry count (0–10) |
| `AGT_TEMPERATURE` | `0.2` | LLM sampling temperature (0.0–2.0) |
| `AGT_LOG_LEVEL` | `INFO` | Logging level |
| `AGT_ENV` | `local` | Runtime environment: `local`, `staging`, `production` |

### Optional API Keys (Enhance Retrieval)

These keys are **optional** but improve retrieval coverage and rate limits.

| Variable | Service | Free? |
|----------|---------|-------|
| `AGT_SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar (higher rate limits) | Yes |
| `AGT_NCBI_API_KEY` | PubMed / NCBI E-Utilities | Yes |
| `AGT_CORE_API_KEY` | CORE aggregator | Yes (with registration) |
| `AGT_SERPAPI_KEY` | Google Scholar via SerpAPI | Paid |
| `AGT_DIMENSIONS_KEY` | Dimensions.ai | Paid |
| `AGT_OPENAI_API_KEY` | OpenAI (if using as alternative LLM) | Paid |
| `AGT_ANTHROPIC_API_KEY` | Anthropic (if using as alternative LLM) | Paid |
| `AGT_GROQ_API_KEY` | Groq (if using as alternative LLM) | Free tier available |

### Backend Security

| Variable | Default | Description |
|----------|---------|-------------|
| `AGT_BACKEND_API_KEY` | None | If set, all API endpoints require `X-AGT-API-Key` header |

### LLM Provider Routing

| Variable | Default | Description |
|----------|---------|-------------|
| `AGT_LLM_FALLBACK_PROVIDER` | None | Fallback provider on primary failure (e.g. `openai`) |
| `AGT_LLM_FAILOVER_ON_TIMEOUT` | `true` | Switch to fallback on timeout |
| `AGT_LLM_FAILOVER_ON_RATE_LIMIT` | `true` | Switch to fallback on rate limit |

### Example `.env` File

```env
# Required
AGT_XAI_API_KEY=xai-your-key-here
AGT_ZOTERO_API_KEY=your-zotero-api-key
AGT_ZOTERO_LIBRARY_ID=12345678
AGT_ZOTERO_LIBRARY_TYPE=user

# LLM settings
AGT_LLM_PROVIDER=xai
AGT_MODEL_NAME=grok-4
AGT_TEMPERATURE=0.2

# Optional: enhanced retrieval
AGT_SEMANTIC_SCHOLAR_API_KEY=your-s2-key
AGT_NCBI_API_KEY=your-ncbi-key

# Optional: backend auth
AGT_BACKEND_API_KEY=my-secret-backend-key

# Optional: LLM failover
AGT_LLM_FALLBACK_PROVIDER=openai
AGT_OPENAI_API_KEY=sk-your-openai-key
```

---

## Running SciAgent

SciAgent has three interfaces: **CLI**, **Streamlit UI**, and **REST API**.

### Option 1: Command-Line Interface

Run a single search workflow from the terminal:

```bash
# Basic search (no write — just displays results)
uv run python -m agt.graph.cli "retrieval augmented generation" --collection "RAG Papers"

# Search and approve (writes to Zotero)
uv run python -m agt.graph.cli "deep learning for drug discovery" \
    --collection "Drug Discovery" \
    --approve

# With a specific thread ID (for resuming later)
uv run python -m agt.graph.cli "transformer architectures 2024+" \
    --collection "Transformers" \
    --thread-id "my-session-1" \
    --approve
```

**Output:** JSON with full workflow state including papers found, write results, and trace spans.

### Option 2: Streamlit UI (Interactive)

Launch the web-based approval interface:

```bash
uv run streamlit run src/agt/ui/app.py
```

Open `http://localhost:8501` in your browser. The UI provides:

1. **Search box** — type a natural-language query
2. **Paper list** — review results with summaries, citations, and sources
3. **Select papers** — check/uncheck individual papers
4. **Collection name** — set or edit the target Zotero collection
5. **Approve/Reject** — approve writes to Zotero or reject to discard
6. **Per-item results** — see created/unchanged/failed status for each paper

### Option 3: REST API (Backend)

Start the FastAPI backend server:

```bash
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
```

The API is designed for programmatic access and as the backend for the Zotero add-on.

---

## API Reference

All endpoints are available at `http://localhost:8000` by default.

### `GET /health`

Check system health, Zotero connectivity, and provider status.

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "preflight": {
    "ok": true,
    "can_read": true,
    "can_write": true,
    "key_valid": true,
    "message": "Library access verified"
  },
  "provider": "xai"
}
```

### `POST /run`

Start a search workflow. Returns papers at the approval checkpoint.

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -H "X-AGT-API-Key: my-secret-backend-key" \
  -H "X-AGT-Client-ID: user-1" \
  -d '{"query": "retrieval augmented generation", "collection_name": "RAG Papers"}'
```

**Response:**
```json
{
  "run_id": "abc-123",
  "thread_id": "thread-456",
  "status": "awaiting_approval"
}
```

### `POST /resume`

Approve or reject a pending workflow.

```bash
# Approve with specific papers selected
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

# Reject (no writes)
curl -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -H "X-AGT-API-Key: my-secret-backend-key" \
  -H "X-AGT-Client-ID: user-1" \
  -d '{"run_id": "abc-123", "approved": false}'
```

### `GET /status/{run_id}`

Check the current state of a workflow.

```bash
curl http://localhost:8000/status/abc-123 \
  -H "X-AGT-API-Key: my-secret-backend-key" \
  -H "X-AGT-Client-ID: user-1"
```

### Authentication

If `AGT_BACKEND_API_KEY` is set, all endpoints require the `X-AGT-API-Key` header. Requests are isolated by `X-AGT-Client-ID` — each client can only access their own workflows.

---

## Retrieval Sources

SciAgent searches across multiple academic databases simultaneously and merges results with deduplication.

### Always Available (No Key Required)

| Source | Coverage | Notes |
|--------|----------|-------|
| **Semantic Scholar** | 200M+ papers | Primary source, rich metadata |
| **OpenAlex** | 250M+ works | Open bibliographic data |
| **Crossref** | 130M+ records | DOI metadata, publisher data |
| **PubMed** | 36M+ biomedical | NCBI E-Utilities |
| **Europe PMC** | 43M+ life sciences | Open access indicator |
| **arXiv** | 2.4M+ preprints | Physics, CS, math, etc. |
| **OpenCitations** | Citation enrichment | Adds citation counts |

### Require API Key

| Source | Key Variable | Notes |
|--------|-------------|-------|
| **CORE** | `AGT_CORE_API_KEY` | Full-text aggregator |
| **Dimensions** | `AGT_DIMENSIONS_KEY` | Comprehensive metadata |
| **Google Scholar** | `AGT_SERPAPI_KEY` | Via SerpAPI (experimental) |

### How Search Works

1. Your natural-language query is rewritten by the LLM into optimized academic search terms
2. All available sources are queried in parallel
3. Results are deduplicated (DOI + arXiv ID + title hash)
4. Papers are ranked by a multi-factor formula: semantic relevance (45%), citations (30%), influential citations (10%), recency (12%), abstract quality (5%), open access (3%)
5. Constraints are applied (year filters, citation thresholds, exclude terms)
6. LLM validates result relevance and retries with improved query if needed

### Query Examples

| Natural Language Query | What Happens |
|----------------------|--------------|
| `"retrieval augmented generation"` | Direct keyword search across all sources |
| `"most cited 2020+ timeseries papers"` | Extracts year≥2020 constraint, citation filter, searches "timeseries" |
| `"RAG techniques not about healthcare"` | Searches "RAG", excludes papers mentioning "healthcare" |
| `"deep RL robotics between 2022 and 2024"` | Year range 2022–2024, keywords "deep reinforcement learning robotics" |
| `"nutrition in sport"` | LLM rewrites to "sports nutrition" for better API coverage |

---

## Advanced Configuration

### Rate Limits

Each retrieval source has a configurable rate limit (requests per minute per thread):

| Variable | Default |
|----------|---------|
| `AGT_SEMANTIC_SCHOLAR_RATE_LIMIT_PER_MINUTE` | 100 |
| `AGT_OPENALEX_RATE_LIMIT_PER_MINUTE` | 100 |
| `AGT_CROSSREF_RATE_LIMIT_PER_MINUTE` | 80 |
| `AGT_PUBMED_RATE_LIMIT_PER_MINUTE` | 100 |
| `AGT_EUROPE_PMC_RATE_LIMIT_PER_MINUTE` | 100 |
| `AGT_CORE_RATE_LIMIT_PER_MINUTE` | 60 |
| `AGT_ARXIV_RATE_LIMIT_PER_MINUTE` | 20 |
| `AGT_OPENCITATIONS_RATE_LIMIT_PER_MINUTE` | 60 |
| `AGT_ZOTERO_RATE_LIMIT_PER_MINUTE` | 60 |
| `AGT_LLM_RATE_LIMIT_PER_MINUTE` | 120 |

### Cost Guardrails

| Variable | Default | Description |
|----------|---------|-------------|
| `AGT_WORKFLOW_MAX_COST_USD` | `0.50` | Maximum LLM spend per workflow run |
| `AGT_XAI_INPUT_COST_PER_1K_TOKENS_USD` | `0.005` | Cost tracking for xAI input tokens |
| `AGT_XAI_OUTPUT_COST_PER_1K_TOKENS_USD` | `0.015` | Cost tracking for xAI output tokens |

### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `AGT_ENABLE_FALLBACK_RETRIEVAL` | `false` | Enable fallback sources when primary returns few results |
| `AGT_USE_KEYBERT` | `false` | Use KeyBERT for keyword extraction (requires `keybert` package) |
| `AGT_USE_SPELL_CHECK` | `false` | Enable spell checking on queries (requires `pyspellchecker`) |
| `AGT_USE_RERANKER` | `false` | Use cross-encoder reranker (requires `sentence-transformers`) |
| `AGT_SUMMARIZATION_USE_LLM` | `true` | Use LLM for paper summaries (false = deterministic truncation) |

### Search Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `AGT_SEMANTIC_SCHOLAR_LIMIT` | `10` | Max results per source per query |
| `AGT_SEARCH_MAX_PAGES` | `1` | Number of result pages to fetch per source (1–5) |
| `AGT_CITATION_THRESHOLD_MOST_CITED` | `10` | Min citations for "most cited" filter |
| `AGT_CITATION_THRESHOLD_GAME_CHANGERS` | `20` | Min citations for "game changers" filter |
| `AGT_CITATION_THRESHOLD_TRENDING` | `5` | Min citations for "trending" filter |
| `AGT_SUMMARIZATION_MAX_SENTENCES` | `4` | Summary length (3–4 sentences) |

### Per-Environment Overrides

Override LLM settings per environment using JSON:

```env
AGT_ENV=staging
AGT_ENV_OVERRIDES={"staging": {"provider": "openai", "model_name": "gpt-4o", "temperature": 0.1}}
```

---

## Troubleshooting

### Startup Failures

**"Missing required field" error:**
Ensure `AGT_XAI_API_KEY`, `AGT_ZOTERO_API_KEY`, and `AGT_ZOTERO_LIBRARY_ID` are set in your `.env` file or exported.

**"Extra field not allowed" error:**
The settings model uses `extra="forbid"`. Check for typos in variable names — all must start with `AGT_` prefix (or use the unprefixed alias).

### Zotero Issues

**Preflight fails with "cannot write":**
Your Zotero API key may not have write permissions. Go to [Zotero API keys](https://www.zotero.org/settings/keys) and ensure "Allow write access" is enabled.

**Library ID not found:**
For personal libraries, your library ID is your Zotero user ID (visible at `https://www.zotero.org/settings/keys`). For group libraries, use the group ID from the URL.

### Search Returns No Results

- Check that your query doesn't have spelling errors (SciAgent currently doesn't auto-correct misspellings)
- Try broader search terms
- If using year constraints (e.g. "2026 papers"), fewer results are expected for recent years
- Enable `AGT_ENABLE_FALLBACK_RETRIEVAL=true` for more source coverage

### Rate Limit Errors

If you see `RateLimitExceededError`, the system has hit the configured per-source rate limit. Options:
- Wait a moment and retry
- Increase the relevant `*_RATE_LIMIT_PER_MINUTE` variable
- Add API keys for rate-limited services (e.g. `AGT_SEMANTIC_SCHOLAR_API_KEY`)

---

## Development

### Running Quality Checks

```bash
# Lint
uv run ruff check .

# Format check
uv run ruff format --check .

# Type check
uv run pyright

# Tests
uv run pytest -q
```

### Running Examples

Each milestone has a runnable demo:

```bash
# M1: Foundation (config, preflight, provider, observability)
uv run python examples/m1_foundation_demo.py

# M2: Retrieval (search, rank, summarize)
uv run python examples/m2_retrieval_demo.py --query "retrieval augmented generation"

# M2.6: Fallback retrieval
uv run python examples/m2_6_fallback_demo.py

# M3: Write correctness (collection resolve, upsert, dedup)
uv run python examples/m3_write_correctness_demo.py

# M4: Approval flow (search → select → approve → write)
uv run python examples/m4_approval_flow_demo.py

# M5: Production hardening (resume, API, failover)
uv run python examples/m5_hardening_demo.py

# M6: Zotero add-on backend contract
uv run python examples/m6_zotero_addon_demo.py
```

### Docker

```bash
# Build
docker build -t sciagent .

# Run (Streamlit UI)
docker run -p 8501:8501 --env-file .env sciagent

# Run (API server)
docker run -p 8000:8000 --env-file .env sciagent \
    uv run uvicorn agt.api.app:app --host 0.0.0.0 --port 8000
```

### Project Structure

```
src/agt/
├── config.py              # Typed settings, validation, secret redaction
├── models.py              # NormalizedPaper, AgentState, WriteResult
├── guardrails.py          # Rate limiting, cost tracking
├── observability.py       # Trace context, spans, structured logging
├── api/app.py             # FastAPI backend (health/run/resume/status)
├── graph/
│   ├── workflow.py        # LangGraph workflow (search/approve/write)
│   └── cli.py             # CLI entrypoint
├── providers/
│   ├── protocol.py        # LLMProvider interface
│   ├── router.py          # Provider routing with failover
│   └── xai.py             # xAI/Grok HTTP adapter
├── tools/
│   ├── search_papers.py   # Multi-source search orchestrator
│   ├── semantic_scholar.py # Semantic Scholar client
│   ├── openalex.py        # OpenAlex client
│   ├── crossref.py        # Crossref client
│   ├── pubmed.py          # PubMed client
│   ├── europe_pmc.py      # Europe PMC client
│   ├── arxiv_api.py       # arXiv client
│   ├── core_ac.py         # CORE client
│   ├── dimensions.py      # Dimensions client
│   ├── google_scholar.py  # Google Scholar (SerpAPI) client
│   ├── opencitations.py   # OpenCitations enrichment
│   ├── ranking.py         # Multi-factor ranking and dedup
│   ├── summarize.py       # Paper summarization
│   ├── query_rewriter.py  # LLM-powered query optimization
│   ├── query_constraints.py # Constraint parsing (year, citations, etc.)
│   ├── keyword_extractor.py # Keyword extraction
│   ├── spell_check.py     # Optional spell checking
│   ├── reranker.py        # Optional cross-encoder reranking
│   └── zotero_upsert.py   # Collection resolve + idempotent upsert
├── ui/app.py              # Streamlit prototype
└── zotero/preflight.py    # Zotero read/write capability check
```
