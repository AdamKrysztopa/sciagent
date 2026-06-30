# SciAgent Zotero Add-on — UI Redesign Plan

> Target: replace the current bare window with a fully functional,
> Zotero-native four-state interface. No external React or CSS framework
> required — pure XUL/HTML inside the plugin sandbox.

---

## What the current state is

From the screenshots: the Tools menu correctly registers "SciAgent"
(ZAP-1 done ✅). The window that opens shows a titlebar and what
appears to be an empty or near-empty panel — no query input, no filter
controls, no results surface. The underlying Zotero library items are
visible behind it, which suggests the window is transparent or unstyled.

---

## Four states the UI must handle

Every state lives in the same window. JavaScript swaps which section
is visible; the titlebar and backend status pill are always shown.

| State                  | Trigger               | What user sees                                                                         |
| ---------------------- | --------------------- | -------------------------------------------------------------------------------------- |
| **1 — Idle / compose** | Window opens          | Query input, collection field, filter controls, source chips, hint text                |
| **2 — Running**        | Search button clicked | Locked plan pill, per-source progress chips, spinner                                   |
| **3 — Review**         | Results arrive        | Plan summary, tabbed results list with checkboxes/scores/summaries, approve/reject bar |
| **4 — Done**           | Approve clicked       | Per-item write status (created / unchanged / failed), new-search button                |

---

## File structure to create / modify

All paths relative to `zotero-addon/`.

```
addon/
  content/
    sciagent.xhtml        ← main window XUL/HTML (create or replace)
    sciagent.css          ← all styles (create or replace)
  icons/
    sciagent-16.png       ← already exists (keep)
    sciagent-32.png       ← already exists (keep)
src/
  modules/
    sciagentWindow.ts     ← window controller (create or replace)
  api/
    backendClient.ts      ← fetch wrapper (create or replace)
```

---

## Design tokens (match Zotero 9 native look)

Zotero 9 uses the Firefox 115 platform. CSS custom properties work.
Use these everywhere — never hardcode hex values.

```css
/* In sciagent.css — top of file */
:root {
  --agt-surface: -moz-dialog; /* matches Zotero panel bg */
  --agt-surface-raised: rgba(255, 255, 255, 0.06);
  --agt-border: rgba(0, 0, 0, 0.12);
  --agt-border-strong: rgba(0, 0, 0, 0.25);
  --agt-text: -moz-dialogtext;
  --agt-text-muted: rgba(128, 128, 128, 0.9);
  --agt-accent: #1d9e75; /* SciAgent brand green */
  --agt-accent-dim: rgba(29, 158, 117, 0.15);
  --agt-amber: #ba7517;
  --agt-amber-dim: rgba(250, 199, 117, 0.25);
  --agt-radius: 6px;
  --agt-radius-sm: 4px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --agt-surface-raised: rgba(255, 255, 255, 0.04);
    --agt-border: rgba(255, 255, 255, 0.1);
    --agt-border-strong: rgba(255, 255, 255, 0.22);
  }
}
```

---

## Component-by-component implementation

### A. Titlebar (always visible)

```html
<!-- In sciagent.xhtml -->
<div id="agt-titlebar">
  <span id="agt-title">SciAgent</span>
  <div id="agt-status-pill">
    <span id="agt-status-dot"></span>
    <span id="agt-status-text">connecting…</span>
  </div>
</div>
```

```css
/* sciagent.css */
#agt-titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 0.5px solid var(--agt-border);
  background: var(--agt-surface-raised);
}
#agt-title {
  font-weight: 500;
  font-size: 13px;
}
#agt-status-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 20px;
  background: var(--agt-accent-dim);
  color: var(--agt-accent);
  border: 0.5px solid var(--agt-accent);
}
#agt-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--agt-accent);
}
#agt-status-pill.error {
  background: rgba(226, 75, 74, 0.1);
  color: #a32d2d;
  border-color: #e24b4a;
}
#agt-status-pill.error #agt-status-dot {
  background: #e24b4a;
}
#agt-status-pill.loading {
  background: var(--agt-amber-dim);
  color: var(--agt-amber);
  border-color: var(--agt-amber);
}
```

In `backendClient.ts`:

```typescript
export async function checkHealth(backendUrl: string): Promise<boolean> {
  try {
    const r = await fetch(`${backendUrl}/health`, {
      signal: AbortSignal.timeout(4000),
    });
    return r.ok;
  } catch {
    return false;
  }
}
```

