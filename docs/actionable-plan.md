# SciAgent Actionable Plan — P9 (Standalone Distribution + First-Class Search Fields + Docs Overhaul)

> **Last audit: 2026-05-13** — All P0–P8 stories complete (see
> [actionable-plan-done-2.md](actionable-plan-done-2.md) and
> [actionable-plan-done.md](actionable-plan-done.md)).
>
> This plan covers **P9: Ship SciAgent as one XPI for end-users**, **extend search with a
> first-class Author field (and a few other high-leverage fields)**, and **rebuild the docs
> around the "minimum config to start, more advanced on demand" principle**.
>
> Canonical execution tracker. Update done/not done state here first.
> Historical, completed work stays in `actionable-plan-done*.md` — do not re-open closed items.

## Design Philosophy

**One installer.** A researcher should be able to install SciAgent in one step from
inside Zotero, the same way they install any other Zotero add-on. Today the
`README.md` still requires `git clone`, `uv sync`, `npm ci`, and `npm run build` —
that is a developer install. The local-first plan
([docs/local-first.md](local-first.md)) and the embedded-server binary already exist
and work on macOS arm64; what is missing is the **release pipeline that bundles
them**, the **default backend mode**, and the **end-user docs that hide the dev
path**.

**Two distribution shapes from one codebase:**

| Shape         | Audience       | What ships                                | Start cost           |
| ------------- | -------------- | ----------------------------------------- | -------------------- |
| Standalone    | Researcher     | One XPI · binary downloads on first run   | install XPI + LLM key |
| Web / dev     | Developer · SaaS host | Source + uv + Docker                | the current README path |

The **standalone** shape is the one we are missing. Both shapes run identical
backend code — the local binary and any future hosted backend are the same
FastAPI app frozen by PyInstaller.

**Minimum config to start.** The first-time experience is one LLM key (or a
running Ollama). Everything else — provider keys, polite-pool email, source
disables, advanced filters — must be discoverable later, not asked up front.
Today the `.env.example`, the `ConfigPanel`, the user manual, and the README
mix required and optional config in one wall of text. P9 separates them.

**Search has fields, not only natural language.** P8.8 added `HardFilters.author_ids`
and a natural-language resolver (`by Yoshua Bengio …`). It works when the user
remembers to phrase the query correctly. It does not exist as a UI field, has
no autocomplete, and silently degrades to topic-only search when the parser
misses. P9 adds **Author**, **Venue/Journal**, and **DOI/seed paper** as first-class
search fields with provider-backed suggestions, alongside the existing year and
keyword controls.

---

## Release Readiness

**P9 release gate** — when the items below pass, the *researcher install path* is
one click and the *power-user search* covers the cases that matter most:

1. The Zotero plugin directory and a single GitHub Release page each host one XPI
   that boots a working SciAgent without any terminal commands on macOS (arm64,
   x86_64), Linux x86_64, and Windows x64.
2. First-run flow inside Zotero downloads the right server binary, starts it,
   surfaces a green health badge, and renders a one-screen "you only need an LLM
   key" config card. No `.env`. No `uv`.
3. Search has explicit fields for **Author**, **Venue**, and **Seed DOI** in
   addition to the free-text query. Authors come with OpenAlex/S2 autocomplete and
   resolve to `author_ids` before search runs.
4. The user-facing docs lead with the XPI install + LLM key. The developer
   install (uv, FastAPI, npm) is one click away, not the front door.

The four pieces are independent — each ships value on its own, but only the
combination clears the "use it without reading the manual" bar that the user
asked for.

---

## Execution Tracker

### Current Status

- All P0–P8 milestones complete as of 2026-05-14. 563 Python / 104 add-on tests green.
- ✅ **P9.0 complete (2026-05-13):** `backendMode` default changed to `"local"`;
  `runtime.ts` `createClient` uses `getResolvedPort()` (57321) instead of
  `config.backendUrl` (8000), fixing a silent port mismatch; `BackendFailurePanel`
  now shows local-aware instructions; health re-check fires automatically after
  first-run binary download completes; `prefs.test.ts` asserts the new default.
