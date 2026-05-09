# SciAgent — Configuration & Usage Manual

> One document covering installation, configuration, and every way to run SciAgent.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running Locally: Complete Guide](#running-locally-complete-guide)
5. [Other Interfaces](#other-interfaces)
6. [Retrieval Sources](#retrieval-sources)
7. [Advanced Configuration](#advanced-configuration)
8. [Troubleshooting](#troubleshooting)
9. [Development](#development)

---

## Prerequisites

| Requirement    | Version                     | Notes                                                             |
| -------------- | --------------------------- | ----------------------------------------------------------------- |
| Python         | >= 3.13 (recommended: 3.14) | Free-threaded GIL optional support                                |
| `uv`           | latest                      | Package manager ([install](https://astral.sh/uv))                 |
| Node.js        | >= 20                       | Required only for the Zotero add-on package in `zotero-addon/`    |
| Zotero         | 9.x                         | Required for the native add-on scaffold and item-pane integration |
| Zotero account | —                           | With API key and library ID                                       |
| xAI API key    | —                           | Default LLM provider (or OpenAI/Anthropic)                        |

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

### Optional: validate and build the Zotero add-on package

The repository now includes a top-level Zotero 9 add-on scaffold in `zotero-addon/`.

```bash
cd zotero-addon
npm ci
npm run lint
npm run build
```

This produces:

- `zotero-addon/build/xpi/` — staged unpacked add-on contents
- `zotero-addon/build/sciagent-zotero-addon.xpi` — installable unsigned package for local/manual use

### Optional: build the docs site from Markdown

```bash
uv run mkdocs serve -a 127.0.0.1:8001
uv run mkdocs build --strict
```

The workspace includes Markdown authoring helpers in `.vscode/`, including autosave, preview-oriented extensions, reusable tasks, and an MCP browser server for docs QA.

---

## Configuration

All configuration is loaded from environment variables via `pydantic-settings`. You can set values in a `.env` file or export them directly.

### Required Variables

These **must** be set — the application will fail fast with an actionable error if they are missing.

| Variable                | Description                                                           | Example          |
| ----------------------- | --------------------------------------------------------------------- | ---------------- |
| `AGT_XAI_API_KEY`       | xAI (Grok) API key                                                    | `xai-abc123...`  |
| `AGT_ZOTERO_API_KEY`    | Zotero API key ([get one here](https://www.zotero.org/settings/keys)) | `AbCdEf12345...` |
| `AGT_ZOTERO_LIBRARY_ID` | Your Zotero library ID (numeric)                                      | `12345678`       |

### Optional Variables

| Variable                  | Default  | Description                                           |
| ------------------------- | -------- | ----------------------------------------------------- |
| `AGT_ZOTERO_LIBRARY_TYPE` | `user`   | `user` or `group`                                     |
| `AGT_LLM_PROVIDER`        | `xai`    | LLM provider: `xai`, `openai`, `anthropic`, `groq`    |
| `AGT_MODEL_NAME`          | `grok-4` | Model name for the selected provider                  |
| `AGT_TIMEOUT_SECONDS`     | `30`     | LLM call timeout (1–300)                              |
| `AGT_RETRIES`             | `3`      | LLM retry count (0–10)                                |
| `AGT_TEMPERATURE`         | `0.2`    | LLM sampling temperature (0.0–2.0)                    |
| `AGT_LOG_LEVEL`           | `INFO`   | Logging level                                         |
| `AGT_ENV`                 | `local`  | Runtime environment: `local`, `staging`, `production` |

### Optional API Keys (Enhance Retrieval)

These keys are **optional** but improve retrieval coverage and rate limits.

| Variable                       | Service                                 | Free?                   |
| ------------------------------ | --------------------------------------- | ----------------------- |
| `AGT_SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar (higher rate limits)   | Yes                     |
| `AGT_NCBI_API_KEY`             | PubMed / NCBI E-Utilities               | Yes                     |
| `AGT_CORE_API_KEY`             | CORE aggregator                         | Yes (with registration) |
| `AGT_SERPAPI_KEY`              | Google Scholar via SerpAPI              | Paid                    |
| `AGT_DIMENSIONS_KEY`           | Dimensions.ai                           | Paid                    |
| `AGT_OPENAI_API_KEY`           | OpenAI (if using as alternative LLM)    | Paid                    |
| `AGT_ANTHROPIC_API_KEY`        | Anthropic (if using as alternative LLM) | Paid                    |
| `AGT_GROQ_API_KEY`             | Groq (if using as alternative LLM)      | Free tier available     |

### Backend Security

| Variable              | Default | Description                                              |
| --------------------- | ------- | -------------------------------------------------------- |
| `AGT_BACKEND_API_KEY` | None    | If set, all API endpoints require `X-AGT-API-Key` header |

### LLM Provider Routing

| Variable                         | Default | Description                                          |
| -------------------------------- | ------- | ---------------------------------------------------- |
| `AGT_LLM_FALLBACK_PROVIDER`      | None    | Fallback provider on primary failure (e.g. `openai`) |
| `AGT_LLM_FAILOVER_ON_TIMEOUT`    | `true`  | Switch to fallback on timeout                        |
| `AGT_LLM_FAILOVER_ON_RATE_LIMIT` | `true`  | Switch to fallback on rate limit                     |

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

SciAgent has four interfaces:

1. **Command-Line Interface (CLI)** — one-shot search from terminal
2. **Streamlit UI** — interactive web-based approval interface
3. **REST API** — programmatic backend for Zotero add-on and custom clients
4. **Zotero 9 Add-on** — native integration with Zotero desktop client (M6)

---

## Running Locally: Complete Guide

This section walks through the full M6 local development flow: starting the backend, building the add-on, installing it in Zotero 9, and running your first search.

### Step 1: Start the Backend API

The backend must be running before using the Zotero add-on.

```bash
cd /path/to/sciagent

# Ensure dependencies are installed
uv sync

# Verify .env file has required keys
# AGT_XAI_API_KEY, AGT_ZOTERO_API_KEY, AGT_ZOTERO_LIBRARY_ID

# Start the API server
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
```

**Expected output:**

```text
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**Verify health:**

```bash
curl http://localhost:8000/health
```

Should return JSON with `"status": "ok"` and Zotero preflight details.

**Common issues:**

- `Missing required field`: Check `.env` has `AGT_XAI_API_KEY`, `AGT_ZOTERO_API_KEY`, and `AGT_ZOTERO_LIBRARY_ID`
- `Address already in use`: Another process is using port 8000; kill it or use `--port 8001`
- `Preflight failed`: Zotero API key may be invalid or lack write permissions

---

### Step 2: Build the Zotero Add-on

```bash
cd zotero-addon

# Install Node.js dependencies (first time only)
npm ci

# Build the XPI package
npm run build
```

**Build outputs:**

- `zotero-addon/build/xpi/` — unpacked add-on contents
- `zotero-addon/build/sciagent-zotero-addon.xpi` — installable package

**Verify build succeeded:**

```bash
ls -lh build/sciagent-zotero-addon.xpi
```

Should show a file around 50-100 KB.

---

### Step 3: Install the Add-on in Zotero 9

**⚠️ Important for macOS users:**

Do **NOT** double-click the XPI file or use "Open With" → Zotero. macOS will attempt to extract it as an archive instead of installing it as an add-on.

**Correct installation method (all platforms):**

1. Open Zotero 9
2. Go to **Tools → Add-ons** (or **Preferences → Plugins** in some Zotero builds)
3. Click the gear icon (⚙️) in the top-right
4. Select **Install Add-on From File...**
5. Navigate to `sciagent/zotero-addon/build/sciagent-zotero-addon.xpi`
6. Click **Open**

**Expected result:**

- SciAgent appears in the add-ons list with version `0.1.0`
- Status shows "Enabled"
- A restart prompt may appear; restart Zotero if requested

**Troubleshooting:**

- **"The add-on ... could not be installed. It may be incompatible with this version of Zotero."**:
  1. Rebuild the XPI: `cd zotero-addon && npm run build`
  2. Verify your Zotero version: **Help → About Zotero**. The add-on requires Zotero 9.0.0 or higher.
  3. Check the manifest in the XPI: `unzip -p build/sciagent-zotero-addon.xpi manifest.json | grep strict_`
     - `strict_min_version` should be `"9.0.0"`
     - `strict_max_version` should be `"9.*"` to accept all Zotero 9.x versions
  4. If you previously installed an incompatible version, uninstall it completely and restart Zotero before reinstalling
- **"This add-on could not be installed"** (generic): XPI may be corrupted; rebuild with `npm run build`
- **"Requires restart"**: Restart Zotero and verify add-on appears in Tools → Add-ons
- **Add-on not visible after installation**: Check Zotero version is 9.x. Zotero 7 and earlier are not supported.

---

### Step 4: Configure Add-on Preferences

After installation, configure the backend connection:

1. In Zotero, go to **Tools → Add-ons**
2. Find **SciAgent** in the list
3. Click the **Preferences** button (or gear icon → Preferences)
4. Set the following:
   - **Backend URL**: `http://localhost:8000`
   - **API Key**: (leave empty if `AGT_BACKEND_API_KEY` is not set; otherwise enter your backend key)
   - **Client ID**: Any identifier, e.g., `user-1` (used for workflow isolation)
   - **Include PDFs**: Placeholder toggle (not yet implemented in backend)

5. Click **Save**

**Preferences are stored locally** and persist across Zotero restarts.

---

### Step 5: Run Your First Search

1. In Zotero, open the **SciAgent item pane section**:
   - The pane should appear in the right sidebar when viewing your library
   - If not visible, check View → Layout or right-click the item pane header

2. **Backend health indicator** (top of pane):
   - Should show **green/connected** if backend is running
   - If red, check backend is running on `http://localhost:8000`

3. **Enter a query**:
   - Example: `retrieval augmented generation`

4. **Set a collection name**:
   - Example: `RAG Papers`
   - The collection will be created if it doesn't exist

5. **Click "Run Search"**

6. **Review parsed filters**:
   - The backend's search plan appears: year range, exclude terms, source policy, preferences
   - This is the contract the backend will execute

7. **(Optional) Edit filters**:
   - Modify year range, add exclude terms, toggle open access, adjust preferences
   - Click "Re-run with Edits" to execute the modified plan

8. **Review results**:
   - Papers appear with titles, authors, year, citations, summary
   - Each paper has a checkbox for selection

9. **Select papers**:
   - Check/uncheck papers you want to add to Zotero
   - Default: all papers selected

10. **Approve or Reject**:
    - **Approve**: Writes selected papers to your Zotero library
    - **Reject**: Discards results without writing

11. **View write results**:
    - Each paper shows status: `created`, `unchanged` (already exists), or `failed`
    - Failed writes include error messages

12. **Verify in Zotero**:
    - Navigate to the target collection
    - Papers should appear with full metadata (title, authors, year, DOI, abstract)

---

### Step 6: Smoke Test Checklist

Before marking M6 complete, verify the following in a live Zotero 9 session:

- [ ] Backend starts without errors: `uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000`
- [ ] Add-on builds cleanly: `npm run build` in `zotero-addon/`
- [ ] XPI installs via Zotero's add-ons manager (not double-click on macOS)
- [ ] Add-on appears in Tools → Add-ons with version 0.1.0
- [ ] Preferences pane opens and saves settings
- [ ] SciAgent item pane section is visible in Zotero
- [ ] Backend health indicator shows green/connected
- [ ] Search query and collection inputs accept text
- [ ] "Run Search" executes without errors
- [ ] Parsed filters render correctly (year, exclude terms, sources, preferences)
- [ ] Filter editor controls allow edits
- [ ] "Re-run with Edits" re-executes with modified plan
- [ ] Result list displays with titles, authors, summaries, citations
- [ ] Selection checkboxes work for individual papers
- [ ] "Approve" writes selected papers to Zotero collection
- [ ] Write results render with `created`/`unchanged`/`failed` status
- [ ] Items appear in target collection with correct metadata
- [ ] "Reject" discards results without writing
- [ ] Preferences persist across Zotero restarts
- [ ] Add-on uninstalls cleanly via Tools → Add-ons

**Current M6 status:**

- ✅ Backend, add-on build, and package quality gates passing
- ❌ Live Zotero 9 desktop smoke test not yet performed
- ❌ M6 not marked complete until manual validation passes

---

## Other Interfaces

### Option 1: Command-Line Interface

Run a single search workflow from the terminal for quick testing or scripting:

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

**Use case:** Batch processing, CI integration, or quick validation without UI.

---

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

**Use case:** Interactive exploration and manual review workflow.

---

### Option 3: REST API (Programmatic)

The FastAPI backend is the foundation for the Zotero add-on and can be used programmatically.

**Start the server:**

```bash
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
```

**Endpoints:**

- `GET /health` — system health and Zotero preflight
- `POST /run` — start a search workflow
- `GET /status/{run_id}` — retrieve workflow state
- `POST /resume` — approve or reject with selection

**Use case:** Custom integrations, automation, or embedding SciAgent in other tools.

**Full API documentation:** See [API Reference](api.md) for request/response schemas, authentication, and client examples.

---

## REST API Reference

For detailed API documentation, request/response schemas, authentication, and client examples, see [API Reference](api.md).

**Quick summary:**

- `GET /health` — system health and Zotero preflight
- `POST /run` — start a search workflow
- `GET /status/{run_id}` — retrieve workflow state and papers
- `POST /resume` — approve or reject with selection

All endpoints support optional authentication via `X-AGT-API-Key` and `X-AGT-Client-ID` headers.

---

## Retrieval Sources

SciAgent searches across multiple academic databases simultaneously and merges results with deduplication.

### Always Available (No Key Required)

| Source               | Coverage            | Notes                                                   |
| -------------------- | ------------------- | ------------------------------------------------------- |
| **Semantic Scholar** | 200M+ papers        | No-key mode by default; optional key raises rate limits |
| **OpenAlex**         | 250M+ works         | Open bibliographic data                                 |
| **Crossref**         | 130M+ records       | DOI metadata, publisher data                            |
| **PubMed**           | 36M+ biomedical     | NCBI E-Utilities                                        |
| **Europe PMC**       | 43M+ life sciences  | Open access indicator                                   |
| **arXiv**            | 2.4M+ preprints     | Physics, CS, math, etc.                                 |
| **BASE**             | 400M+ records       | Open academic search index                              |
| **OpenCitations**    | Citation enrichment | Adds citation counts                                    |

### Require API Key

| Source             | Key Variable         | Notes                      |
| ------------------ | -------------------- | -------------------------- |
| **CORE**           | `AGT_CORE_API_KEY`   | Full-text aggregator       |
| **Dimensions**     | `AGT_DIMENSIONS_KEY` | Comprehensive metadata     |
| **Google Scholar** | `AGT_SERPAPI_KEY`    | Via SerpAPI (experimental) |

### How Search Works

1. The query is parsed into a deterministic search plan: topic terms, hard filters, soft preferences, and source policy
2. The LLM may rewrite topic wording for better academic search coverage, but it cannot remove or loosen hard filters
3. Keyless/easy-access sources are queried in parallel by default; keyed search sources are optional enrichment
4. Results are deduplicated (DOI + arXiv ID + title hash)
5. Hard filters are applied before ranking, including year filters, date ranges, citation thresholds, source filters, and exclude terms
6. Papers are ranked by a multi-factor formula: semantic relevance (45%), citations (30%), influential citations (10%), recency (12%), abstract quality (5%), open access (3%)
7. LLM validates result relevance and retries with improved topic wording if needed

### Deterministic Search Filters

SciAgent treats filters as structured constraints, not just semantic hints. For example:

| Query phrase            | Parsed filter                             |
| ----------------------- | ----------------------------------------- |
| `not older than 2024`   | `min_year = 2024`                         |
| `between 2022 and 2024` | `min_year = 2022`, `max_year = 2024`      |
| `not about healthcare`  | `exclude_terms = ["healthcare"]`          |
| `open access only`      | `open_access = true`                      |
| `most cited`            | `min_citations` from configured threshold |

The app and Zotero add-on should show these filters as editable controls before approval so users can verify exactly what will be searched and written.

### Query Examples

| Natural Language Query                                                                      | What Happens                                                                          |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `"retrieval augmented generation"`                                                          | Direct keyword search across all sources                                              |
| `"most cited 2020+ timeseries papers"`                                                      | Extracts `year >= 2020`, citation filter, searches "timeseries"                       |
| `"time-series forecasting methods selection based on the data itself, not older than 2024"` | Extracts `min_year = 2024`, searches method/model selection from data characteristics |
| `"RAG techniques not about healthcare"`                                                     | Searches "RAG", excludes papers mentioning "healthcare"                               |
| `"deep RL robotics between 2022 and 2024"`                                                  | Year range 2022–2024, keywords "deep reinforcement learning robotics"                 |
| `"nutrition in sport"`                                                                      | LLM rewrites to "sports nutrition" for better API coverage                            |

---

## Advanced Configuration

### Rate Limits

Each retrieval source has a configurable rate limit (requests per minute per thread):

| Variable                                     | Default |
| -------------------------------------------- | ------- |
| `AGT_SEMANTIC_SCHOLAR_RATE_LIMIT_PER_MINUTE` | 100     |
| `AGT_OPENALEX_RATE_LIMIT_PER_MINUTE`         | 100     |
| `AGT_CROSSREF_RATE_LIMIT_PER_MINUTE`         | 80      |
| `AGT_PUBMED_RATE_LIMIT_PER_MINUTE`           | 100     |
| `AGT_EUROPE_PMC_RATE_LIMIT_PER_MINUTE`       | 100     |
| `AGT_CORE_RATE_LIMIT_PER_MINUTE`             | 60      |
| `AGT_ARXIV_RATE_LIMIT_PER_MINUTE`            | 20      |
| `AGT_OPENCITATIONS_RATE_LIMIT_PER_MINUTE`    | 60      |
| `AGT_ZOTERO_RATE_LIMIT_PER_MINUTE`           | 60      |
| `AGT_LLM_RATE_LIMIT_PER_MINUTE`              | 120     |

### Cost Guardrails

| Variable                                | Default | Description                         |
| --------------------------------------- | ------- | ----------------------------------- |
| `AGT_WORKFLOW_MAX_COST_USD`             | `0.50`  | Maximum LLM spend per workflow run  |
| `AGT_XAI_INPUT_COST_PER_1K_TOKENS_USD`  | `0.005` | Cost tracking for xAI input tokens  |
| `AGT_XAI_OUTPUT_COST_PER_1K_TOKENS_USD` | `0.015` | Cost tracking for xAI output tokens |

### Feature Flags

| Variable                        | Default | Description                                                     |
| ------------------------------- | ------- | --------------------------------------------------------------- |
| `AGT_ENABLE_FALLBACK_RETRIEVAL` | `false` | Enable fallback sources when primary returns few results        |
| `AGT_USE_KEYBERT`               | `false` | Use KeyBERT for keyword extraction (requires `keybert` package) |
| `AGT_USE_SPELL_CHECK`           | `false` | Enable spell checking on queries (requires `pyspellchecker`)    |
| `AGT_USE_RERANKER`              | `false` | Use cross-encoder reranker (requires `sentence-transformers`)   |
| `AGT_SUMMARIZATION_USE_LLM`     | `true`  | Use LLM for paper summaries (false = deterministic truncation)  |

### Search Tuning

| Variable                               | Default | Description                                      |
| -------------------------------------- | ------- | ------------------------------------------------ |
| `AGT_SEMANTIC_SCHOLAR_LIMIT`           | `10`    | Max results per source per query                 |
| `AGT_SEARCH_MAX_PAGES`                 | `1`     | Number of result pages to fetch per source (1–5) |
| `AGT_CITATION_THRESHOLD_MOST_CITED`    | `10`    | Min citations for "most cited" filter            |
| `AGT_CITATION_THRESHOLD_GAME_CHANGERS` | `20`    | Min citations for "game changers" filter         |
| `AGT_CITATION_THRESHOLD_TRENDING`      | `5`     | Min citations for "trending" filter              |
| `AGT_SUMMARIZATION_MAX_SENTENCES`      | `4`     | Summary length (3–4 sentences)                   |

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
# Python backend
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none
```

```bash
# Zotero add-on
cd zotero-addon
npm ci
npm run lint
npm run build
npm run typecheck
npm run test
cd ..
```

```bash
# Docs and agent instructions
npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" "examples/**/*.md" ".github/**/*.md" "zotero-addon/README.md"
uv run mkdocs build --strict
```

`pre-commit` stays intentionally lightweight and Python-only.

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

The real add-on scaffold lives in `zotero-addon/` and packages a Zotero 9 add-on with:

- `manifest.json` + `bootstrap.js`
- typed backend client for `/health`, `/run`, `/status/{run_id}`, `/resume`
- native item-pane section + preference pane registration boundaries
- React MVP for query, parsed filter review/edit, selection, approval, reject, and result rendering

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