In `sciagentWindow.ts`, on window load:

```typescript
async function updateStatusPill() {
  const pill = doc.getElementById("agt-status-pill")!;
  const text = doc.getElementById("agt-status-text")!;
  pill.className = "loading";
  text.textContent = "connecting…";
  const ok = await checkHealth(getBackendUrl());
  pill.className = ok ? "" : "error";
  text.textContent = ok ? "backend connected" : "backend offline";
}
```

---

### B. State 1 — Idle / compose

```html
<div id="agt-state-idle" class="agt-state">
  <div class="agt-section-label">Research query</div>
  <div class="agt-row">
    <input
      id="agt-query"
      class="agt-input"
      type="text"
      placeholder="e.g. time-series forecasting, not older than 2023"
    />
    <button id="agt-btn-search" class="agt-btn agt-btn-primary">Search</button>
  </div>

  <div class="agt-section-label">Target collection</div>
  <div class="agt-row" style="margin-bottom:12px">
    <input
      id="agt-collection"
      class="agt-input"
      placeholder="Collection name (created if missing)"
    />
  </div>

  <div class="agt-section-label">
    Filters <span class="agt-hint">(applied before search)</span>
  </div>
  <div class="agt-filter-grid">
    <div class="agt-filter-box">
      <div class="agt-filter-label">Year from</div>
      <input
        id="agt-year-min"
        class="agt-filter-input"
        type="number"
        placeholder="any"
        min="1900"
        max="2030"
      />
    </div>
    <div class="agt-filter-box">
      <div class="agt-filter-label">Year to</div>
      <input
        id="agt-year-max"
        class="agt-filter-input"
        type="number"
        placeholder="any"
        min="1900"
        max="2030"
      />
    </div>
    <div class="agt-filter-box">
      <div class="agt-filter-label">Open access</div>
      <select id="agt-oa" class="agt-filter-input">
        <option value="any">Any</option>
        <option value="preferred" selected>Preferred</option>
        <option value="required">Required</option>
      </select>
    </div>
    <div class="agt-filter-box">
      <div class="agt-filter-label">Citations</div>
      <select id="agt-citations" class="agt-filter-input">
        <option value="any" selected>Any</option>
        <option value="cited">Cited (10+)</option>
        <option value="influential">Influential (20+)</option>
      </select>
    </div>
  </div>
  <div class="agt-filter-box" style="margin-bottom:10px">
    <div class="agt-filter-label">Exclude terms (comma separated)</div>
    <input
      id="agt-exclude"
      class="agt-filter-input"
      placeholder="e.g. healthcare, clinical"
    />
  </div>

  <div class="agt-section-label">Sources</div>
  <div id="agt-source-chips" class="agt-chips"></div>
  <!-- chips populated from /health capability response -->

  <div id="agt-idle-hint" class="agt-hint-block">
    Enter a query above and hit Search.<br />
    SciAgent will show you the search plan before writing anything.
  </div>
</div>
```

CSS additions:

```css
.agt-section-label {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--agt-text-muted);
  margin-bottom: 5px;
  margin-top: 10px;
}
.agt-section-label:first-child {
  margin-top: 0;
}
.agt-hint {
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  font-size: 10px;
}
.agt-row {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.agt-input {
  flex: 1;
  border: 0.5px solid var(--agt-border-strong);
  border-radius: var(--agt-radius);
  padding: 7px 10px;
  font-size: 13px;
  color: var(--agt-text);
  background: var(--agt-surface);
}
.agt-input:focus {
  outline: none;
  border-color: var(--agt-accent);
}
.agt-filter-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 6px;
}
.agt-filter-box {
  border: 0.5px solid var(--agt-border);
  border-radius: var(--agt-radius);
  padding: 7px 10px;
  background: var(--agt-surface-raised);
}
.agt-filter-label {
  font-size: 10px;
  color: var(--agt-text-muted);
  margin-bottom: 2px;
}
.agt-filter-input {
  width: 100%;
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 500;
  color: var(--agt-text);
  padding: 0;
  outline: none;
}
.agt-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.agt-chip {
  font-size: 10px;
  padding: 3px 7px;
  border-radius: 20px;
  border: 0.5px solid var(--agt-border);
  color: var(--agt-text-muted);
  background: var(--agt-surface-raised);
  cursor: pointer;
  user-select: none;
}
.agt-chip.on {
  background: rgba(29, 158, 117, 0.12);
  color: var(--agt-accent);
  border-color: var(--agt-accent);
}
.agt-chip.off {
  text-decoration: line-through;
  opacity: 0.45;
}
.agt-hint-block {
  text-align: center;
  padding: 1.5rem 1rem;
  color: var(--agt-text-muted);
  font-size: 12px;
  line-height: 1.6;
}
```