- **Open product gap.** No tagged release has run the full `build-binaries.yml`
  end-to-end (P9.1). `README.md` Quick Start still asks the user to clone the
  repo and run uvicorn (P9.11). Author search ends at result-card chips —
  no Author input field (P9.6–P9.8).

### P9 Status

| ID    | Story                                                  | Effort | Owner          | Status |
| ----- | ------------------------------------------------------ | ------ | -------------- | ------ |
| P9.0  | Release-mode default + first-run polish                | ~0.25d | zotero-frontend | ✅ done (2026-05-13) |
| P9.1  | Build-binaries CI cross-platform validation            | ~0.75d | settings-bootstrap | not done |
| P9.2  | Unified `release.yml` (binaries + XPI + update.rdf)    | ~0.5d  | settings-bootstrap | not done |
| P9.3  | `update.rdf` self-update wiring                        | ~0.25d | zotero-frontend | not done |
| P9.4  | macOS Gatekeeper note + Windows SmartScreen note       | ~0.25d | zotero-addon  | not done |
| P9.5  | Embedded `FirstRunConfigCard` (LLM key + Zotero)       | ~0.5d  | zotero-frontend | not done |
| P9.6  | `Author` first-class search field (backend)            | ~0.5d  | python-backend-engineer | not done |
| P9.7  | `Author` autocomplete endpoint                         | ~0.25d | python-backend-engineer | not done |
| P9.8  | `Author` UI field with chip autocomplete               | ~0.5d  | zotero-frontend | not done |
| P9.9  | `Venue/Journal` first-class field                      | ~0.5d  | full-stack    | not done |
| P9.10 | `Seed DOI` paste field (drives `seed_dois`)            | ~0.25d | zotero-frontend | not done |
| P9.11 | README rewrite: XPI-first quick start                  | ~0.25d | core-planner  | not done |
| P9.12 | `docs/user-manual.md` rewrite (minimum-config path)    | ~0.5d  | core-planner  | not done |
| P9.13 | New `docs/install.md` (single source for install flow) | ~0.25d | core-planner  | not done |
| P9.14 | New `docs/keys.md` (how to get every key)              | ~0.5d  | core-planner  | not done |
| P9.15 | `docs/advanced-config.md` (everything that is optional) | ~0.25d | core-planner | not done |
| P9.16 | `mkdocs.yml` nav reshuffle + landing-page redesign     | ~0.25d | core-planner  | not done |
| P9.17 | Telemetry-free first-run smoke (manual checklist)      | ~0.25d | sciagent-orchestrator | not done |

**Total estimate:** ~6.25 days.

---

## Market Snapshot — What "one-click research add-ons" actually look like

> Source: independent review of the active 2025–2026 research-tool landscape.
> Reread before each P9 milestone closes. SciAgent is not Elicit; it is
> closest to Zotero Connector + Inciteful + Litmaps with approval-gated writes.

| Tool                  | Install model                          | Free tier                | Search fields beyond query                 | Notes for SciAgent                                                                                              |
| --------------------- | -------------------------------------- | ------------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Zotero Connector      | One click from zotero.org              | Free                     | n/a (browser capture, no federated search) | Sets the **bar for install friction**. Anything more than "click → install" loses casual users.                  |
| Zotero built-in lookup | Bundled                              | Free                     | DOI, ISBN, PMID                            | We must at minimum cover **DOI seed lookup** to match parity.                                                   |
| ResearchRabbit         | Web app, account                       | Free                     | Seed paper, author, keyword                | First-class **seed paper + author** controls — close to our planned P9.6/P9.10 shape.                            |
| Litmaps                | Web app, account                       | Freemium                 | Seed paper, author, year, keyword          | Markets "explore by paper" — implies seed-DOI is table stakes. Author autocomplete is theirs by default.        |
| Connected Papers       | Web, no account for one map/day        | Limited free             | Seed paper                                 | Search is **single seed DOI / title**. Confirms that a seed-DOI field on its own is enough for many workflows.  |
| Inciteful              | Web app                                | Free                     | Seed paper, author, year range             | Pure web, no install. Their author field is plain text with no resolver — we can beat them by autocompleting.    |
| Elicit                 | Web app, account                       | Limited free queries     | Topic, optional filters                    | Strong on natural-language Q&A, weak on author/venue search. Different niche.                                  |
| Consensus              | Web app, account                       | Limited free queries     | Topic                                      | Same niche as Elicit.                                                                                            |
| Scite                  | Web + Zotero plugin                    | Subscription             | DOI, citation type                         | Zotero plugin model proves users **will install a domain add-on if the install is trivial**.                    |
| Paperpile              | Browser ext + macOS app                | Subscription             | Topic, author, year                        | Has the standalone macOS app pattern we are emulating — bundled binary, no Python prompt.                       |
| Semantic Scholar       | Web + API                              | Free                     | Topic, author, year, venue                 | Their UI exposes **all four fields explicitly**. We already query S2 — we should expose the same shape.         |
| OpenAlex Works UI      | Web                                    | Free                     | Topic, author, venue, year, OA, type       | Same — confirms author + venue belong in the UI, not just the URL grammar.                                       |

