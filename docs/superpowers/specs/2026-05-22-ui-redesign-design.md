# Spec C — Zotero Sidebar UI Redesign

**Date:** 2026-05-22
**Status:** Approved — ready for implementation planning
**Scope:** `zotero-addon/` frontend only (TypeScript + React). No backend changes required.

---

## 1. Problem Statement

The current sidebar mixes configuration fields, health status, banner messages, and the search form
into a single undifferentiated scroll. New users cannot tell where to start. Experienced users cannot
scan the state of a running search at a glance. The information hierarchy is flat.

---

## 2. Design Principles

- **Zotero-native chrome.** Dark gray palette matching Zotero's own UI (`#3c3c3c` header, `#2d2d2d`
  panels, `#333` inputs). No custom dark-mode or light-mode themes. Blends in rather than standing
  out.
- **Three permanent zones.** Every screen state uses the same layout skeleton. The user always knows
  where to look.
- **Progressive disclosure.** Advanced options are collapsed by default and revealed on demand.
  Phase-specific content (running, review, done) replaces the idle form rather than stacking on top.
- **Settings live in Zotero's preference pane.** The sidebar does not embed a settings form. The ⚙
  button opens the existing Zotero preferences dialog. The button signals config problems via colour.

---

## 3. Shell Structure

```
┌─ Zone 1: Header bar (always visible, ~28px) ─────────────────┐
│  SciAgent  ● status-pill                         ⚙ button     │
├─ Zone 2: Health strip (always visible, ~38px) ────────────────┤
│  ✓ Backend · ✓ Zotero · ✓ LLM                                 │
│  + S2 key → faster results · + Core → more OA papers          │
├─ Zone 3: Content (flex-fill, scrollable) ──────────────────────┤
│  Phase-driven content (idle / running / review / done)         │
└────────────────────────────────────────────────────────────────┘
```

### Zone 1 — Header bar

| Element | Detail |
|---|---|
| App name | "SciAgent" — `font-weight: 700`, `color: #e0e0e0` |
| Status pill | Rounded pill beside the name. Colour and label change per phase (see §5). |
| ⚙ button | Opens existing Zotero preferences dialog. **Border and text turn `#e05c5c` (red) when minimum config is missing** (backend URL, Zotero API key, or LLM key absent). Grey (`#555`) otherwise. |

### Zone 2 — Health strip

Two rows, always visible, never removed:

- **Row 1 — minimum required:** `✓ Backend · ✓ Zotero · ✓ LLM` — each item green (`#4ade80`)
  when healthy, red (`#e05c5c`) when failing, yellow (`#facc15`) when pending.
- **Row 2 — optional extras hint:** Inline nudges for unconfigured optional keys, e.g.
  `+ S2 key → faster results · + Core → more OA papers`. Hidden once all optional keys are set.

### Zone 3 — Content

Phase-driven. The four states are described in §5–§8.

---

## 4. Design Language (Zotero-native)

| Token | Value |
|---|---|
| Header background | `#3c3c3c` |
| Health strip background | `#2d2d2d` |
| Content background | `#252525` |
| Input / card background | `#333` |
| Border default | `1px solid #555` |
| Border subtle | `1px solid #444` |
| Text primary | `#e0e0e0` |
| Text secondary | `#aaa` |
| Text muted | `#777` |
| Accent blue | `#1d6bbf` (Search button, links) |
| Accent green | `#4ade80` (healthy, selected, approved) |
| Accent yellow | `#facc15` (running, in-progress) |
| Accent purple | `#c084fc` (awaiting approval) |
| Accent red | `#e05c5c` (error, unconfigured) |
| Base font size | `0.78rem` (sidebar constraint) |
| Border radius | `3–4px` |

---

## 5. Phase: Idle (Search Form)

### Collapsed (default)

```
[ Search query textarea — 3 rows                      ]
[ Collection dropdown ▾ ]  [ Year dropdown ▾          ]
▸ Advanced filters (author, keywords, citations…)
[ Search ]  [ ABC✓ ]  [ ⚑ ]
```

**Toolbar icons:**
- `ABC✓` — spell-check the query in-place, briefly shows diff before applying.
- `⚑` — extract keywords from the currently selected Zotero item, populates query + keywords fields.

### Expanded (user clicks ▸)

The toggle becomes `▾ Advanced filters` and reveals a bordered block:

