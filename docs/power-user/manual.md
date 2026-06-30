# SciAgent — Configuration & Usage Manual

> One document covering installation, configuration, and every way to run SciAgent.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running Locally: Complete Guide](#running-locally-complete-guide)
5. [Standalone Binary](#standalone-binary)
6. [Other Interfaces](#other-interfaces)
7. [Retrieval Sources](#retrieval-sources)
8. [Advanced Configuration](#advanced-configuration)
9. [Troubleshooting](#troubleshooting)
10. [Development](#development)

---

## Prerequisites

| Requirement    | Version                     | Notes                                                          |
| -------------- | --------------------------- | -------------------------------------------------------------- |
| Python         | >= 3.13 (recommended: 3.14) | Free-threaded GIL optional support                             |
| `uv`           | latest                      | Package manager ([install](https://astral.sh/uv))              |
| Node.js        | >= 20                       | Required only for the Zotero add-on package in `zotero-addon/` |
| Zotero         | 9.x                         | Required for the native add-on's main-window workflow          |
| Zotero account | —                           | With API key and library ID                                    |
| OpenAI API key | —                           | Default first-run LLM path; Anthropic or xAI also work         |

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

The repo config installs both `pre-commit` and `pre-push` hooks with that single command.

### Option A: Install the Add-on from GitHub Releases (end-user path)

If a pre-built release exists, skip the source build entirely:

1. Go to the [GitHub Releases page](https://github.com/AdamKrysztopa/sciagent/releases)
2. Download `sciagent-zotero-addon.xpi` from the latest release
3. In Zotero 9: **Tools → Add-ons → gear icon → Install Add-on From File...**
4. Select the downloaded XPI

The add-on will self-update automatically: Zotero polls
`https://raw.githubusercontent.com/AdamKrysztopa/sciagent/main/zotero-addon/update.rdf`
on each startup and prompts when a new version is available.

### Option B: Build and validate the Zotero add-on from source (developer path)

The repository includes a Zotero 9 add-on in `zotero-addon/`.

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
| `AGT_ZOTERO_API_KEY`    | Zotero API key ([get one here](https://www.zotero.org/settings/keys)) | `AbCdEf12345...` |
| `AGT_ZOTERO_LIBRARY_ID` | Your Zotero library ID (numeric)                                      | `12345678`       |

You must also set at least one LLM key. The auto-detect priority is OpenAI → Anthropic → xAI → Groq.
Alternatively, use Ollama (no key) or any OpenAI-compatible endpoint:

| Variable                | Description                                                     | Example                        |
| ----------------------- | --------------------------------------------------------------- | ------------------------------ |
| `AGT_OPENAI_API_KEY`    | Default first-run OpenAI API key                                | `sk-abc123...`                 |
| `AGT_ANTHROPIC_API_KEY` | Anthropic API key                                               | `sk-ant-abc123...`             |
| `AGT_XAI_API_KEY`       | xAI (Grok) API key                                              | `xai-abc123...`                |
| `AGT_GROQ_API_KEY`      | Groq API key (free tier available)                              | `gsk_abc123...`                |
| `AGT_LLM_API_KEY`       | API key for a custom OpenAI-compatible endpoint (SCI-0601)      | `ds-abc123...`                 |
| `AGT_LLM_BASE_URL`      | Base URL for OpenAI-compatible endpoint; triggers auto-detect   | `https://api.deepseek.com/v1`  |

### Optional Variables

| Variable                    | Default           | Description                                                                             |
| --------------------------- | ----------------- | --------------------------------------------------------------------------------------- |
| `AGT_ZOTERO_LIBRARY_TYPE`   | `user`            | `user` or `group`                                                                       |
| `AGT_LLM_PROVIDER`          | `auto-detect`     | Explicit provider override. Values: `openai`, `anthropic`, `xai`, `groq`, `ollama`, `openai-compatible` |
| `AGT_LLM_MODEL`             | provider-specific | Model name for Ollama or custom endpoint (alias for `AGT_MODEL_NAME`)                   |
| `AGT_MODEL_NAME`            | provider-specific | Optional model override. Defaults to the selected provider's built-in model             |
| `AGT_DATA_DIR`              | `~/.sciagent`     | Root data directory for sessions, cache, and watch files (SCI-0604)                     |
| `AGT_TIMEOUT_SECONDS`       | `30`              | LLM call timeout (1–300)                                                                |
| `AGT_RETRIES`               | `3`               | LLM retry count (0–10)                                                                  |
| `AGT_TEMPERATURE`           | `0.2`             | LLM sampling temperature (0.0–2.0)                                                      |
| `AGT_LOG_LEVEL`             | `INFO`            | Logging level                                                                           |
| `AGT_ENV`                   | `local`           | Runtime environment: `local`, `staging`, `production`                                   |
| `AGT_MAILTO`                | —                 | Your email for the OpenAlex/Crossref/DOAJ "polite pool" — improves rate limits           |
| `AGT_DISABLED_PROVIDERS`    | `[]`              | JSON array of provider names to disable regardless of key availability, e.g. `["base"]` |

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

| Variable                   | Default      | Description                                                    |
| -------------------------- | ------------ | -------------------------------------------------------------- |
| `AGT_BACKEND_API_KEY`      | None         | If set, all API endpoints require `X-AGT-API-Key` header       |
| `AGT_CORS_ALLOWED_ORIGINS` | `["*"]`      | JSON array of allowed CORS origins. Use `["*"]` for local use. |
| `AGT_API_RATE_LIMIT`       | `200/minute` | Global HTTP rate limit per IP (slowapi format).                |

See [docs/reference/security.md](../reference/security.md) for the full security checklist.

### LLM Provider Routing

| Variable                         | Default | Description                                          |
| -------------------------------- | ------- | ---------------------------------------------------- |
| `AGT_LLM_FALLBACK_PROVIDER`      | None    | Fallback provider on primary failure (e.g. `openai`) |
| `AGT_LLM_FAILOVER_ON_TIMEOUT`    | `true`  | Switch to fallback on timeout                        |
| `AGT_LLM_FAILOVER_ON_RATE_LIMIT` | `true`  | Switch to fallback on rate limit                     |

### Supported LLM Providers

| Provider name        | Requires key  | How to enable                                                     |
| -------------------- | ------------- | ----------------------------------------------------------------- |
| `openai`             | Yes           | Set `AGT_OPENAI_API_KEY` (auto-detected)                          |
| `anthropic`          | Yes           | Set `AGT_ANTHROPIC_API_KEY` (auto-detected)                       |
| `xai`                | Yes           | Set `AGT_XAI_API_KEY` (auto-detected)                             |
| `groq`               | Yes (free)    | Set `AGT_GROQ_API_KEY` (auto-detected)                            |
| `ollama`             | No            | `AGT_LLM_PROVIDER=ollama` — runs against `localhost:11434/v1`     |
| `openai-compatible`  | Optional      | Set `AGT_LLM_BASE_URL`; key via `AGT_LLM_API_KEY` if required    |

**Ollama (fully offline):**

```env
AGT_LLM_PROVIDER=ollama
AGT_LLM_MODEL=llama3.2
```

**DeepSeek / Together AI / LM Studio (any OpenAI-compatible endpoint):**

```env
AGT_LLM_PROVIDER=openai-compatible
AGT_LLM_BASE_URL=https://api.deepseek.com/v1
AGT_LLM_API_KEY=your-deepseek-key
AGT_LLM_MODEL=deepseek-chat
```

Setting `AGT_LLM_BASE_URL` without an explicit `AGT_LLM_PROVIDER` also triggers auto-detection of `openai-compatible`.

### Embedded Server CLI (SCI-0604)

The package ships a `sciagent-server` CLI that wraps uvicorn. It is the entrypoint the Zotero
add-on spawns as a subprocess when the embedded binary is used.

```bash
# Start on the default port (57321)
uv run sciagent-server

# Custom port and data directory
uv run sciagent-server --port 57321 --data-dir ~/.sciagent --log-level info

# Check version
uv run sciagent-server --version
```

Setting `--data-dir` overrides `AGT_DATA_DIR` so sessions, cache, and watches resolve under that
directory. This is how the Zotero add-on isolates the data location from the system default.

### Example `.env` File

```env
# Required
AGT_OPENAI_API_KEY=sk-your-openai-key
AGT_ZOTERO_API_KEY=your-zotero-api-key
AGT_ZOTERO_LIBRARY_ID=12345678
AGT_ZOTERO_LIBRARY_TYPE=user

# Optional alternatives
# AGT_ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
# AGT_XAI_API_KEY=xai-your-key-here

# Optional explicit routing
# AGT_LLM_PROVIDER=openai
# AGT_MODEL_NAME=gpt-5.4
AGT_TEMPERATURE=0.2

# Ollama (no key needed)
# AGT_LLM_PROVIDER=ollama
# AGT_LLM_MODEL=llama3.2

# Custom OpenAI-compatible endpoint
# AGT_LLM_PROVIDER=openai-compatible
# AGT_LLM_BASE_URL=https://api.deepseek.com/v1
# AGT_LLM_API_KEY=ds-your-key
# AGT_LLM_MODEL=deepseek-chat

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

SciAgent has four interfaces, but only one primary researcher path:

1. **Zotero 9 Add-on** — primary researcher interface inside Zotero
2. **Streamlit UI** — prototype and support surface for local demos
3. **REST API** — developer and support backend contract for custom clients
4. **Command-Line Interface (CLI)** — developer and support terminal runner

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
# One LLM key: AGT_OPENAI_API_KEY or AGT_ANTHROPIC_API_KEY or AGT_XAI_API_KEY
# Plus: AGT_ZOTERO_API_KEY and AGT_ZOTERO_LIBRARY_ID

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

Should return JSON with `"ok": true`, the resolved provider name, and Zotero preflight details.

**Common issues:**

- `Missing required field`: Check `.env` has one LLM key (`AGT_OPENAI_API_KEY`, `AGT_ANTHROPIC_API_KEY`, or `AGT_XAI_API_KEY`) plus `AGT_ZOTERO_API_KEY` and `AGT_ZOTERO_LIBRARY_ID`
- `Address already in use`: Another process is using port 8000; kill it or use `--port 8001`
- `Preflight failed`: Zotero API key may be invalid or lack write permissions

### Alternative: Run with Docker Compose

If you prefer Docker over a native Python install:

```bash
# Build and start backend
docker compose up --build -d

# Verify
curl http://localhost:8000/health
```

This uses `docker-compose.yml` in the repo root. Edit `.env` first — the compose file mounts it
directly. Persistent data (`~/.sciagent/sessions`, watches, cache) is bind-mounted automatically.

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

### Zotero Add-on Compatibility

| Status      | Versions             | Notes                                                                 |
| ----------- | -------------------- | --------------------------------------------------------------------- |
| Tested      | 9.0.0-9.\* packaging | `manifest.json`, `update.rdf`, and `npm run build` align in this repo |
| Expected    | Zotero 9.x runtime   | Supported target, but live desktop validation is still manual         |
| Unsupported | < 9.0.0 or > 9.x     | Not claimed; add-on metadata rejects these versions                   |

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

- SciAgent appears in the add-ons list with version `0.2.0`
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

1. In Zotero, open the **SciAgent main workspace** from **Tools → SciAgent**.
   - This is the primary workflow surface.
   - If your build still registers an item-pane section, treat it as a secondary launcher into the same product path rather than the main UI.

2. **Backend health indicator** (top of workspace):
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

Verified 2026-05-12 on Zotero 9.x with both `uvicorn` and Docker container backends.

- [x] Backend starts without errors: `uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000`
- [x] Add-on builds cleanly: `npm run build` in `zotero-addon/`
- [x] XPI installs via Zotero's add-ons manager (not double-click on macOS)
- [x] Add-on appears in Tools → Add-ons with version 0.2.0
- [x] Preferences pane opens and saves settings
- [x] **Tools → SciAgent** opens the main-window workspace
- [x] Backend health indicator shows green/connected in the main-window workspace
- [x] If the item-pane section is present, it behaves as a secondary launcher only
- [x] Search query and collection inputs accept text
- [x] "Run Search" executes without errors
- [x] Parsed filters render correctly (year, exclude terms, sources, preferences)
- [x] Filter editor controls allow edits
- [x] "Re-run with Edits" re-executes with modified plan
- [x] Result list displays with titles, authors, summaries, citations
- [x] Selection checkboxes work for individual papers
- [x] "Approve" writes selected papers to Zotero collection
- [x] Write results render with `created`/`unchanged`/`failed` status
- [x] Items appear in target collection with correct metadata
- [x] "Reject" discards results without writing
- [x] Preferences persist across Zotero restarts
- [x] Add-on uninstalls cleanly via Tools → Add-ons

**M6 status: ✅ Complete (2026-05-12)**

- ✅ Backend, add-on build, and package quality gates passing
- ✅ Add-on metadata consistently targets Zotero 9.x packaging
- ✅ Live Zotero 9 desktop smoke test passed — both `uvicorn` and Docker container backends confirmed
- ✅ M6 signed off

---

## Standalone Binary

The repo ships a PyInstaller build that packages the entire Python backend into a single
executable. No Python install is required at runtime — the binary bundles all dependencies.

The Zotero add-on spawns this binary automatically. End users never run it directly.
Developers and CI use it to verify the frozen artifact before publishing a release.

### What It Is

`sciagent-server` is the same `agt.api.app` FastAPI application, frozen by PyInstaller.
It accepts identical CLI flags and exposes the same REST API as the dev server started
via `uv run uvicorn`.

### Build Requirements

| Requirement | Notes                                      |
| ----------- | ------------------------------------------ |
| `uv`        | Must be installed (see Prerequisites)      |
| UPX         | Optional; reduces binary size by ~30–40%   |
| ~5 min      | First build (subsequent builds are faster) |

Install UPX before building if you want the smaller artifact:

```bash
# macOS
brew install upx

# Ubuntu / Debian
sudo apt-get install upx

# Windows
choco install upx -y
```

### Build Command

From the repository root:

```bash
uv run pyinstaller build/sciagent-server.spec \
  --distpath build/dist \
  --workpath build/work \
  --clean
```

**Verified output (macOS arm64, 2026-05-12):**

```text
37 MB  build/dist/sciagent-server  (Mach-O 64-bit arm64, UPX-compressed)
```

The binary is written to `build/dist/sciagent-server` (or `.exe` on Windows). The
`build/work/` directory contains intermediate artifacts and can be ignored.

### Verify the Binary Works

```bash
# Version check (no credentials needed)
./build/dist/sciagent-server --version
# → sciagent-server 0.2.0

# Start on a test port — no credentials means ok:false body but HTTP 200
./build/dist/sciagent-server --port 58000 &
sleep 2
curl http://127.0.0.1:58000/health
# → {"ok": false, "provider": "openai", "can_read": false, ...}
kill %1

# Start with credentials loaded from .env
env $(grep -v '^#' .env | xargs) ./build/dist/sciagent-server --port 57321 &
sleep 2
curl http://127.0.0.1:57321/health
# → {"ok": true, "can_read": true, "can_write": true, "key_valid": true, ...}

# Full workflow — requires Zotero + LLM credentials in .env
curl -s -X POST http://127.0.0.1:57321/run \
  -H "Content-Type: application/json" \
  -d '{"query": "retrieval augmented generation 2024+", "collection_name": "RAG"}' | python3 -m json.tool
# → {"run_id": "...", "status": "awaiting_approval", ...}

kill %1
```

Health returns HTTP 200 regardless of whether credentials are present. The `ok` field
in the body indicates credential validity, not server liveness — CI smoke tests that
use `curl -f` (check HTTP status only) will pass even without credentials.

### macOS Gatekeeper

The binary is unsigned. On first launch, macOS blocks it:

> "sciagent-server" can't be opened because Apple cannot check it for malicious
> software.

**Workaround (Finder):** Right-click the binary → Open → confirm once. From then on
macOS runs it without prompting.

**Workaround (Terminal):** Clear the quarantine attribute before running:

```bash
xattr -d com.apple.quarantine build/dist/sciagent-server
```

This is a development/beta limitation. Production releases will be codesigned with an
Apple Developer ID (tracked as OPN-03 / ZAP-11).

### How the Zotero Add-on Uses It

When the add-on is in local-backend mode, `serverManager.ts` handles the full lifecycle:

1. **Zotero starts** — checks `~/.sciagent/bin/sciagent-server-<platform>` exists
2. **First run** — shows a download dialog; fetches the platform binary from the GitHub
   Release and marks it executable
3. **Spawn** — calls `Subprocess.call()` with `--port 57321 --data-dir ~/.sciagent`
   and all provider env vars from Zotero preferences
4. **Health poll** — polls `/health` every 300 ms for up to 15 s; shows a visible error
   if the server does not start in time
5. **Zotero shuts down** — calls `_proc.kill()`

Provider credentials pass to the binary as environment variables:

| Env var              | Source                            |
| -------------------- | --------------------------------- |
| `OPENAI_API_KEY`     | Zotero pref `openai_api_key`      |
| `ANTHROPIC_API_KEY`  | Zotero pref `anthropic_api_key`   |
| `XAI_API_KEY`        | Zotero pref `xai_api_key`         |
| `GROQ_API_KEY`       | Zotero pref `groq_api_key`        |
| `AGT_LLM_PROVIDER`   | Zotero pref `llmProvider`         |
| `AGT_LLM_BASE_URL`   | Zotero pref `llmBaseUrl`          |
| `AGT_LLM_MODEL`      | Zotero pref `llmModel`            |

The binary reads these the same way it reads `.env` — pydantic-settings checks the
process environment before falling back to `.env`.

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

**Full API documentation:** See [API Reference](../reference/api.md) for request/response schemas, authentication, and client examples.

---

### Option 4: MCP Server (AI Agent Integration)

SciAgent exposes a read-only [Model Context Protocol](https://modelcontextprotocol.io) server for
use by AI coding assistants (Claude Code, Cursor, etc.).

**Start the server:**

```bash
uv run python -m agt.mcp_server
```

**Available tools (read-only):**

| Tool             | Description                                                      |
| ---------------- | ---------------------------------------------------------------- |
| `search_papers`  | Run a paper search and return ranked results as JSON             |
| `list_watches`   | List all saved watch queries                                     |
| `get_session`    | Retrieve a saved session by ID                                   |
| `library_doctor` | Scan a Zotero collection for missing DOI/abstract/PDF/duplicates |

Write operations are intentionally excluded — the approval-gate invariant is preserved.

**Wire into Claude Code (`.claude/settings.json` or MCP client config):**

```json
{
  "mcpServers": {
    "sciagent": {
      "command": "uv",
      "args": ["run", "python", "-m", "agt.mcp_server"],
      "cwd": "/path/to/sciagent"
    }
  }
}
```

**Use case:** Ask your AI assistant "search for recent papers on RAG" and get results directly in
your coding session without leaving the editor.

---

## REST API Reference

For detailed API documentation, request/response schemas, authentication, and client examples, see [API Reference](../reference/api.md).

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
| **DOAJ**             | 9M+ OA articles     | Directory of Open Access Journals; all results are OA   |
| **OpenCitations**    | Citation enrichment | Adds citation counts and citation graph expansion       |

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

### Search Depth

Use the **depth selector** in the sidebar or `AGT_SEARCH_DEPTH` env var to control breadth vs. speed:

| Depth      | Providers queried                                   | Results/provider | Ref expansion |
| ---------- | --------------------------------------------------- | ---------------- | ------------- |
| `quick`    | OpenAlex, arXiv                                     | 10               | off           |
| `balanced` | + Crossref, Europe PMC, DOAJ, PubMed                | 25               | off           |
| `deep`     | + Semantic Scholar, CORE, BASE, OpenCitations       | 50               | on            |

The sidebar shows a depth plan preview — which providers will run — before you start the search.

### Provider Coverage Panel

The sidebar's **Coverage** panel (populated from `GET /providers`) shows:

- Each provider's capability matrix (which fields it can return)
- Runtime health (available / rate-limited / failed / disabled)
- BYOK hints: providers that need a key display an upgrade chip with the env var to set

### Result Provenance

Every result card shows:

- **Source chips** — which providers contributed to this merged record (e.g. `openalex • crossref`)
- **Missing-field tooltips** — hover the "ⓘ" icon next to an empty field for the reason: provider
  didn't return it, no queried provider supports it, a key is missing, or the current depth skipped it
- **Conflict dot** — a red dot means two providers disagreed on a field value. The approval dialog
  shows each conflict and asks for explicit confirmation before writing to Zotero

### Author Search and Citation Graph

**Author-scoped search:** Queries like "papers by Karpathy 2023" resolve the author via OpenAlex
and Semantic Scholar, then filter results to that author's resolved IDs. Author chips in result
cards are tappable to trigger a new scoped search.

**Citation graph expansion:** Queries like "papers citing Attention Is All You Need" use
`SearchPlan.seed_dois` to fan out via OpenCitations and Semantic Scholar. Result cards show a
directional badge (`↓ ref` / `↑ cites`) to indicate how the paper was found.

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

| Variable                        | Default | Description                                                                                               |
| ------------------------------- | ------- | --------------------------------------------------------------------------------------------------------- |
| `AGT_ENABLE_FALLBACK_RETRIEVAL` | `false` | Enable fallback sources when primary returns few results                                                  |
| `AGT_USE_KEYBERT`               | `false` | Retired experimental flag; benchmarked worse than default, so leave disabled                              |
| `AGT_USE_SPELL_CHECK`           | `false` | Experimental typo-correction flag; keep disabled until a typo-focused benchmark exists                    |
| `AGT_USE_RERANKER`              | `false` | Positive experimental reranker (requires `sentence-transformers`); useful opt-in, not a P1 exit by itself |
| `AGT_SUMMARIZATION_USE_LLM`     | `true`  | Use LLM for paper summaries (false = deterministic truncation)                                            |

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
Ensure one LLM key (`AGT_OPENAI_API_KEY`, `AGT_ANTHROPIC_API_KEY`, or `AGT_XAI_API_KEY`) plus `AGT_ZOTERO_API_KEY` and `AGT_ZOTERO_LIBRARY_ID` are set in your `.env` file or exported.

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

Commit-time hooks stay fast, and `pre-push` runs the full Python, Zotero add-on, and docs gates before push.

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

The real add-on scaffold lives in `zotero-addon/` and packages the primary Zotero 9 interface with:

- `manifest.json` + `bootstrap.js`
- typed backend client for `/health`, `/run`, `/status/{run_id}`, `/resume`
- native main-window workspace + preference pane registration boundaries
- optional item-pane registration as a secondary launcher
- React MVP for query, parsed filter review/edit, selection, approval, reject, and result rendering

### Publishing a Release

The CI workflow `build-binaries.yml` builds all artifacts and publishes a GitHub Release when
a tag matching `v*` is pushed. Steps:

1. **Bump versions** — update `manifest.json` and `package.json` in `zotero-addon/` to the new
   version (e.g. `0.3.0`).

2. **Update `zotero-addon/update.rdf`** — set `em:version` to the new version and
   `em:updateLink` to the expected release download URL:

   ```
   https://github.com/AdamKrysztopa/sciagent/releases/download/v0.3.0/sciagent-zotero-addon.xpi
   ```

3. **Bump the server version** — update the `--version` string in `src/agt/server.py` to match.

4. **Commit and tag**:

   ```bash
   git add zotero-addon/manifest.json zotero-addon/package.json \
           zotero-addon/update.rdf src/agt/server.py
   git commit -m "chore: release v0.3.0"
   git tag v0.3.0
   git push origin main --tags
   ```

5. **CI takes over** — `build-binaries.yml` runs on the tag push and:
   - Builds Python binaries for all four platforms (macOS arm64/x86\_64, Linux x86\_64, Windows x64)
   - Builds the XPI (with full lint + typecheck + test gates)
   - Computes the XPI SHA256 and rewrites `zotero-addon/update.rdf` with the hash
   - Commits the updated `update.rdf` back to `main` (so Zotero auto-update kicks in)
   - Creates a GitHub Release with the XPI, `update.rdf`, and all four platform binaries

6. **Verify** — check the Release page; confirm Zotero detects the update from
   `https://raw.githubusercontent.com/AdamKrysztopa/sciagent/main/zotero-addon/update.rdf`.

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