**Gaps SciAgent fills uniquely** — Zotero-native, approval-gated, deterministic
filters with provenance, federated across 9 free sources, runs locally with no
account. Those are differentiators we must keep visible in the install path,
not bury under three terminal commands.

**Gaps SciAgent must close (P9 scope)** —

1. **Install friction**: every comparable Zotero add-on installs from one XPI.
   SciAgent must match that or lose every user who would not run `uv sync`.
2. **Author/Venue/Seed fields**: every comparable tool exposes these as fields.
   We expose them only as natural-language hints today.
3. **Onboarding clarity**: every comparable tool asks for at most one credential
   on first use. SciAgent's `.env.example` lists 14+ keys. Most are optional but
   the doc reads as if they are not.

---

## P9 Milestones

### P9.A — Standalone XPI Install *(2 days)*

> Source: docs/local-first.md (already designed; this is the integration and
> release pass). Everything below builds on existing code — no new architecture.

**Goal:** A researcher downloads one XPI from a GitHub Release, installs it from
inside Zotero, opens it, pastes an LLM key, and runs a search. No terminal.

| ID    | Story                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Effort |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P9.0  | **Release-mode default.** In `zotero-addon/src/host/prefs.ts`, set `backendMode` default to `"local"` (it may already be — verify and document). Confirm `bootstrap.js` calls `serverManager.startServer()` on plugin load and `stopServer()` on shutdown. Add an integration check that warns if the binary is missing **and** `backendMode === "local"`.                                                                                                                                                                                  | ~0.25d |
| P9.1  | **Cross-platform binary validation.** Trigger `.github/workflows/build-binaries.yml` on a release-candidate branch. Confirm `linux-x86_64`, `macos-arm64`, `macos-x86_64`, `windows-x64` binaries all pass the `--version` and `/health` smoke step. Fix any platform-specific PyInstaller hooks (most likely Linux missing `anyio` backends, Windows missing console subsystem flags). Record SHA256s in CI logs and in `docs/install.md`.                                                                                                  | ~0.75d |
| P9.2  | **Unified release workflow.** Either extend `build-binaries.yml` to also run the existing XPI build (already present in `package-xpi` job) and publish `update.rdf`, or merge `zotero-addon-release.yml` into `build-binaries.yml`. Outcome: one tag (`v1.0.0`) produces one GitHub Release that contains: four signed binaries, four `.sha256`, one XPI, one `update.rdf`. Verify by tagging `v1.0.0-rc.1` from a branch.                                                                                                                  | ~0.5d  |
| P9.3  | **Self-update wiring.** The XPI metadata already declares `updateURL`; point it at the `update.rdf` published in P9.2. After the next tag, an installed plugin must offer to auto-update without a re-download. Test by installing `v1.0.0-rc.1` and tagging `v1.0.0-rc.2` 10 minutes later.                                                                                                                                                                                                                                                | ~0.25d |
| P9.4  | **Code-signing notes.** Add a short admonition block to `docs/install.md` for macOS Gatekeeper (`right-click → Open`) and Windows SmartScreen ("More info → Run anyway"). Keep the long-term Apple Developer / EV cert plan in `docs/local-first.md` Part 7 — do not block P9 on it.                                                                                                                                                                                                                                                       | ~0.25d |
| P9.5  | **Embedded First-Run Config Card.** After the binary downloads and the server is healthy, the sidebar must show a single card: one input for an LLM key (pre-selected provider auto-detected from key prefix) and one input for the Zotero API key + Library ID with a "Find these on zotero.org/settings/keys" link. Saving the card writes to Zotero prefs and triggers a `/health` re-check. Hide every other config (sources, depth, advanced filters) behind a "Show advanced" toggle.                                                  | ~0.5d  |