| Field | Type | Notes |
|---|---|---|
| Author | Text input | Single name fragment |
| Must include keywords | Text input | Comma-separated |
| Exclude keywords | Text input | Comma-separated |
| Min citations | Number input | Default empty (no minimum) |
| Open access only | Checkbox | Filters to OA results |
| Venue / journal | Text input | Abbreviation or full name |

The advanced block collapses when the user clicks `▾` again. State persists across searches within the session.

**Year dropdown options:** Any year / ≥ 2024 / ≥ 2022 / ≥ 2020 / Custom (shows year input).

---

## 6. Phase: Running (Progress)

Status pill: `● running` (yellow `#facc15`, background `#2a2000`).

Header row gains a `✕ Cancel` button (grey, right-aligned). Pressing it sends a cancel request and
returns to idle.

### Query echo

```
Searching for
"<original query>"
→ rewritten: "<LLM-rewritten query>"   ← appears once LLM step completes
```

### Pipeline tracker

Ordered list of phases. Each row: status icon · label · elapsed time (on completion).

| Icon | Meaning |
|---|---|
| `✓` green | Completed |
| `⟳` yellow (animated) | In progress |
| `○` grey | Pending |
| `✕` red | Failed / skipped |

Pipeline phases in order:
1. Spell-check query
2. LLM query rewrite
3. Fetch sources *(shows "N / 8 done" counter while running)*
4. Merge & deduplicate
5. Rank & rerank

### Per-source status

Displayed as a list once "Fetch sources" begins. Each row: source name · status.

Status values: `waiting` (grey) → `⟳ fetching…` (yellow, row highlighted) → `✓ N papers` (green)
/ `✕ timeout` (red, non-blocking).

Sources: S2, OpenAlex, arXiv, PubMed, CORE, Europe PMC, Crossref, BASE.

A timed-out or errored source is shown in red but does not block results — the pipeline continues
with successful sources.

---

## 7. Phase: Review / Awaiting Approval

Status pill: `● awaiting approval` (purple `#c084fc`, background `#1e0a2e`).

### Summary bar (pinned top of Zone 3)

```
Found 23 papers · 18 selected     [ all ] [ ★★★ ] [ none ]
```

Quick-select buttons toggle all / top-ranked / none.

### Paper list (scrollable)

Each paper card:

```
☑  Title of the Paper                           ← checkbox left-aligned
   Author et al. · Year · Venue
   ★★★  [S2]  14,203 cit.  [OA]
   Abstract snippet (first ~150 chars)…          ← shown for ★★★ and ★★☆
```

| Element | Detail |
|---|---|
| Checkbox | Checked = include in Zotero write. Unchecked = skip. |
| Title | Full title. Clickable → opens DOI/URL in system browser. |
| Authors | "First-author et al." format. |
| Year · Venue | Publication year + venue abbreviation (NeurIPS, Nature, etc.). |
| ★ rank | 1–3 stars from reranker score. 3 stars → dark green card. 1 star → greyed, no abstract. |
| Source badge | Coloured pill: S2 / OAlex / arXiv / EPMC / CORE / Crossref / BASE. |
| Citation count | From Semantic Scholar or OpenAlex. |
| OA badge | Blue "OA" pill when open-access PDF is available. |
| Abstract snippet | ~150 chars, shown only for ★★★ and ★★☆ papers. |

Unchecked (deselected) cards: reduced opacity (0.7), no abstract, no coloured border.

### Action bar (pinned bottom of Zone 3)

```
[ ✓ Add 18 to Zotero ]  [ ↩ New search ]
```

- **Add to Zotero** — calls `POST /resume/{run_id}` with the checked paper IDs. Button label updates
  dynamically with the current checked count.
- **New search** — discards the current run and returns to idle state.

---

## 8. Phase: Done

Status pill returns to `● idle` (green).

Zone 3 shows a centred confirmation card:

```
    ✓
18 papers added to Zotero
in collection: Inbox

📄 18 added · 5 skipped (already in library)
⏱ 8.4s total

[ New search ]  [ View in Zotero ]
```

- **View in Zotero** — focuses the target collection in the Zotero main panel (calls
  `Zotero.getActiveZoteroPane().selectCollection(...)` if the host API permits).
- After ~30 seconds idle on this screen the sidebar auto-returns to idle with the search form.

---

## 9. Settings Panel (no change to existing pane)

The settings panel remains the existing Zotero preferences dialog, accessed via **Edit → Preferences
→ SciAgent** (or **Zotero → Preferences → SciAgent** on macOS). No form is embedded in the sidebar.

