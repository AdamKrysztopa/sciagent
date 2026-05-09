# Zotero Add-on Development Plan (AGT Native Plugin)

**Assuming Core Backend (AGT-1 through AGT-8) is complete, with AGT-28 required before filterable add-on work and backend contract follow-up required before capability-driven search can ship cleanly**

**Goal:** Turn the existing Python LangGraph + FastAPI backend into a **seamless native Zotero 9 workspace centered on the main library window**.
No more browser tab. Open SciAgent from Zotero's main window → set deterministic filters and source selection before search → approve → items appear instantly in your library (idempotent, with PDF attach if enabled).

**Zotero 9 is the supported M6 target; Zotero 7 compatibility is unclaimed and untested.**

**Scope:** Pure Zotero plugin (TypeScript + WebExtension manifest).
**Leverages:** Existing backend APIs (`/health`, `/run`, `/resume`, `/status/{run_id}`) plus planned capability and initial-search contract extensions for source filters, attachment metadata, and settings awareness.
**Target Release:** Q2 2026 (as promised in marketing).

## M6.1 Planning Corrections

- Primary UX is main-window or library-pane-first. The current item-details or item-pane MVP may remain a secondary launcher, but it is not the product-defining surface.
- Visual design must follow Zotero-native pane conventions rather than a chat-style panel that clashes with the rest of the app.
- Settings are split from backend-owned secrets. Add-on preferences may store backend URL, backend API key, client ID, and local defaults; backend provider and source credentials stay in backend env and `.env.example`.
- Deterministic filters and source/search-tool selection must be captured before the first backend search call. They are a search contract, not a post-results refinement.
- Backend capability metadata must drive which filters, sources, source states, and PDF actions the add-on can expose.

---

# Epic: ZAP-1 — Plugin Foundation & Tooling

- Type: Epic
- Priority: P0
- Estimate: 2d
- Dependencies: None (core backend already deployed)
- Goal: Zero-to-working skeleton using official 2026 best practices.

## Story: ZAP-0 — Zotero Add-on Template Bootstrap

- Type: Story
- Parent: ZAP-1
- Priority: P0
- Estimate: 0.5d
- Acceptance Criteria:
  - Clone & configure `windingwind/zotero-addon-template` (latest 2026 version).
  - TypeScript + esbuild + hot-reload enabled.
  - `manifest.json` + `bootstrap.js` generated with correct plugin ID (`agt@yourdomain.org`).
  - Plugin loads in Zotero 9 with "AGT" menu item and an empty main-window workspace shell.

## Story: ZAP-1 — Development Environment & Hot Reload

- Type: Story
- Parent: ZAP-1
- Priority: P0
- Estimate: 0.5d
- Acceptance Criteria:
  - Extension proxy file for loading from source.
  - `npm run build` → `.xpi` auto-generated.
  - Repo quality gate validates `npm run lint`, `npm run build`, `npm run typecheck`, and `npm run test` against `zotero-addon/` in CI.
  - Zotero debug output + JS console connected: Tools → Developer → Error Console (`Cmd+Shift+Z` / `Ctrl+Shift+Z`) for bootstrap errors, chrome registration failures, and runtime exceptions.
  - `zotero-types` package installed for full autocomplete.

## Story: ZAP-2 — Backend Connection Layer

- Type: Story
- Parent: ZAP-1
- Priority: P0
- Estimate: 1d
- Acceptance Criteria:
  - Configurable backend URL (default: `http://localhost:8000` or self-hosted).
  - `fetch` wrapper with auth (backend API key from Zotero prefs).
  - Health and capabilities check on plugin load with clear connection status in the main-window surface or settings pane.
  - Only backend URL, backend API key, client ID, and local UX defaults are stored in the add-on (via `Zotero.Prefs`).
  - Provider/search-source secrets remain backend-owned in backend env and `.env.example`; the add-on consumes capability metadata instead of collecting those secrets.
  - Capability payload exposes contract version, enabled sources/search tools, per-source filter support, per-source status reasons, and PDF/attachment support needed by the UI.

# Epic: ZAP-2 — Native Main-Window UI