**Acceptance (P9.A):**

- `https://github.com/AdamKrysztopa/sciagent/releases/latest` shows one XPI and
  four binaries from a single workflow run.
- Fresh macOS arm64 box: install Zotero 9 → install the XPI → open Tools →
  SciAgent → first-run dialog auto-downloads the binary → config card asks for
  one LLM key + one Zotero key → first search returns results — all without a
  terminal.
- The same flow tested manually on Linux x86_64 and Windows x64 (one each,
  documented in `docs/install.md` § Verified Platforms).

---

### P9.B — First-Class Search Fields *(1.25 days)*

> Source: market gap + user request. Natural-language author hints exist
> (P8.8) but no UI field. P9 adds the field, the autocomplete, and similar
> first-class controls for venue and seed-DOI.

**Goal:** A user searching for "papers by Yoshua Bengio on attention" types
"attention" in the query box and "Yoshua Bengio" in the Author box — both
fields go through the deterministic filter contract, both are visible in the
search plan, neither relies on the LLM rewriter to guess intent.

| ID    | Story                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Effort |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P9.6  | **Author field in the contract.** Extend `FilterEditContract` in `src/agt/models.py` with `authors: list[ResolvedAuthor]` (a small Pydantic model wrapping `name`, `openalex_id`, `orcid`, `s2_author_id`). Wire `run_search_phase` so that any resolved IDs land in `HardFilters.author_ids` *and* `HardFilters.author_names` for providers that do not support ID-based queries (Crossref query.author, arXiv `au:`). Add `author` push-down in `SearchPlan.filters_pushed_down`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | ~0.5d  |
| P9.7  | **Autocomplete endpoint.** Add `GET /authors/suggest?q=...&limit=5` to `src/agt/api/app.py`. Implementation reuses `author_resolver.py` (`resolve_author` already hits OpenAlex `/authors?search=` and S2 `/author/search`). Cap at 5 candidates ranked by works_count. Cache aggressively (in-process LRU, 15 min TTL).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | ~0.25d |
| P9.8  | **Author chip input.** In `FilterEditor.tsx` add a new section "Author" above "Year". A text input fires the suggest endpoint with a 200 ms debounce. Selected authors render as chips that include the resolved IDs (OpenAlex/ORCID badges as in `ResultsList`). Chips are removable. Saving the draft attaches resolved IDs to the `FilterEditContract.authors` array. The result card "Author chip → new scoped search" path already exists (P8.8) and should keep working — clicking a chip in a result now pre-fills the Author field instead of re-issuing a natural-language query.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | ~0.5d  |
| P9.9  | **Venue / Journal field.** Same shape as Author but resolves via OpenAlex `/venues?search=` and Crossref `/journals?query=`. Adds `HardFilters.venue_ids` and `HardFilters.venue_names`. Push-down on OpenAlex `filter=primary_location.source.id`, Crossref `query.container-title`. Show as chips below Author.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | ~0.5d  |
| P9.10 | **Seed DOI paste field.** `SearchPlan.seed_dois` already exists (P8.9). Surface it as a textarea in `FilterEditor.tsx` labelled "Seed papers (DOI, one per line)". Show a small inline preview of the resolved title once the backend echoes the citation graph. This lets users do "papers citing X" without typing the special phrase.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | ~0.25d |

**Acceptance (P9.B):**

- Searching for "attention" with an empty Author field returns the same top
  results as today.
- Searching for "attention" with "Yoshua Bengio" in the Author field returns
  only papers that name him (with the standard provenance chips), and the
  search plan shows `authors: ["A5023888391" /* OpenAlex */]` and
  `filters_pushed_down.openalex: ["author"]`.
