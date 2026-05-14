# SciAgent — User Manual

> Version 0.2.0 · Zotero-native, approval-gated academic search across 9 free sources.

---

## 5 Minutes from Install to First Search

> This section assumes the XPI is already installed and the backend binary is running.
> If you have not done that yet, start with [Installation](install.md).

### Open the SciAgent panel

In Zotero, go to **Tools → SciAgent**. The sidebar opens on the right side of the Zotero window.

The status pill at the top of the panel shows the backend connection state:

- **Green** — backend is running and reachable.
- **Red** — backend is offline. Click **Retry** to reconnect, or check that the
  binary started correctly (see [Backend offline](#backend-offline)).

### First-run card: enter an LLM key

On first launch, SciAgent shows a setup card asking for one LLM API key. Paste any one of:

- OpenAI (`sk-...`)
- Anthropic (`sk-ant-...`)
- xAI
- Groq (`gsk_...`)

Click **Save**. SciAgent tests the key and stores it in the add-on preferences.
For provider-specific instructions see [Keys](keys.md).

### Run your first search

1. Type a research question in the search box, for example:
   `transformer-based retrieval augmented generation 2022–2024`
2. Click **Search** (or press Enter).
3. SciAgent shows a **search plan** before fetching anything: parsed year filters,
   exclude terms, active providers, and depth. Review it and click **Confirm** to proceed.
4. Results appear as cards showing title, authors, year, citation count, abstract, and
   which sources contributed to each merged record.

### Approve results into Zotero

1. Check the papers you want to save. Uncheck any you want to skip.
2. Set a **Collection** name (e.g. `RAG Papers`). SciAgent creates it if it does not exist.
3. Click **Approve**. Each card updates with a write status:
   - `created` — new item added to Zotero.
   - `unchanged` — item was already in your library; no duplicate created.
   - `failed` — see the inline error message.

Nothing touches your Zotero library until you click Approve.

---

## When Something Goes Wrong

### Backend offline

The status pill turns red when the backend is not reachable.

1. Click **Retry** in the panel. If it stays red, check the terminal or system tray
   where the backend binary runs.
2. If you just installed, the binary may need a one-time OS approval.
   See [OS Security Warnings](install.md#os-security-warnings).
3. Confirm the backend URL in **Preferences → SciAgent** matches where the server started
   (default: `http://localhost:8000`).

### No results

- Check for spelling mistakes — SciAgent does not auto-correct queries.
- Try broader or shorter search terms.
- `quick` depth queries only 2 sources. Switch to `balanced` or `deep` in the depth
  selector before re-running.
- Very recent dates (e.g. "2025 papers") return fewer results by nature.

### LLM key not accepted

The search plan step requires a working LLM key. If the key is rejected:

- Check that you pasted the full key with no leading/trailing whitespace.
- Verify the key is active in your provider dashboard.
- See [Keys](keys.md) for provider-specific troubleshooting.

### macOS / Windows binary warning

The server binary is not yet code-signed. Both Gatekeeper (macOS) and SmartScreen (Windows)
will block it on first run. Full approval steps are at
[OS Security Warnings](install.md#os-security-warnings).

### Common error codes in the status panel

| Code | Meaning | Action |
| ---- | ------- | ------ |
| `ERR_PREFLIGHT` | Zotero API key lacks write access | Go to [zotero.org/settings/keys](https://www.zotero.org/settings/keys) and enable **Allow write access** |
| `ERR_NO_LLM` | No LLM key configured | Open **Preferences → SciAgent → LLM Provider** and add a key |
| `ERR_RATE_LIMIT` | Provider throttled the request | Wait a moment and retry; add `AGT_MAILTO` or a provider key to raise limits |
| `ERR_CONFLICT` | Providers disagreed on a field | Open the approval dialog to review each conflict before writing |
| `ERR_PORT` | Port 8000 already in use | Restart the backend on a different port and update the URL in preferences |

---

## When You Want More

### Author filter

In the sidebar, click the **Authors** chip input and type a name. SciAgent resolves the
author against OpenAlex and Semantic Scholar and restricts results to that author's
verified IDs. You can add multiple authors — results match any of them.

### Venue / Journal filter

Click the **Venue** chip input and type a journal or conference name (partial matches work).
Results are restricted to papers published in matching venues.

### Seed DOI

Paste a DOI into the **Seed DOI** field to anchor a citation-graph search. SciAgent
expands forward and backward citation links from that paper via OpenCitations and
Semantic Scholar. Result cards show:

- `↓ ref` — cited by your seed paper.
- `↑ cites` — cites your seed paper.

### Year and citation filters

- **Year range** — set min/year and max/year in the filter bar, or write them inline in
  your query (e.g. `2021–2024`). Parsed filters are shown in the search plan before search.
- **Min citations** — slide the citation threshold to surface only well-cited work.
- **Open access only** — toggle the OA switch to restrict results to open-access papers.

### Search depth

Select depth in the sidebar before running. The panel shows which providers will be
queried at each level.

| Depth | Providers queried | Results per source | Speed |
| ----- | ----------------- | ------------------ | ----- |
| `quick` | OpenAlex, arXiv | 10 | ~5 s |
| `balanced` | + Crossref, Europe PMC, DOAJ, PubMed | 25 | ~15 s |
| `deep` | + Semantic Scholar, CORE, BASE, OpenCitations | 50 | ~30 s |

### Watch List for recurring searches

Click **Save as Watch** from the search plan panel. SciAgent saves the full plan
(query, filters, depth) and re-runs it on demand. Only papers new since the last
run are shown — safe to approve repeatedly without creating duplicates.

### Library Doctor and Gap Finder

Open **Tools → SciAgent → Library Doctor** to scan your Zotero library for missing
abstracts, broken DOIs, or incomplete metadata. **Gap Finder** takes a collection you
specify and suggests related papers not yet in your library.

### All environment variables

For the full list of `AGT_*` settings (custom LLM models, proxy config, disabled
providers, timeouts, and more) see [Advanced Config](advanced-config.md).

### Optional provider keys

Adding free API keys for Semantic Scholar, PubMed, or CORE raises rate limits and
unlocks additional data. For the full list and where to get each key see [Keys](keys.md).