- Type: Epic
- Priority: P0
- Estimate: 4.25d
- Dependencies: ZAP-1
- Goal: Zotero-native main-window search, pre-search filtering, and approval experience that feels consistent with the rest of Zotero (no browser).

## Story: ZAP-3 — Library-Window Workspace & Entry Points

- Type: Story
- Parent: ZAP-2
- Priority: P0
- Estimate: 1d
- Acceptance Criteria:
  - Primary workflow opens from the Zotero main window (menu, toolbar, or library-window pane/tab) without requiring an item selection.
  - Item-details or reader-side integration, if kept, deep-links into the same workspace rather than owning a separate UI state machine.
  - Layout and interactions follow Zotero-native pane conventions rather than a detached chat-style panel.
  - AGT icon and entry points are visible from standard Zotero surfaces.

## Story: ZAP-4 — Main-Window Search Flow

- Type: Story
- Parent: ZAP-2
- Priority: P0
- Estimate: 1d
- Acceptance Criteria:
  - Query input + “Search” button (or Enter) in the main-window workspace.
  - User can set deterministic filters before the first search: year min/max or date range, open-access preference, citation threshold, document type, include terms, exclude terms, collection target, and PDF preference where relevant.
  - User can set source/search-tool inclusion before the first search, driven by backend capability metadata.
  - Initial search call sends structured filters and source/search-tool selections to the backend; hard filters are applied before semantic rewrite/search and before candidate results are produced.
  - Candidate list renders stable indices, summaries, checkboxes, applied filters, and source-state summary while the workflow waits for approval.
  - Source-state summary separates used, disabled by user, unavailable because backend key/config is missing, skipped by policy or unsupported filter, failed at runtime, and queried-with-zero-results; a source appears in exactly one terminal state per run.
  - “Recent” boost and dedup already handled by backend.

## Story: ZAP-4A — Pre-Search Filter Composer & Review Surface

- Type: Story
- Parent: ZAP-2
- Priority: P0
- Estimate: 0.75d
- Dependencies: ZAP-4, Core backend AGT-28
- Acceptance Criteria:
  - User can inspect and edit deterministic filters before the first search and before accepting a result set.
  - Filter controls include year min/max, date range, source/search-tool toggles, open-access preference, citation threshold, document type, include terms, and exclude terms.
  - UI distinguishes hard filters from soft preferences and warns when a source cannot enforce a filter server-side.
  - Backend capability metadata determines which controls are enabled and what explanatory copy to show.
  - Structured filters are sent on the initial search request and on re-runs instead of being re-encoded only as natural language.
  - Candidate list displays which sources were used, disabled by user, skipped by policy, failed, or unavailable because optional backend-side keys were not configured.

## Story: ZAP-5 — Approval & Collection UI

- Type: Story
- Parent: ZAP-2
- Priority: P0
- Estimate: 1.5d
- Acceptance Criteria:
  - “Create Collection” field (auto-suggest name).
  - Approve / Reject / Edit buttons.
  - Progress spinner + item-by-item success (green checkmarks).
  - Review and approval stay in the same main-window workspace and follow Zotero-native interaction patterns better than the current item-details MVP.

# Epic: ZAP-3 — Zotero Write Integration

- Type: Epic
- Priority: P0
- Estimate: 3d
- Dependencies: ZAP-1, ZAP-2, Core backend (AGT-11)
- Goal: Direct native writes — no pyzotero needed.

## Story: ZAP-6 — Collection Resolver (Native)

- Type: Story
- Parent: ZAP-3
- Priority: P0
- Estimate: 0.75d
- Acceptance Criteria:
  - Uses `Zotero.Collections.getByName()` + create if missing.
  - Parent collection support via Zotero API.

## Story: ZAP-7 — Idempotent Item Creation

- Type: Story
- Parent: ZAP-3
- Priority: P0
- Estimate: 1.5d
- Acceptance Criteria:
  - Calls backend for normalized data → maps to `Zotero.Item` template.
  - DOI + title-hash dedup before `Zotero.Items.add()`.
  - Partial success reporting back to UI.

## Story: ZAP-8 — PDF Attachment (Native)