- Searching for an empty topic with one DOI in Seed papers returns the citation
  graph of that DOI as today's "citing X" prefix did — but without the user
  needing to know the prefix.
- Existing benchmark queries (P8.14) remain at ≥15/22 must-find.

---

### P9.C — Documentation Overhaul: Minimum-Config First *(1.25 days)*

> Source: user goal. The current `README.md` and `user-manual.md` mix required
> and optional config. The user wants the first page to be reachable by anyone
> with Zotero, and the advanced material to live behind a click.

**Goal:** A first-time visitor on the GitHub README or the MkDocs landing page
reads three things — "install the XPI", "paste your LLM key", "search" — and
can do all three. Everything beyond that is one link deep.

| ID    | Story                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Effort |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| P9.11 | **README rewrite.** Front matter: one paragraph, one badge row, one image of the sidebar. Quick Start collapses to three steps — download XPI, install in Zotero, paste LLM key. A second collapsed section labelled "Developer install (uv + npm)" keeps the current `uv sync` / `npm run build` path verbatim for contributors. No fewer than four anchor links — Install, Manual, API, Roadmap.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | ~0.25d |
| P9.12 | **User manual rewrite.** Split `docs/user-manual.md` into three top-of-file sections — `## 5 minutes from install to first search`, `## When something goes wrong`, `## When you want more`. Move everything provider-specific into `docs/keys.md` (P9.14). Move every optional flag into `docs/advanced-config.md` (P9.15). Keep the screenshots inline.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | ~0.5d  |
| P9.13 | **New `docs/install.md`.** Single source of truth for installation. Sections: Standalone (XPI), Verified platforms table, Self-update, macOS Gatekeeper / Windows SmartScreen notes, Docker (recommended for self-hosters), Source build (the current README content). Becomes the destination of every "Install" anchor across the docs.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | ~0.25d |
| P9.14 | **New `docs/keys.md` — "How to get every key".** One section per credential: LLM keys (OpenAI, Anthropic, xAI, Groq, Ollama, custom OpenAI-compatible), Zotero API key + Library ID, optional academic keys (Semantic Scholar, NCBI/PubMed, CORE, SerpAPI, Dimensions), polite-pool email. Each section has: who needs it, why, exact link to the console, the form value to copy, the env var name, the matching sidebar ConfigPanel field name. Screenshots where the console UI is non-obvious (Zotero key page, OpenAI dashboard). Tag every key as **Required**, **Strongly recommended**, or **Optional**. Promise: a researcher reading this can collect every credential SciAgent might want in under 15 minutes — but they only need the **Required** ones to start.                                                                                                                                                                                                                | ~0.5d  |
| P9.15 | **New `docs/advanced-config.md`.** Every `AGT_*` flag that is not in the **Required** set above. Grouped by purpose: provider tuning, search depth, PDF attachments, rate guards, Docker/data dir, MCP server. Links into `docs/api.md` and `docs/settings.md` for canonical definitions. The page makes it explicit that nothing here is needed to start.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | ~0.25d |
| P9.16 | **MkDocs nav and landing redesign.** New nav (see proposed shape in §Docs Tree Below). New `docs/index.md` lead — three cards: Install, Manual, Power user. Move planning docs and historical action plans into a collapsed "Project" section. Verify `mkdocs build --strict` is clean and `markdownlint-cli2` is clean.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | ~0.25d |
| P9.17 | **Telemetry-free first-run manual smoke.** Add a one-page checklist `docs/install.md#smoke-checklist` that a fresh user can run on macOS, Linux, and Windows. Use it once per platform before tagging the v1.0.0 release and record the verified date in the table.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | ~0.25d |

**Acceptance (P9.C):**

- New `docs/install.md`, `docs/keys.md`, `docs/advanced-config.md` exist and
  pass `markdownlint-cli2` and `mkdocs build --strict`.
- `README.md` Quick Start is three steps. The developer install is one
  collapsed section.
- The MkDocs landing page has three cards and ten total nav entries (today: 16).
- Every external service that exposes a key referenced in `.env.example` is
  documented in `docs/keys.md` with a link to the console.

---

## Proposed Docs Tree (P9.16)

