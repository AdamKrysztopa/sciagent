# Zotero Add-on Development Plan (AGT Native Plugin)  
**Assuming Core Backend (AGT-1 through AGT-8) is 100% complete**

**Goal:** Turn the existing Python LangGraph + FastAPI backend into a **seamless native sidebar inside Zotero 7+**.  
No more browser tab. One-click “Search Papers” in Zotero → natural language → approve → items appear instantly in your library (idempotent, with PDF attach if enabled).

**Scope:** Pure Zotero plugin (TypeScript + WebExtension manifest).  
**Leverages:** Already-built backend APIs (`/search`, `/run-workflow`, `/resume`, `/status`).  
**Target Release:** Q2 2026 (as promised in marketing).

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
  - Plugin loads in Zotero 7+ with “AGT” menu item and empty sidebar.

## Story: ZAP-1 — Development Environment & Hot Reload
- Type: Story
- Parent: ZAP-1
- Priority: P0
- Estimate: 0.5d
- Acceptance Criteria:
  - Extension proxy file for loading from source.
  - `npm run build` → `.xpi` auto-generated.
  - Zotero debug output + JS console connected.
  - `zotero-types` package installed for full autocomplete.

## Story: ZAP-2 — Backend Connection Layer
- Type: Story
- Parent: ZAP-1
- Priority: P0
- Estimate: 1d
- Acceptance Criteria:
  - Configurable backend URL (default: `http://localhost:8000` or self-hosted).
  - `fetch` wrapper with auth (API key from Zotero prefs).
  - Health check on plugin load (green/red status in sidebar).
  - Secrets never stored in plugin (use Zotero.Prefs).

# Epic: ZAP-2 — Native Sidebar UI
- Type: Epic
- Priority: P0
- Estimate: 3.5d
- Dependencies: ZAP-1
- Goal: Beautiful, Zotero-native chat experience (no browser).

## Story: ZAP-3 — Sidebar Registration & Layout
- Type: Story
- Parent: ZAP-2
- Priority: P0
- Estimate: 1d
- Acceptance Criteria:
  - Uses Zotero 7+ custom pane API (`Zotero.ItemPaneManager.registerSection` or reader sidebar).
  - Collapsible vertical sidebar with AGT icon.
  - Chat-like interface (React + Tailwind for speed).

## Story: ZAP-4 — Natural Language Search Flow
- Type: Story
- Parent: ZAP-2
- Priority: P0
- Estimate: 1d
- Acceptance Criteria:
  - Input box + “Search” button (or Enter).
  - Calls backend `/search` → renders card list with stable indices, summaries, checkboxes.
  - “Recent” boost and dedup already handled by backend.

## Story: ZAP-5 — Approval & Collection UI
- Type: Story
- Parent: ZAP-2
- Priority: P0
- Estimate: 1.5d
- Acceptance Criteria:
  - “Create Collection” field (auto-suggest name).
  - Approve / Reject / Edit buttons (React fragments).
  - Progress spinner + item-by-item success (green checkmarks).
  - Matches exact UX from marketing demo.

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
  - Backend returns PDF URL → `Zotero.Attachments.importFromURL()`.
  - Checksum stored in extra field.
  - Feature flag in plugin prefs.

# Epic: ZAP-4 — Polish, Packaging & Distribution
- Type: Epic
- Priority: P0
- Estimate: 3d
- Dependencies: ZAP-3
- Goal: Ship-ready plugin.

## Story: ZAP-9 — Preferences Pane & Config
- Type: Story
- Parent: ZAP-4
- Priority: P0
- Estimate: 0.75d
- Acceptance Criteria:
  - Zotero Tools → Add-ons → AGT Preferences (backend URL, API key, PDF toggle).

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
- Estimate: 11.5d total
- Dependencies: All ZAP-1 to ZAP-4 stories
- Acceptance Criteria:
  - Sidebar appears in Zotero.
  - Full natural-language search → approve → items in library (idempotent).
  - Works with local or self-hosted backend.
  - One-click install via .xpi.
  - Matches the exact 38-second demo from marketing speech.

**Tech Stack for Add-on (2026 native)**
- TypeScript + `zotero-addon-template`
- React 18 + Tailwind (via template)
- Zotero JS API (`Zotero.*`)
- `fetch` to core backend
- esbuild + hot reload

**Next Steps After This Plan**
1. `npx create-zotero-plugin` (or clone template) — done in 5 minutes.
2. First story (ZAP-0) gives you a working empty sidebar today.

This plan is **completely decoupled** from the Python core — you can ship the add-on independently while the backend runs locally or in the cloud.

Want me to generate:
- The exact `manifest.json` + `bootstrap.js` starter
- Full React sidebar component skeleton
- Or the GitHub Actions build workflow?

Just say the word and we start coding the add-on tomorrow.  

AGT is about to live **inside** Zotero. Let’s make it happen. 🚀