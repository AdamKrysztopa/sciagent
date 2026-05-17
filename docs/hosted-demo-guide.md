# SciAgent — Hosted Demo: Complete User Guide

> **Who this guide is for:** Researchers who want to use the public SciAgent
> backend at `https://sciagent-ewpafdgfya-ew.a.run.app` without running any
> server software themselves. You need Zotero 9 and 15 minutes.

---

## What SciAgent Does

You type a research question. SciAgent searches OpenAlex, Semantic Scholar,
Crossref, PubMed, arXiv, Europe PMC, BASE, and OpenCitations simultaneously,
deduplicates and ranks the results, and shows them to you for approval before
anything touches your library. Only the papers you check get written to Zotero.

The hosted backend runs the search engine and the LLM (DeepSeek, operator-paid).
Your Zotero credentials travel with each request and are never stored.

---

## Before You Start

You need:

- **Zotero 9** installed on your computer.
  Download from [zotero.org/download](https://www.zotero.org/download).
- **A Zotero account** (free) — needed to generate an API key.
  Register at [zotero.org/user/register](https://www.zotero.org/user/register).

That is all. No Python. No terminal. No LLM key.

---

## Step 1 — Get Your Zotero Credentials (5 min)

You need two things: an API key and your library ID.

### Create an API key

1. Go to [zotero.org/settings/keys](https://www.zotero.org/settings/keys).
   Log in if prompted.
2. Click **Create new private key**.
3. Give it a name (e.g. `SciAgent`).
4. Under **Personal Library**, check:
   - **Allow library access**
   - **Allow write access**
5. Click **Save Key**.
6. Copy the 24-character key string that appears. **This is shown only once** —
   paste it somewhere safe before closing the page.

### Find your library ID

Your numeric **User ID** appears at the top of the same
[keys page](https://www.zotero.org/settings/keys), in a line that reads:

> Your userID for use in API calls is **1234567**.

Copy that number. It is your Library ID.

!!! tip "Group libraries"
    If you want SciAgent to write into a **group library** rather than your
    personal one, the library ID is the group's numeric ID shown in the group's
    URL (`zotero.org/groups/<id>`), and you should set Library Type to
    **Group library** in step 3.

---

## Step 2 — Install the Add-on (2 min)

1. Go to the [latest release](https://github.com/AdamKrysztopa/sciagent/releases/latest)
   on GitHub.
2. Download `sciagent-zotero-addon.xpi`.
3. In Zotero: **Tools → Add-ons → Install Add-on From File…**
4. Select the `.xpi` file you just downloaded.
5. Click **Restart Now** when Zotero prompts.

After restart, **Tools → SciAgent** appears in the menu bar.

---

## Step 3 — Configure for Remote Mode (3 min)

!!! important
    The add-on defaults to **Local** mode, which tries to start an embedded
    server on your machine. For the hosted demo you must switch to **Remote**
    mode before anything will work.

1. Open **Tools → SciAgent**.
2. Scroll down past the search box to the **Preferences** card.
3. Under **Connection & Auth**, set:
   - **Backend Mode:** `Remote (hosted backend)`
   - **Backend URL:** `https://sciagent-ewpafdgfya-ew.a.run.app`
4. Under **Zotero Account**, fill in:
   - **Zotero API Key:** the key you copied in Step 1
   - **Library ID:** your numeric user ID from Step 1
   - **Library Type:** `User library` (or `Group library` if applicable)
5. Click **Save Preferences**.

The status pill at the top of the panel should turn **green** within a few
seconds. If it stays red, see [Troubleshooting](#troubleshooting).

---

## Step 4 — Run Your First Search

### Open the panel

Go to **Tools → SciAgent**. The panel opens on the right side of the Zotero
window.

### Enter a query

Type your research question in natural language. Examples:

- `transformer-based retrieval augmented generation 2022–2024`
- `CRISPR off-target effects in human cells`
- `machine learning for drug discovery reviews`

Year ranges, open-access filters, and min-citation thresholds can be written
inline or set with the filter controls below the search box.

### Choose a search depth

| Depth | Sources queried | Speed |
|---|---|---|
| `quick` | OpenAlex, arXiv | ~5 s |
| `balanced` (default) | + Crossref, Europe PMC, PubMed | ~15 s |
| `deep` | + Semantic Scholar, BASE, OpenCitations | ~30 s |

Start with **balanced**. Use **deep** when you want comprehensive coverage for
a systematic review.

### Click Search

SciAgent sends your query to the backend and returns a ranked list of papers.
Each card shows:

- Title, authors, year, journal/venue
- Citation count and open-access status
- Abstract snippet
- Which sources contributed to this record
- Relevance score

---

## Step 5 — Approve Results into Zotero

1. **Check** the papers you want to save. All papers are selected by default —
   uncheck any you want to skip.
2. Set a **Collection Name** in the approval panel (e.g. `RAG Papers`).
   SciAgent creates the collection if it does not already exist.
3. Click **Approve Selected**.

Each card updates with a write status:

| Status | Meaning |
|---|---|
| `created` | New item added to your Zotero collection. |
| `unchanged` | Item was already in your library — no duplicate created. |
| `failed` | See the inline error message. Usually a network or permission issue. |

Nothing is written to Zotero until you click Approve. Clicking **Reject**
discards all results without writing anything.

---

## Going Further

### Refine your search with filters

The filter panel below the search box lets you set:

- **Year range** — `Min Year` / `Max Year`, or write `2021–2024` in the query.
- **Min Citations** — hide low-citation papers; useful for established topics.
- **Open Access Only** — restrict results to papers with a free full text.
- **Author filter** — type a name to restrict results to a specific author.
  SciAgent resolves the author against OpenAlex and Semantic Scholar and
  narrows using their verified IDs. Add multiple authors to match any of them.
- **Venue / Journal filter** — type a journal or conference name (partial
  matches work).
- **Seed DOI** — paste a DOI to anchor a citation-graph search. SciAgent
  expands forward and backward citation links from that paper.

### Save a search as a Watch

Click **Save as Watch** after a search. SciAgent saves the full plan (query,
filters, depth) and re-runs it on demand from the **Watch List** panel. Only
papers new since the last run are shown — safe to approve repeatedly without
creating duplicates.

### Library Doctor

Click **Find Gaps** (or open the Library Doctor section) and enter a collection
name. SciAgent scans that collection for:

- Missing abstracts or broken DOIs
- Duplicate items
- Incomplete metadata

It then suggests papers not yet in your library that are closely related to
what you already have.

### Spell-check

Enable **Spell-check queries before search** in Preferences. SciAgent corrects
common misspellings in your query and shows a suggestion banner before
searching. Click the suggestion to accept it.

---

## Optional — Use Your Own LLM Key

The hosted backend uses the operator's DeepSeek key by default (subject to a
$10/month cap). If you want to use your own key:

1. In Preferences, scroll to **LLM Override (Remote Mode)**.
2. Check **Use my own LLM key for remote backend**.
3. Fill in:
   - **LLM Provider** (OpenAI, Anthropic, DeepSeek, xAI, Groq, or OpenAI-compatible)
   - **API Key** for that provider
   - **Base URL** — leave blank unless you use a custom endpoint
   - **Model** — leave blank to use the provider's default
4. Click **Save Preferences**.

LLM calls will now be charged to your account, not the operator's. The
operator's cap no longer applies to you.

---

## Troubleshooting

### Status pill stays red after saving preferences

- Double-check the **Backend URL** is exactly
  `https://sciagent-ewpafdgfya-ew.a.run.app` (no trailing slash).
- Confirm **Backend Mode** is set to `Remote (hosted backend)`.
- The service may be temporarily down (it has no SLA). Try again in a few
  minutes.

### "API key rejected" or 401 error

- Verify the Zotero API Key is the full key string from
  [zotero.org/settings/keys](https://www.zotero.org/settings/keys).
- Check the key has **Allow write access** enabled.
- Verify the Library ID matches the user ID on the same page.

### Search returns no results

- Try broader or shorter search terms.
- Increase depth to `balanced` or `deep`.
- Very recent dates (papers published in the last few weeks) have lower
  coverage across all providers.

### A paper I approved does not appear in Zotero

- Check the write status — it may show `unchanged` (the item was already
  there) or `failed` (see the inline message).
- Confirm your Zotero API key has write access and the library ID is correct.
- Refresh the Zotero library (right-click the collection → **Refresh**).

### The backend says the service is at capacity

The demo runs with a maximum of 2 instances and a $10/month LLM cap. If you
hit the cap, bring your own LLM key (see above) or wait until the following
month.

---

## Privacy & Trust

| What the backend receives | What the backend does with it |
|---|---|
| Your search query | Passes to LLM for rewriting + to source APIs for retrieval |
| Your Zotero API key and library ID | Used to write approved items; never logged, never stored |
| The papers it writes | Written to your library; not stored on the backend |

The backend does **not**:

- Store your Zotero credentials after the request completes.
- Log your API key (structlog redaction is enforced).
- Read your existing Zotero library beyond checking for duplicate DOIs.
- Share your data with anyone except the LLM provider (DeepSeek by default).

The service is a demo with no SLA. Source code:
[github.com/AdamKrysztopa/sciagent](https://github.com/AdamKrysztopa/sciagent).