TypeScript — build chips from capability metadata:

```typescript
function renderSourceChips(capabilities: SourceCapability[]) {
  const container = doc.getElementById("agt-source-chips")!;
  container.innerHTML = "";
  for (const cap of capabilities) {
    const chip = doc.createElement("span");
    chip.className = `agt-chip ${cap.enabled ? "on" : "off"}`;
    chip.textContent =
      cap.label + (cap.requiresKey && !cap.keyConfigured ? " (no key)" : "");
    chip.title = cap.enabled ? "Click to disable" : "Click to enable";
    chip.addEventListener("click", () => {
      cap.enabled = !cap.enabled;
      chip.className = `agt-chip ${cap.enabled ? "on" : "off"}`;
    });
    container.appendChild(chip);
  }
}
```

---

### C. State 2 — Running

```html
<div id="agt-state-running" class="agt-state" style="display:none">
  <div class="agt-plan-box">
    <div class="agt-plan-title">Search plan (filters locked)</div>
    <div id="agt-plan-tags" class="agt-plan-tags"></div>
  </div>

  <div
    id="agt-running-chips"
    class="agt-chips"
    style="margin-bottom:14px"
  ></div>

  <div class="agt-spinner-wrap">
    <div class="agt-spinner"></div>
    <div id="agt-running-msg" class="agt-hint-block" style="padding-top:0">
      Querying sources in parallel…
    </div>
  </div>
</div>
```

```css
.agt-plan-box {
  background: var(--agt-amber-dim);
  border: 0.5px solid var(--agt-amber);
  border-radius: var(--agt-radius);
  padding: 8px 10px;
  margin-bottom: 10px;
}
.agt-plan-title {
  font-size: 10px;
  font-weight: 500;
  color: var(--agt-amber);
  margin-bottom: 5px;
}
.agt-plan-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}
.agt-plan-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--agt-surface);
  border: 0.5px solid var(--agt-amber);
  border-radius: 3px;
  padding: 2px 6px;
  font-size: 10px;
  color: var(--agt-amber);
}
.agt-spinner-wrap {
  text-align: center;
  padding: 1.5rem 0;
}
.agt-spinner {
  width: 20px;
  height: 20px;
  margin: 0 auto 10px;
  border: 2px solid var(--agt-border);
  border-top-color: var(--agt-text);
  border-radius: 50%;
  animation: agt-spin 0.7s linear infinite;
}
@keyframes agt-spin {
  to {
    transform: rotate(360deg);
  }
}
```

TypeScript:

```typescript
function renderPlanTags(plan: SearchPlan) {
  const container = doc.getElementById("agt-plan-tags")!;
  const tags: [string, string][] = [
    [
      "📅",
      plan.hardFilters.minYear ? `min_year: ${plan.hardFilters.minYear}` : null,
    ],
    [
      "📅",
      plan.hardFilters.maxYear ? `max_year: ${plan.hardFilters.maxYear}` : null,
    ],
    [
      "✕",
      plan.hardFilters.excludeTerms?.length
        ? `exclude: ${plan.hardFilters.excludeTerms.join(", ")}`
        : null,
    ],
    [
      "🔓",
      plan.hardFilters.openAccess !== "any"
        ? `open_access: ${plan.hardFilters.openAccess}`
        : null,
    ],
  ].filter(([, v]) => v !== null) as [string, string][];

  container.innerHTML = tags
    .map(
      ([icon, label]) => `<span class="agt-plan-tag">${icon} ${label}</span>`,
    )
    .join("");
}
```

---

### D. State 3 — Review

