# SciAgent — User Manual

> Version 0.2.0 · For researchers who want Zotero-native, approval-gated academic search.

SciAgent federates academic search across 9 free sources, merges results with full provenance,
and writes approved papers to your Zotero library — never silently, always with your sign-off.

---

## Table of Contents

1. [What You Need Before Starting](#what-you-need-before-starting)
2. [Installation](#installation)
3. [Starting SciAgent](#starting-sciagent)
4. [Your First Search](#your-first-search)
5. [Search Features](#search-features)
6. [Provider Configuration](#provider-configuration)
7. [Troubleshooting](#troubleshooting)

---

## What You Need Before Starting

| Requirement    | Where to get it                                              |
| -------------- | ------------------------------------------------------------ |
| **Zotero 9.x** | [zotero.org/download](https://www.zotero.org/download)       |
| **Zotero API key** | [zotero.org/settings/keys](https://www.zotero.org/settings/keys) — needs write access |
| **Zotero library ID** | Your numeric user ID on the same keys page                |
| **One LLM key** | OpenAI, Anthropic, xAI, or Groq — or run Ollama locally (free) |
| **Python 3.13+** | [python.org](https://www.python.org) or `pyenv install 3.14` |
| **uv** (Python manager) | `curl -Lsf https://astral.sh/uv/install.sh \| sh`        |
| **Node.js 20+** | [nodejs.org](https://nodejs.org) — only needed to build the add-on |
| **git** | Pre-installed on macOS/Linux; [git-scm.com](https://git-scm.com) on Windows |

---

## Installation

### Step 1 — Install Python backend

```bash
# Clone the repository
git clone https://github.com/AdamKrysztopa/sciagent.git
cd sciagent

# Install all Python dependencies (creates .venv automatically)
uv sync
```

That's it. No system-wide Python install required — `uv` manages the virtualenv.

**Verify:**

```bash
uv run sciagent-server --version
# sciagent-server 0.2.0
```

---

### Step 2 — Configure credentials

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in **at minimum**:

```env
# --- LLM (pick one) ---
AGT_OPENAI_API_KEY=sk-...          # OpenAI
# AGT_ANTHROPIC_API_KEY=sk-ant-...  # Anthropic Claude
# AGT_GROQ_API_KEY=gsk_...          # Groq (free tier)

# --- Zotero write path ---
AGT_ZOTERO_API_KEY=your-zotero-api-key
AGT_ZOTERO_LIBRARY_ID=12345678        # your numeric user ID

# --- Strongly recommended ---
AGT_MAILTO=your-email@example.com     # unlocks polite-pool rate limits for OpenAlex, Crossref, DOAJ
```

#### Getting your Zotero API key and library ID

1. Go to [zotero.org/settings/keys](https://www.zotero.org/settings/keys)
2. Click **Create new private key**
3. Enable **Allow write access** — this is required for SciAgent to add papers
4. Copy the key into `AGT_ZOTERO_API_KEY`
5. Your **library ID** is shown on that same page as "Your userID for use in API calls"

#### Using Ollama (fully offline, no LLM key needed)

Install [Ollama](https://ollama.ai) and pull a model:

```bash
ollama pull llama3.2
```

Then in `.env`:

```env
AGT_LLM_PROVIDER=ollama
AGT_LLM_MODEL=llama3.2
```

---

### Step 3 — Build the Zotero add-on

```bash
cd zotero-addon
npm ci            # install Node dependencies (first time only)
npm run build     # produces build/sciagent-zotero-addon.xpi
cd ..
```

**Expected output:** a file at `zotero-addon/build/sciagent-zotero-addon.xpi` (around 250 KB).

---

### Step 4 — Install the add-on in Zotero

> **macOS warning:** Do NOT double-click the XPI file. macOS treats it as a zip archive and
> extracts it instead of installing it. Always use the in-app install method below.

1. Open Zotero 9
2. Go to **Tools → Add-ons**
3. Click the **gear icon** (⚙) in the top-right corner
4. Select **Install Add-on From File…**
5. Navigate to `sciagent/zotero-addon/build/sciagent-zotero-addon.xpi`
6. Click **Open** and confirm

Zotero may ask you to restart — do so if prompted.

**After restart, verify:** SciAgent should appear in the add-on list with status **Enabled** and
version **0.2.0**.

---

## Starting SciAgent

**Every time you want to use SciAgent, start the backend first:**

```bash
cd sciagent
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
```

Wait for:

```text
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Then open Zotero → **Tools → SciAgent**.

The health indicator at the top of the workspace should show **green / connected**. If it shows
red, the backend is not running — go back to the terminal step.

### Alternative: Docker (no Python install)

If you prefer Docker over a native Python setup:

```bash
cp .env.example .env  # fill in credentials
docker compose up --build -d
curl http://localhost:8000/health  # should return {"ok": true, ...}
```

The `.env` file is mounted directly — edit it to change credentials.

---

## Your First Search

1. **Open Tools → SciAgent** in Zotero
2. **Type a research question** in the search box, e.g. `retrieval augmented generation 2023+`
3. **Set a collection name** — e.g. `RAG Papers`. SciAgent creates the collection if it doesn't exist.
4. Click **Run Search**. SciAgent shows the **search plan** (parsed year filters, exclude terms,
   source list) before fetching anything, then runs the search across all active providers in
   parallel, and merges and deduplicates results with full provenance.
5. **Review the results** — each card shows title, authors, year, citation count, abstract, and
   which sources contributed to that record
6. **Check/uncheck papers** you want to add to Zotero
7. Click **Approve** — SciAgent writes selected papers to the target collection
8. Each paper gets a write status: `created`, `unchanged` (already in library), or `failed`

Writing is approval-gated: nothing touches your Zotero library until you click Approve.

---

## Search Features

### Search depth

Use the **depth selector** in the sidebar before running:

| Depth      | Providers queried                                | Results/source | Speed  |
| ---------- | ------------------------------------------------ | -------------- | ------ |
| `quick`    | OpenAlex, arXiv                                  | 10             | ~5 s   |
| `balanced` | + Crossref, Europe PMC, DOAJ, PubMed             | 25             | ~15 s  |
| `deep`     | + Semantic Scholar, CORE, BASE, OpenCitations    | 50             | ~30 s  |

The sidebar shows which providers will run at the selected depth _before_ you search.

### Deterministic filters

Hard filters are parsed from your query and displayed before search — they cannot be silently
loosened:

| What you write               | What SciAgent enforces                        |
| ---------------------------- | --------------------------------------------- |
| `not older than 2023`        | `min_year = 2023`                             |
| `between 2021 and 2024`      | `min_year = 2021`, `max_year = 2024`          |
| `not about healthcare`       | `exclude_terms = ["healthcare"]`              |
| `open access only`           | `open_access = true`                          |
| `most cited`                 | citation threshold filter                     |

You can also **edit any filter** before re-running: adjust year range, add exclusions, toggle OA.

### Result provenance

Every result shows exactly where its data came from:

- **Source chips** — which providers contributed to this merged record (e.g. `openalex • crossref`)
- **Missing-field tooltips** — hover the "ⓘ" next to an empty field to see why it's missing:
  provider didn't return it, no queried provider supports that field, a key is required, or the
  current depth skipped it
- **Conflict dot** — a red ● means providers disagreed on a field value. The approval dialog shows
  each conflict and requires explicit confirmation before writing to Zotero

### Author search

Queries like _"papers by Yoshua Bengio 2020–2024"_ resolve the author via OpenAlex and Semantic
Scholar, then filter results to that author's verified IDs. Author chips in result cards are
tappable to launch a new scoped search.

### Citation graph

Queries like _"papers citing Attention Is All You Need"_ trigger citation graph expansion via
OpenCitations and Semantic Scholar. Result cards show:

- `↓ ref` — this paper was cited by your seed
- `↑ cites` — this paper cites your seed

### Saving and re-running searches (watch lists)

From the sidebar, save any search plan as a **Watch**. SciAgent re-runs it on demand and shows
only new papers since the last run — safe to approve repeatedly without creating duplicates.

---

## Provider Configuration

### Free sources (always active, no key needed)

| Source            | Coverage           |
| ----------------- | ------------------ |
| OpenAlex          | 250M+ works        |
| Crossref          | 130M+ DOI records  |
| arXiv             | 2.4M+ preprints    |
| Europe PMC        | 43M+ life sciences |
| PubMed            | 36M+ biomedical    |
| DOAJ              | 9M+ OA articles    |
| BASE              | 400M+ records      |
| OpenCitations     | Citation graph     |
| Semantic Scholar  | 200M+ (rate-limited without key) |

### Optional keys (add to `.env` to unlock)

| Variable                       | What it unlocks                                  |
| ------------------------------ | ------------------------------------------------ |
| `AGT_SEMANTIC_SCHOLAR_API_KEY` | Higher S2 throughput (free key at semanticscholar.org) |
| `AGT_NCBI_API_KEY`             | Higher PubMed limits (free at ncbi.nlm.nih.gov/account) |
| `AGT_CORE_API_KEY`             | CORE full-text OA index (free at core.ac.uk)      |
| `AGT_SERPAPI_KEY`              | Google Scholar via SerpAPI (paid)                |
| `AGT_DIMENSIONS_KEY`           | Dimensions institutional metadata (paid)          |

You can also enter provider keys directly in the **ConfigPanel** inside the Zotero sidebar
(**Tools → SciAgent → ⚙ Config**). Each key has a **Test** button that validates it before saving.

### Disabling specific providers

```env
AGT_DISABLED_PROVIDERS=["base","core"]
```

Disabled providers appear as `disabled` in the Coverage panel with no silent failure.

---

## Troubleshooting

### Backend won't start

**"Extra inputs are not permitted"** — a variable name in `.env` has a typo or is missing the
`AGT_` prefix. All variables must start with `AGT_`.

**"Missing required field"** — `AGT_ZOTERO_API_KEY` or `AGT_ZOTERO_LIBRARY_ID` is empty.
At least one LLM key is also required.

**Port 8000 already in use** — another process has the port. Either kill it or start on a
different port:

```bash
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8001
```

Then update the backend URL in the add-on preferences to `http://localhost:8001`.

### Zotero add-on issues

**"The add-on could not be installed"** — rebuild the XPI:

```bash
cd zotero-addon && npm run build
```

Then install the freshly built file from `zotero-addon/build/sciagent-zotero-addon.xpi`.

**Requires Zotero 9.0.0+** — earlier versions are not supported. Check **Help → About Zotero**.

**Backend health shows red** — the backend is not running or the URL in preferences is wrong.
Default URL is `http://localhost:8000`. Check the terminal where you started the backend.

### Zotero preflight fails ("cannot write")

Your API key may lack write permissions. Go to
[zotero.org/settings/keys](https://www.zotero.org/settings/keys), edit your key, and enable
**Allow write access**.

### Search returns no results

- Check for spelling errors — SciAgent does not auto-correct queries
- Try broader search terms
- For very recent dates (e.g. "2026 papers"), fewer results are expected
- `quick` depth only queries 2 sources; switch to `balanced` or `deep`

### Rate limit errors

If you see rate-limit messages in the Coverage panel:

- Add `AGT_SEMANTIC_SCHOLAR_API_KEY` (free) for Semantic Scholar
- Add `AGT_MAILTO=your-email@example.com` to enter the polite pool for OpenAlex/Crossref/DOAJ
- Wait and retry — rate limits are per session and reset quickly

---

## Quick Reference: all environment variables

See `.env.example` in the repo root for the full annotated list. The most important:

```env
# LLM (required — pick one)
AGT_OPENAI_API_KEY=
AGT_ANTHROPIC_API_KEY=
AGT_XAI_API_KEY=
AGT_GROQ_API_KEY=

# Zotero write path (required)
AGT_ZOTERO_API_KEY=
AGT_ZOTERO_LIBRARY_ID=

# Polite pool (strongly recommended)
AGT_MAILTO=your-email@example.com

# Optional: search quality
AGT_SEMANTIC_SCHOLAR_API_KEY=
AGT_NCBI_API_KEY=
AGT_CORE_API_KEY=

# Optional: search depth default
AGT_SEARCH_DEPTH=balanced   # quick | balanced | deep

# Optional: Ollama (no hosted LLM key)
AGT_LLM_PROVIDER=ollama
AGT_LLM_MODEL=llama3.2

# Optional: disable specific providers
AGT_DISABLED_PROVIDERS=["base"]
```