```text
Overview
  Home (cards: Install / Manual / API)
Get Started
  Install (docs/install.md)
  Get Your Keys (docs/keys.md)
  User Manual (docs/user-manual.md)
Power User
  Advanced Config (docs/advanced-config.md)
  Configuration & Usage (docs/manual.md)
  Deployment & Hosting (docs/deployment.md)
Reference
  REST API (docs/api.md)
  Provider Inventory (docs/providers.md)
  Settings (docs/settings.md)
  Security (docs/security.md)
  Zotero Add-on (docs/zotero.md)
  P1 Benchmark (docs/benchmark.md)
Project
  Roadmap (docs/core.md)
  Action Plan (docs/actionable-plan.md)
  History (docs/actionable-plan-done.md, docs/actionable-plan-done-2.md)
  Priorities (docs/priorities.md)
  Next Steps (docs/next-steps.md)
```

---

## Sequencing

Each tranche is shippable on its own. Recommended order:

1. **P9.A** — release pipeline + first-run polish. This is what unlocks the
   "share with a friend" path the user wants. Two days of work and most of it
   is already coded; we are wiring and verifying.
2. **P9.C** (in parallel after P9.5 lands) — documentation. Writing while the
   release pipeline cooks. The new docs are the artefact a v1.0.0 release
   announcement points at.
3. **P9.B** — search fields. Most valuable to existing users, but the install
   gap blocks new users entirely, so it goes last. The market table above
   confirms Author + Venue + Seed DOI as table stakes, not differentiators —
   we are catching up here, not leading.

---

## Risk Register

| Risk                                                                  | Likelihood | Mitigation                                                                                                                  |
| --------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------- |
| Windows / Linux PyInstaller surprises                                  | Medium     | P9.1 runs in CI before any tag. Time-box at ~0.75d; if a platform refuses, ship macOS + Linux first and Windows in v1.0.1. |
| macOS Gatekeeper friction breaks the "no terminal" promise            | Medium     | P9.4 ships an inline note in the FirstRunDialog and a `docs/install.md` admonition. Long-term: Apple Developer cert.       |
| Author resolver returns the wrong person ("J. Smith" disambiguation)  | Medium     | P9.7 returns up to 5 ranked candidates with `works_count`, OpenAlex affiliation, and ORCID. The user picks before search. |
| Venue resolution drifts (journal-merge events, deprecated venues)     | Low        | OpenAlex is the canonical source; fall back to free-text venue name only when no ID resolves.                              |
| Docs sprawl — three new MD files plus rewrites                        | Low        | P9.16 enforces the new nav and the markdownlint + mkdocs-strict gates catch dead links and stale tables.                   |
| Self-update misfires (`update.rdf` ID mismatch)                        | Low        | P9.2 + P9.3 verified by `v1.0.0-rc.1` → `v1.0.0-rc.2` chain before tagging `v1.0.0`. Roll back is `Disable add-on`.        |
| Author/Venue contract change breaks the API contract version          | Medium     | Bump `REQUIRED_API_CONTRACT_VERSION` in `zotero-addon/src/shared/contracts.ts`. Plugin already validates compatibility.   |

---

## Quality Gates

Every P9 PR runs the same gates as P8:

```bash
# Python
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none

# Zotero add-on
cd zotero-addon && npm ci && npm run lint && npm run build && npm run typecheck && npm run test

# Docs
npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" "examples/**/*.md" ".github/**/*.md" "zotero-addon/README.md"
uv run mkdocs build --strict
```

Plus three P9-specific manual smokes recorded in `docs/install.md`:

- Fresh macOS arm64: install XPI → paste keys → run search → write to Zotero.
- Fresh Linux x86_64: same.
- Fresh Windows x64: same.

---

## Out of Scope for P9

- macOS / Windows code signing (planned for v1.1, see `docs/local-first.md` Part 7).
- Hosted SaaS tier (planned for "Later / SaaS phase" release in `docs/core.md`).
- New academic providers beyond the 9 already in P8.
- Reranker / model swaps. P8.10 covered the key-validation surface.
- Title and abstract fields as separate inputs (low marginal value over the
  query box; revisit if user research shows otherwise).