- Type: Story
- Parent: ZAP-3
- Priority: P1
- Estimate: 0.75d
- Acceptance Criteria:
  - Backend returns attachment candidate metadata (preferred PDF URL or explicit unavailable reason) for each approved paper.
  - Add-on supports a saved default and per-run override for PDF import.
  - PDF import runs after successful item creation via `Zotero.Attachments.importFromURL()` with duplicate-attachment and idempotency rules explicit.
  - Attachment failures are reported per item and never corrupt the primary item write flow.

# Epic: ZAP-4 — Polish, Packaging & Distribution

- Type: Epic
- Priority: P0
- Estimate: 3d
- Dependencies: ZAP-3
- Goal: Ship-ready plugin.

## Story: ZAP-9 — Settings Panel, Secrets Boundary & Saved Defaults

- Type: Story
- Parent: ZAP-4
- Priority: P0
- Estimate: 0.75d
- Acceptance Criteria:
  - Zotero Tools → Add-ons → AGT Preferences is split into Connection & Auth (backend URL, backend API key, client ID) and Search Defaults & Sources (default collection, deterministic filter defaults, source/search-tool toggles, PDF default).
  - Preferences explain that provider/search-source secrets are backend-owned and are not entered in the add-on.
  - Preferences include default keyless source policy and opt-in toggles only for keyed/paid sources already exposed by backend capability metadata.
  - Preferences include saved filter defaults for pre-search execution, not just post-results refinement.
  - Preferences expose backend contract version or last capability refresh status for troubleshooting.

## Story: ZAP-10 — Error Handling & Offline Mode

- Type: Story
- Parent: ZAP-4
- Priority: P1
- Estimate: 1d
- Acceptance Criteria:
  - Graceful fallback messages.
  - Local cache of last results.

## Story: ZAP-11 — Build, Sign & Publish

- Type: Story
- Parent: ZAP-4
- Priority: P0
- Estimate: 1.25d
- Acceptance Criteria:
  - `npm run build` → signed `.xpi`.
  - GitHub Actions workflow for auto-release.
  - Listed on Zotero plugin directory + GitHub Releases.

# Release: AGT Zotero Add-on MVP

- Type: Release
- Priority: P0
- Estimate: 12.25d total
- Dependencies: All ZAP-1 to ZAP-4 stories plus ZAP-4A
- Acceptance Criteria:
  - Main-window search workspace appears in Zotero.
  - Settings panel separates connection/auth from saved search defaults; backend provider/source secrets remain backend-owned in env.
  - Full natural-language search → set deterministic pre-search filters and source/search-tool selection → approve → items in library (idempotent).
  - Deterministic filters are applied before semantic search and before results are shown.
  - Source availability is transparent: used, disabled by user, unavailable because backend keys/config are missing, skipped by policy, failed, and zero-result sources are shown distinctly, with one terminal state per source.
  - Default paper discovery works with the backend's keyless/easy-access source policy; optional search-engine API keys are enrichment only and never requested by the add-on.
  - Optional PDF attachment path shows deterministic per-item outcomes.
  - Capability and version handshake succeeds against the supported backend contract.
  - Works with local or self-hosted backend.
  - One-click install via .xpi.
  - Feels visually and structurally consistent with Zotero rather than a detached chat demo.

**Tech Stack for Add-on (2026 native)**

- TypeScript + `zotero-addon-template`
- React 18 + Tailwind (via template)
- Zotero JS API (`Zotero.*`)
- `fetch` to core backend
- esbuild + hot reload

**Next Steps After This Plan**

1. `npx create-zotero-plugin` (or clone template) — done in 5 minutes.
2. First story (ZAP-0) gives you a working empty sidebar today.

The plugin scaffold is decoupled from Python implementation work, but the main-window search UX now depends on backend capability metadata, initial-search filter/source contract updates, PDF capability/status reporting, and AGT-28 search-plan metadata.

Want me to generate:

- The exact `manifest.json` + `bootstrap.js` starter
- Full React sidebar component skeleton
- Or the GitHub Actions build workflow?

Just say the word and we start coding the add-on tomorrow.

AGT is about to live **inside** Zotero. Let’s make it happen. 🚀