```html
<div
  id="agt-state-review"
  class="agt-state"
  style="display:none; padding-bottom:0"
>
  <div class="agt-row" style="margin-bottom:8px">
    <input id="agt-query-review" class="agt-input" readonly />
    <button id="agt-btn-rerun" class="agt-btn">Re-run</button>
  </div>

  <div
    class="agt-plan-box"
    id="agt-plan-summary"
    style="margin-bottom:8px"
  ></div>

  <div class="agt-tab-row">
    <div class="agt-tab active" data-tab="results">Results</div>
    <div class="agt-tab" data-tab="sources">Sources</div>
    <div class="agt-tab" data-tab="settings">Settings</div>
  </div>

  <div id="agt-tab-results" class="agt-tab-panel">
    <div id="agt-results-list"></div>
    <div id="agt-select-all-row">
      <button id="agt-btn-select-all" class="agt-link-btn">Select all</button>
      <button id="agt-btn-deselect-all" class="agt-link-btn">
        Deselect all
      </button>
    </div>
  </div>

  <div id="agt-tab-sources" class="agt-tab-panel" style="display:none">
    <div id="agt-source-status-list"></div>
  </div>

  <div id="agt-tab-settings" class="agt-tab-panel" style="display:none">
    <!-- re-editable collection name before final approve -->
    <div class="agt-filter-box" style="margin:8px 0">
      <div class="agt-filter-label">Collection name</div>
      <input id="agt-collection-review" class="agt-filter-input" />
    </div>
    <div class="agt-filter-box">
      <div class="agt-filter-label">PDF attachment</div>
      <select id="agt-pdf-attach" class="agt-filter-input">
        <option value="off">Off</option>
        <option value="on">On (open access only)</option>
      </select>
    </div>
  </div>

  <div class="agt-action-bar">
    <button id="agt-btn-approve" class="agt-btn agt-btn-primary"></button>
    <button id="agt-btn-reject" class="agt-btn">Reject</button>
  </div>
</div>
```

```css
.agt-tab-row {
  display: flex;
  border-bottom: 0.5px solid var(--agt-border);
  margin-bottom: 0;
}
.agt-tab {
  padding: 7px 13px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  color: var(--agt-text-muted);
  border-bottom: 2px solid transparent;
  margin-bottom: -0.5px;
}
.agt-tab.active {
  color: var(--agt-text);
  border-bottom-color: var(--agt-text);
}
.agt-tab-panel {
  max-height: 280px;
  overflow-y: auto;
}
.agt-result-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 9px 0;
  border-bottom: 0.5px solid var(--agt-border);
}
.agt-result-item:last-child {
  border-bottom: none;
}
.agt-checkbox {
  width: 14px;
  height: 14px;
  border: 0.5px solid var(--agt-border-strong);
  border-radius: 3px;
  flex-shrink: 0;
  margin-top: 2px;
  background: var(--agt-surface);
  position: relative;
  cursor: pointer;
}
.agt-checkbox.checked {
  background: var(--agt-text);
  border-color: var(--agt-text);
}
.agt-checkbox.checked::after {
  content: "";
  position: absolute;
  left: 3px;
  top: 1px;
  width: 5px;
  height: 8px;
  border: 1.5px solid var(--agt-surface);
  border-top: none;
  border-left: none;
  transform: rotate(40deg);
}
.agt-result-title {
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
  margin-bottom: 2px;
}
.agt-result-meta {
  font-size: 10px;
  color: var(--agt-text-muted);
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 3px;
}
.agt-oa-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(29, 158, 117, 0.12);
  color: var(--agt-accent);
  border: 0.5px solid var(--agt-accent);
}
.agt-result-summary {
  font-size: 11px;
  color: var(--agt-text-muted);
  line-height: 1.5;
}
.agt-score-bar {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 4px;
}
.agt-score-bg {
  flex: 1;
  height: 3px;
  border-radius: 2px;
  background: var(--agt-border);
  position: relative;
  overflow: hidden;
}
.agt-score-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--agt-accent);
}
.agt-score-val {
  font-size: 10px;
  color: var(--agt-text-muted);
  width: 28px;
  text-align: right;
}
.agt-select-all-row {
  padding: 5px 0;
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: var(--agt-text-muted);
  justify-content: center;
}
.agt-link-btn {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: inherit;
  text-decoration: underline;
  padding: 0;
}
.agt-action-bar {
  display: flex;
  gap: 6px;
  padding: 10px 0;
  border-top: 0.5px solid var(--agt-border);
}
```

TypeScript — render result list:

```typescript
function renderResults(papers: NormalizedPaper[], selected: Set<string>) {
  const list = doc.getElementById("agt-results-list")!;
  list.innerHTML = "";
  for (const paper of papers) {
    const item = doc.createElement("div");
    item.className = "agt-result-item";

    const cb = doc.createElement("div");
    cb.className = `agt-checkbox ${selected.has(paper.id) ? "checked" : ""}`;
    cb.addEventListener("click", () => {
      if (selected.has(paper.id)) selected.delete(paper.id);
      else selected.add(paper.id);
      cb.className = `agt-checkbox ${selected.has(paper.id) ? "checked" : ""}`;
      updateApproveButton(selected.size);
    });

    const content = doc.createElement("div");
    content.className = "agt-result-content";
    content.innerHTML = `
      <div class="agt-result-title">${escHtml(paper.title)}</div>
      <div class="agt-result-meta">
        <span>${escHtml(paper.authors.slice(0, 3).join(", "))}${paper.authors.length > 3 ? " et al." : ""}</span>
        <span>${paper.year ?? "—"}</span>
        <span>${paper.citationCount?.toLocaleString() ?? "0"} citations</span>
        ${paper.isOpenAccess ? '<span class="agt-oa-badge">OA</span>' : ""}
      </div>
      <div class="agt-result-summary">${escHtml(paper.summary ?? "")}</div>
      <div class="agt-score-bar">
        <div class="agt-score-bg">
          <div class="agt-score-fill" style="width:${Math.round((paper.score ?? 0) * 100)}%"></div>
        </div>
        <span class="agt-score-val">${(paper.score ?? 0).toFixed(2)}</span>
      </div>`;

    item.appendChild(cb);
    item.appendChild(content);
    list.appendChild(item);
  }
}
```

---

### E. State 4 — Done

```html
<div id="agt-state-done" class="agt-state" style="display:none">
  <div id="agt-done-banner" class="agt-done-banner"></div>

  <div class="agt-section-label">Write results</div>
  <div id="agt-write-results"></div>

  <div class="agt-action-bar">
    <button id="agt-btn-new-search" class="agt-btn">+ New search</button>
    <button id="agt-btn-open-collection" class="agt-btn">
      Open collection
    </button>
  </div>
</div>
```

```css
.agt-done-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px;
  background: rgba(29, 158, 117, 0.12);
  border-radius: var(--agt-radius);
  border: 0.5px solid var(--agt-accent);
}
.agt-write-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 0.5px solid var(--agt-border);
  font-size: 11px;
}
.agt-write-item:last-child {
  border-bottom: none;
}
.agt-status-icon {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
}
.agt-status-icon.created {
  background: rgba(29, 158, 117, 0.15);
  color: var(--agt-accent);
}
.agt-status-icon.unchanged {
  background: var(--agt-amber-dim);
  color: var(--agt-amber);
}
.agt-status-icon.failed {
  background: rgba(226, 75, 74, 0.12);
  color: #a32d2d;
}
.agt-write-title {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.agt-write-tag {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  flex-shrink: 0;
}
.agt-write-tag.created {
  background: rgba(29, 158, 117, 0.12);
  color: var(--agt-accent);
}
.agt-write-tag.unchanged {
  background: var(--agt-amber-dim);
  color: var(--agt-amber);
}
.agt-write-tag.failed {
  background: rgba(226, 75, 74, 0.1);
  color: #a32d2d;
}
```

---

### F. Global button and layout styles

```css
.agt-btn {
  padding: 7px 12px;
  border: 0.5px solid var(--agt-border-strong);
  border-radius: var(--agt-radius);
  font-size: 12px;
  font-weight: 500;
  background: var(--agt-surface);
  color: var(--agt-text);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.agt-btn:hover {
  background: var(--agt-surface-raised);
}
.agt-btn:active {
  opacity: 0.8;
}
.agt-btn.agt-btn-primary {
  background: var(--agt-text);
  color: var(--agt-surface);
  border-color: var(--agt-text);
}
.agt-btn.agt-btn-primary:hover {
  opacity: 0.85;
}
.agt-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.agt-state {
  padding: 12px 14px;
}

/* State transitions */
.agt-state {
  display: none;
}
.agt-state.active {
  display: block;
}
```

---

## State machine in TypeScript