The ⚙ button in the sidebar header calls `Zotero.openPreferences('SciAgent')`.

**"Minimum to work" check** — at startup and after any config change, the addon evaluates whether
these three values are present and non-empty:

1. Backend URL (`extensions.agt.backendUrl`)
2. Zotero API key (`extensions.agt.zoteroApiKey`)
3. LLM key (any of `extensions.agt.openaiApiKey`, `anthropicApiKey`, `xaiApiKey`, `groqApiKey`)

If any are absent, the ⚙ button renders with a red border and label:
`border: 1px solid #e05c5c; color: #e05c5c`. When all three are present, the button is grey.

---

## 10. State Machine

```
idle → submitting → running → awaiting_approval → resuming → completed
                ↘ error / failed / rejected → idle
```

The status pill in Zone 1 maps directly to the `RunPhase` enum from the existing backend contract.
No new states are needed.

**Status pill colours per phase:**

| Phase | Label | Text/border colour | Background |
|---|---|---|---|
| `idle` | ● idle | `#4ade80` | `#0d2318` |
| `submitting` | ● submitting | `#facc15` | `#2a2000` |
| `running` | ● running | `#facc15` | `#2a2000` |
| `awaiting_approval` | ● awaiting approval | `#c084fc` | `#1e0a2e` |
| `resuming` | ● saving… | `#facc15` | `#2a2000` |
| `completed` | ● idle | `#4ade80` | `#0d2318` |
| `error` / `failed` | ● error | `#e05c5c` | `#2a0a0a` |

**Running state header:** The ⚙ settings button is replaced by `✕ Cancel` while `RunPhase` is
`submitting`, `running`, or `resuming`. It reappears (as grey ⚙ or red ⚙) once the phase
exits back to idle/error.

---

## 11. Component Breakdown

| Component | Responsibility |
|---|---|
| `SciAgentSidebar` | Root — renders zones 1/2/3, reads `RunPhase` |
| `HeaderBar` | Zone 1: title, status pill, settings button (red logic) |
| `HealthStrip` | Zone 2: min-required row + optional extras hint |
| `IdleView` | Zone 3 idle: query form, dropdowns, collapsible `AdvancedFilters` |
| `AdvancedFilters` | Collapsible panel: author, keywords, min-citations, OA, venue |
| `RunningView` | Zone 3 running: query echo, pipeline tracker, `SourceGrid` |
| `PipelineTracker` | Ordered phase list with icon + elapsed time |
| `SourceGrid` | Per-source status list |
| `ReviewView` | Zone 3 review: summary bar, `PaperList`, action bar |
| `PaperCard` | Individual paper row: checkbox, title, authors, badges, abstract |
| `DoneView` | Zone 3 done: confirmation card + action buttons |

All existing Zotero host API calls stay in `src/host/` adapters. No `Zotero.*` calls in leaf
components.

---

## 12. Acceptance Criteria

- [ ] Three-zone layout renders at all sidebar widths (240px–400px).
- [ ] ⚙ button is red when any of backend URL / Zotero key / LLM key is absent; grey otherwise.
- [ ] ⚙ button opens Zotero preferences pane to the SciAgent tab.
- [ ] Advanced filters panel collapses and expands; state persists within the session.
- [ ] `ABC✓` spell-check populates the query field in-place.
- [ ] `⚑` keyword extraction reads the selected Zotero item and populates the query + keywords.
- [ ] Running state shows pipeline phases with live icons; per-source status updates as sources complete.
- [ ] A timed-out source shows red ✕ but does not block the rest of the pipeline.
- [ ] Review list shows title, author/year/venue, stars, source badge, citation count, OA badge.
- [ ] Abstract snippet shown for ★★★ and ★★☆ papers; hidden for ★☆☆.
- [ ] Quick-select buttons (all / ★★★ / none) correctly toggle checkboxes.
- [ ] "Add to Zotero" button label reflects the live checked count.
- [ ] Done screen shows added count, skipped count, and elapsed time.
- [ ] All quality gates pass: `npm run lint && npm run build && npm run typecheck && npm run test`.

---

## 13. Out of Scope

- Dark/light theme toggle (Zotero-native only).
- Settings fields inside the sidebar (stays in Zotero prefs pane).
- Backend API changes (frontend reads existing `/status`, `/run`, `/resume`, `/health` endpoints).
- Watches, gap-finder, library-doctor UI (future spec).