```typescript
type AGTState = "idle" | "running" | "review" | "done";

function setState(state: AGTState) {
  for (const s of ["idle", "running", "review", "done"] as AGTState[]) {
    const el = doc.getElementById(`agt-state-${s}`)!;
    el.classList.toggle("active", s === state);
  }
  // Update status pill for running state
  const pill = doc.getElementById("agt-status-pill")!;
  if (state === "running") pill.classList.add("loading");
  else pill.classList.remove("loading");
}
```

---

## Full user flow wiring

```typescript
// In sciagentWindow.ts — onload
doc.getElementById("agt-btn-search")!.addEventListener("click", async () => {
  const query = (
    doc.getElementById("agt-query") as HTMLInputElement
  ).value.trim();
  const collection = (
    doc.getElementById("agt-collection") as HTMLInputElement
  ).value.trim();
  if (!query) return;

  setState("running");

  // Build request from form controls
  const body = {
    query,
    collection_name: collection || "SciAgent Results",
    overrides: {
      year_min: getIntVal("agt-year-min"),
      year_max: getIntVal("agt-year-max"),
      open_access: getSelectVal("agt-oa"),
      citations: getSelectVal("agt-citations"),
      exclude_terms: getInputVal("agt-exclude")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      sources: getEnabledSources(),
    },
  };

  try {
    const { run_id, search_plan } = await startRun(body);
    renderPlanTags(search_plan);
    pollStatus(run_id); // polls /status/{run_id} every 1.5s
  } catch (e) {
    setState("idle");
    showError(String(e));
  }
});

async function pollStatus(runId: string) {
  const result = await waitForResults(runId); // polls until status !== 'running'
  setState("review");
  renderResults(result.papers, new Set(result.papers.map((p) => p.id)));
  updateApproveButton(result.papers.length);
  (doc.getElementById("agt-query-review") as HTMLInputElement).value = (
    doc.getElementById("agt-query") as HTMLInputElement
  ).value;
}

doc.getElementById("agt-btn-approve")!.addEventListener("click", async () => {
  const selected = getSelectedIds();
  const collection = (
    doc.getElementById("agt-collection-review") as HTMLInputElement
  ).value;
  setState("running");
  try {
    const writeResult = await resumeRun(currentRunId, selected, collection);
    renderWriteResults(writeResult);
    setState("done");
  } catch (e) {
    setState("review");
    showError(String(e));
  }
});

doc.getElementById("agt-btn-new-search")!.addEventListener("click", () => {
  setState("idle");
});
```

---

## xhtml shell

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <title>SciAgent</title>
  <link rel="stylesheet" href="sciagent.css" />
</head>
<body id="agt-root">
  <!-- Titlebar always visible -->
  <div id="agt-titlebar">…</div>

  <!-- States — only one active at a time -->
  <div id="agt-state-idle"    class="agt-state active">…</div>
  <div id="agt-state-running" class="agt-state">…</div>
  <div id="agt-state-review"  class="agt-state">…</div>
  <div id="agt-state-done"    class="agt-state">…</div>

  <script src="sciagentWindow.js"></script>
</body>
</html>
```

---

## Window registration in hooks.ts

```typescript
// Register a named window, not a dialog, so it persists
ztoolkit.getGlobal("openDialog")(
  "chrome://sciagent/content/sciagent.xhtml",
  "sciagent-main",
  "chrome,resizable,centerscreen,width=440,height=680",
);
```

In `manifest.json`, add:

```json
"chrome_url_overrides": {},
"web_accessible_resources": ["content/sciagent.xhtml", "content/sciagent.css"]
```

In `addon/chrome.manifest`:

```
content sciagent content/
```

---

## Acceptance criteria for this batch

- [ ] Window opens at 440×680 (resizable), native Zotero chrome
- [ ] State 1: query input, collection field, all 4 filter controls, source chips from `/health`
- [ ] State 2: locked plan tags, per-source chips animating, spinner
- [ ] State 3: scrollable results list with checkboxes, score bars, OA badges, summaries; 3 tabs (Results / Sources / Settings); approve button shows count
- [ ] State 4: per-item write status with created/unchanged/failed badges; summary banner; new-search button resets to state 1
- [ ] Backend status pill reflects live `/health` check on open and refreshes every 30s
- [ ] Source chips disable/enable before search; disabled chips send `source_policy` override to backend
- [ ] Approve button label dynamically reads "Approve N papers → {collection}"
- [ ] All controls work in Zotero 9 light and dark mode
- [ ] `npm run build` passes cleanly; `npm run typecheck` zero errors
