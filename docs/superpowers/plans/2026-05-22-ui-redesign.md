# Sidebar UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current cluttered single-scroll sidebar with a three-zone shell (header / health strip / phase-driven content) and a verbose running state with per-pipeline-step and per-source visibility.

**Architecture:** All four phase views (IdleView, RunningView, ReviewView, DoneView) are currently defined inline in `App.tsx`; this plan extracts each into its own file, replaces or enhances its content, and wires a new `HeaderBar` and `HealthStrip` as permanent zones 1 and 2. The hook (`useSciAgentController`) gains two new fields: `isMinConfigMissing` and `onCancel`. CSS additions land in `section.css`.

**Tech Stack:** TypeScript 5, React 19 (function components + hooks), vitest 3, `renderToStaticMarkup` for tests, existing `agt-*` CSS variable system in `src/ui/section.css`.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/ui/components/HeaderBar.tsx` | Zone 1: title + status pill + ⚙/cancel button |
| Create | `src/ui/components/HeaderBar.test.ts` | Unit tests for HeaderBar |
| Create | `src/ui/components/HealthStrip.tsx` | Zone 2: min-required row + optional extras hint |
| Create | `src/ui/components/HealthStrip.test.ts` | Unit tests for HealthStrip |
| Create | `src/ui/components/AdvancedFilters.tsx` | Collapsible filter panel (author, keywords, etc.) |
| Create | `src/ui/components/AdvancedFilters.test.ts` | Unit tests for AdvancedFilters |
| Create | `src/ui/components/IdleView.tsx` | Zone 3 idle: query form + advanced filters |
| Create | `src/ui/components/PipelineTracker.tsx` | Running: ordered phase list with icons |
| Create | `src/ui/components/PipelineTracker.test.ts` | Unit tests for PipelineTracker |
| Create | `src/ui/components/RunningView.tsx` | Zone 3 running: query echo + tracker |
| Create | `src/ui/components/PaperCard.tsx` | Single paper row for the review list |
| Create | `src/ui/components/PaperCard.test.ts` | Unit tests for PaperCard |
| Create | `src/ui/components/ReviewView.tsx` | Zone 3 review: summary bar + paper list + actions |
| Create | `src/ui/components/DoneView.tsx` | Zone 3 done: confirmation card |
| Modify | `src/ui/hooks/useSciAgentController.ts` | Add `isMinConfigMissing`, `onCancel` |
| Modify | `src/ui/App.tsx` | Wire 3-zone shell; import new view components |
| Modify | `src/ui/section.css` | Add `.agt-health-strip`, `.agt-advanced-filters`, `.agt-pipeline-*`, `.agt-paper-card` classes |

## Task Status

| # | Task | Status | Key deliverable |
|---|---|---|---|
| 1 | Expose `isMinConfigMissing` and `onCancel` from hook | ⬜ pending | `useSciAgentController` + `backendClient.cancelRun` |
| 2 | `HeaderBar` component | ⬜ pending | Zone 1 header with status pill and ⚙/cancel button |
| 3 | `HealthStrip` component | ⬜ pending | Zone 2 min-required row + optional extras hint |
| 4 | `AdvancedFilters` component | ⬜ pending | Collapsible panel with 6 filter fields |
| 5 | `IdleView` extracted | ⬜ pending | Query form + year dropdown + advanced filters + toolbar |
| 6 | `PipelineTracker` component | ⬜ pending | Five-stage pipeline with per-stage status icons |
| 7 | `RunningView` extracted | ⬜ pending | Verbose running view with query echo + tracker + sources |
| 8 | `PaperCard` component | ⬜ pending | Paper row: title, stars, badges, abstract snippet |
| 9 | `ReviewView` extracted | ⬜ pending | Review list with collection picker + action bar |
| 10 | `DoneView` extracted | ⬜ pending | Confirmation screen with added/skipped counts |
| 11 | Wire 3-zone shell in `App.tsx` | ⬜ pending | Full integration + all quality gates green |

Update status as you go: ⬜ pending → 🔄 in progress → ✅ done → ❌ blocked.

---

## Task 1: Expose `isMinConfigMissing` and `onCancel` from the hook

**Files:**
- Modify: `zotero-addon/src/ui/hooks/useSciAgentController.ts`

### Background — hook changes

The hook's `return` block starts at line 543. `config` is already in scope. `cancelRun` needs to call `DELETE /run/{runId}` via the backend client — check `backendClient.ts` for the method name (look for `cancel` or `DELETE /run`). If no cancel method exists, call `services.createClient(config).cancelRun(runId)` and add that method in Task 1 step 2.

**Minimum config missing** means: `config.backendUrl` is empty **or** `config.zoteroApiKey` is empty **or** all four LLM keys are empty (`openaiApiKey`, `anthropicApiKey`, `xaiApiKey`, `groqApiKey`).

- [ ] **Step 1: Add `isMinConfigMissing` to the return block**

In `useSciAgentController.ts`, in the `return { ... }` block (around line 543), add:

```typescript
isMinConfigMissing:
  config.backendUrl.trim().length === 0 ||
  config.zoteroApiKey.trim().length === 0 ||
  (config.openaiApiKey.trim().length === 0 &&
    config.anthropicApiKey.trim().length === 0 &&
    config.xaiApiKey.trim().length === 0 &&
    config.groqApiKey.trim().length === 0),
```

- [ ] **Step 2: Add `cancelRun` internal function and `onCancel` export**

Check `zotero-addon/src/client/backendClient.ts` for a cancel method. If it exists (e.g., `cancelRun(runId: string)`), use it. If not, add this method to `backendClient.ts`:

```typescript
async cancelRun(runId: string): Promise<void> {
  await this.request("DELETE", `/run/${runId}`);
}
```

Then in `useSciAgentController.ts`, add inside the function body (before the `return`):

```typescript
const cancelRun = useEffectEvent(async () => {
  const runId = runView.snapshot?.run_id;
  if (runId == null) return;
  try {
    await services.createClient(config).cancelRun(runId);
  } catch {
    // non-fatal: backend may already be done
  }
  setRunView({ error: null, phase: "idle", snapshot: null });
});
```

And add to the `return` block:

```typescript
onCancel: () => void cancelRun(),
```

- [ ] **Step 3: Run typecheck to confirm no errors**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add zotero-addon/src/ui/hooks/useSciAgentController.ts zotero-addon/src/client/backendClient.ts
git commit -m "feat(ui): expose isMinConfigMissing and onCancel from hook"
```

---

## Task 2: `HeaderBar` component

**Files:**
- Create: `zotero-addon/src/ui/components/HeaderBar.tsx`
- Create: `zotero-addon/src/ui/components/HeaderBar.test.ts`

### Background — Zone 1 header

Replaces the current `<header>` in `App.tsx` (the titlebar with StatusPill). Zone 1 is always visible. The ⚙ button becomes red when `isMinConfigMissing`. During `submitting`, `running`, or `resuming` phases, the ⚙ button is replaced by a `✕ Cancel` button.

The status pill label mapping:
- `idle`, `completed` → `"idle"` (green)
- `submitting`, `running`, `resuming` → `"running"` (amber/yellow)  
- `awaiting_approval` → `"awaiting approval"` (purple, use `--agt-amber` as placeholder — no purple variable exists yet, add `--agt-purple: #c084fc` to `:root` in `section.css`)
- `rejected`, `failed`, `error` → `"error"` (red)

- [ ] **Step 1: Write the failing test**

Create `zotero-addon/src/ui/components/HeaderBar.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { HeaderBar } from "./HeaderBar";
import type { RunPhase } from "../hooks/useSciAgentController";

function render(props: {
  phase: RunPhase;
  isMinConfigMissing: boolean;
  onOpenSettings: () => void;
  onCancel: () => void;
}): string {
  return renderToStaticMarkup(createElement(HeaderBar, props));
}

describe("HeaderBar status pill", () => {
  it("shows 'idle' label when phase is idle", () => {
    const html = render({ phase: "idle", isMinConfigMissing: false, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("idle");
  });

  it("shows 'running' label when phase is running", () => {
    const html = render({ phase: "running", isMinConfigMissing: false, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("running");
  });

  it("shows 'awaiting approval' label when phase is awaiting_approval", () => {
    const html = render({ phase: "awaiting_approval", isMinConfigMissing: false, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("awaiting approval");
  });

  it("shows 'error' label when phase is error", () => {
    const html = render({ phase: "error", isMinConfigMissing: false, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("error");
  });
});

describe("HeaderBar settings button", () => {
  it("renders settings button when phase is idle", () => {
    const html = render({ phase: "idle", isMinConfigMissing: false, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("agt-header-settings");
    expect(html).not.toContain("agt-header-cancel");
  });

  it("adds danger modifier when isMinConfigMissing is true", () => {
    const html = render({ phase: "idle", isMinConfigMissing: true, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("agt-header-settings--danger");
  });

  it("renders cancel button instead of settings when phase is running", () => {
    const html = render({ phase: "running", isMinConfigMissing: false, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("agt-header-cancel");
    expect(html).not.toContain("agt-header-settings");
  });

  it("renders cancel button when phase is submitting", () => {
    const html = render({ phase: "submitting", isMinConfigMissing: false, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("agt-header-cancel");
  });

  it("renders cancel button when phase is resuming", () => {
    const html = render({ phase: "resuming", isMinConfigMissing: false, onOpenSettings: vi.fn(), onCancel: vi.fn() });
    expect(html).toContain("agt-header-cancel");
  });
});
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd zotero-addon && npm run test -- HeaderBar
```

Expected: FAIL — `HeaderBar` not found.

- [ ] **Step 3: Implement `HeaderBar`**

Create `zotero-addon/src/ui/components/HeaderBar.tsx`:

```typescript
import { createElement } from "react";
import type { RunPhase } from "../hooks/useSciAgentController";

const ACTIVE_PHASES: ReadonlySet<RunPhase> = new Set(["submitting", "running", "resuming"]);

function pillLabel(phase: RunPhase): string {
  if (ACTIVE_PHASES.has(phase)) return "running";
  if (phase === "awaiting_approval") return "awaiting approval";
  if (phase === "rejected" || phase === "failed" || phase === "error") return "error";
  return "idle";
}

function pillClass(phase: RunPhase): string {
  if (ACTIVE_PHASES.has(phase)) return "agt-status-pill--loading";
  if (phase === "awaiting_approval") return "agt-status-pill--purple";
  if (phase === "rejected" || phase === "failed" || phase === "error") return "agt-status-pill--error";
  return "agt-status-pill--ok";
}

export interface HeaderBarProps {
  phase: RunPhase;
  isMinConfigMissing: boolean;
  onOpenSettings: () => void;
  onCancel: () => void;
}

export function HeaderBar({ phase, isMinConfigMissing, onOpenSettings, onCancel }: HeaderBarProps) {
  const isActive = ACTIVE_PHASES.has(phase);
  return createElement(
    "header",
    { className: "agt-titlebar" },
    createElement(
      "div",
      { className: "agt-titlebar-left" },
      createElement("span", { className: "agt-app-name" }, "SciAgent"),
      createElement(
        "output",
        { className: `agt-status-pill ${pillClass(phase)}`, "aria-live": "polite" },
        createElement("span", { className: "agt-status-dot", "aria-hidden": "true" }),
        pillLabel(phase),
      ),
    ),
    isActive
      ? createElement(
          "button",
          { className: "agt-header-cancel", onClick: onCancel, type: "button", "aria-label": "Cancel search" },
          "✕ Cancel",
        )
      : createElement(
          "button",
          {
            className: `agt-header-settings${isMinConfigMissing ? " agt-header-settings--danger" : ""}`,
            onClick: onOpenSettings,
            type: "button",
            "aria-label": "Open settings",
          },
          "⚙",
        ),
  );
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd zotero-addon && npm run test -- HeaderBar
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Add CSS for new classes**

In `zotero-addon/src/ui/section.css`, find the `/* ── Titlebar ──` section and add after the existing titlebar rules:

```css
.agt-titlebar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agt-app-name {
  font-weight: 700;
  font-size: 0.85rem;
}

.agt-status-pill--purple {
  background: rgba(192, 132, 252, 0.15);
  color: #c084fc;
  border-color: rgba(192, 132, 252, 0.4);
}

.agt-header-settings {
  background: none;
  border: 1px solid var(--agt-border-strong);
  border-radius: var(--agt-radius-sm);
  color: var(--agt-text-muted);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 6px;
}

.agt-header-settings--danger {
  border-color: var(--agt-danger);
  color: var(--agt-danger);
}

.agt-header-cancel {
  background: none;
  border: 1px solid var(--agt-border-strong);
  border-radius: var(--agt-radius-sm);
  color: var(--agt-text-muted);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 8px;
}
```

- [ ] **Step 6: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors.

- [ ] **Step 7: Commit**

```bash
git add zotero-addon/src/ui/components/HeaderBar.tsx zotero-addon/src/ui/components/HeaderBar.test.ts zotero-addon/src/ui/section.css
git commit -m "feat(ui): add HeaderBar component (zone 1)"
```

---

## Task 3: `HealthStrip` component

**Files:**
- Create: `zotero-addon/src/ui/components/HealthStrip.tsx`
- Create: `zotero-addon/src/ui/components/HealthStrip.test.ts`

### Background — Zone 2 health data

Zone 2: always-visible two-row strip. Row 1 shows Backend · Zotero · LLM with a coloured tick/cross. Row 2 shows nudges for optional unconfigured keys (S2, CORE) — hidden when all optional keys are set.

`HealthResponse` shape (from `contracts.ts`): `{ ok: boolean; message: string; preflight: { ok: boolean; message: string | null } }`. Backend is healthy when `healthResponse?.ok === true`. Zotero is OK when `healthResponse?.preflight.ok === true`.

LLM is considered configured if any LLM key is non-empty in `config`.

Optional extras (show hint when key is empty):
- `config.apiKey` → S2 key (SciAgent API key) — "S2 key → faster results"

Note: CORE requires a dedicated key not currently in `AddonConfig`. Only show the S2 nudge for now; add CORE when the field exists.

- [ ] **Step 1: Write the failing test**

Create `zotero-addon/src/ui/components/HealthStrip.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { HealthStrip } from "./HealthStrip";
import type { AddonConfig } from "../../host/prefs";
import type { HealthResponse } from "../../shared/contracts";
import { DEFAULT_ADDON_CONFIG } from "../../host/prefs";

function makeHealth(ok: boolean, preflightOk = true): HealthResponse {
  return {
    ok,
    message: ok ? "ok" : "unreachable",
    preflight: { ok: preflightOk, message: preflightOk ? null : "preflight failed" },
  } as HealthResponse;
}

function render(
  healthResponse: HealthResponse | null,
  config: Partial<AddonConfig> = {},
): string {
  return renderToStaticMarkup(
    createElement(HealthStrip, {
      healthResponse,
      healthBusy: false,
      config: { ...DEFAULT_ADDON_CONFIG, ...config },
    }),
  );
}

describe("HealthStrip min-required row", () => {
  it("shows green Backend tick when health is ok", () => {
    const html = render(makeHealth(true));
    expect(html).toContain("agt-health-ok");
    expect(html).toContain("Backend");
  });

  it("shows red Backend cross when health is not ok", () => {
    const html = render(makeHealth(false));
    expect(html).toContain("agt-health-error");
    expect(html).toContain("Backend");
  });

  it("shows pending Backend when healthResponse is null and not busy", () => {
    const html = render(null);
    expect(html).toContain("agt-health-pending");
  });

  it("shows green Zotero tick when preflight is ok", () => {
    const html = render(makeHealth(true, true));
    expect(html).toContain("Zotero");
  });

  it("shows green LLM tick when any LLM key is set", () => {
    const html = render(makeHealth(true), { openaiApiKey: "sk-test" });
    expect(html).toContain("LLM");
    expect(html).toContain("agt-health-ok");
  });

  it("shows red LLM cross when all LLM keys are empty", () => {
    const html = render(makeHealth(true), {
      openaiApiKey: "",
      anthropicApiKey: "",
      xaiApiKey: "",
      groqApiKey: "",
    });
    expect(html).toContain("agt-health-error");
  });
});

describe("HealthStrip optional extras hint", () => {
  it("shows S2 nudge when apiKey is empty", () => {
    const html = render(makeHealth(true), { apiKey: "" });
    expect(html).toContain("S2 key");
    expect(html).toContain("agt-health-extras");
  });

  it("hides extras row when apiKey is set", () => {
    const html = render(makeHealth(true), { apiKey: "my-api-key" });
    expect(html).not.toContain("agt-health-extras");
  });
});
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd zotero-addon && npm run test -- HealthStrip
```

Expected: FAIL — `HealthStrip` not found.

- [ ] **Step 3: Implement `HealthStrip`**

Create `zotero-addon/src/ui/components/HealthStrip.tsx`:

```typescript
import { createElement } from "react";
import type { AddonConfig } from "../../host/prefs";
import type { HealthResponse } from "../../shared/contracts";

function hasAnyLlmKey(config: AddonConfig): boolean {
  return (
    config.openaiApiKey.trim().length > 0 ||
    config.anthropicApiKey.trim().length > 0 ||
    config.xaiApiKey.trim().length > 0 ||
    config.groqApiKey.trim().length > 0
  );
}

type IndicatorState = "ok" | "error" | "pending";

function indicatorClass(state: IndicatorState): string {
  if (state === "ok") return "agt-health-ok";
  if (state === "error") return "agt-health-error";
  return "agt-health-pending";
}

function indicatorSymbol(state: IndicatorState): string {
  if (state === "ok") return "✓";
  if (state === "error") return "✕";
  return "○";
}

function Indicator({ label, state }: { label: string; state: IndicatorState }) {
  return createElement(
    "span",
    { className: `agt-health-indicator ${indicatorClass(state)}` },
    indicatorSymbol(state),
    " ",
    label,
  );
}

export interface HealthStripProps {
  healthResponse: HealthResponse | null;
  healthBusy: boolean;
  config: AddonConfig;
}

export function HealthStrip({ healthResponse, healthBusy, config }: HealthStripProps) {
  const backendState: IndicatorState =
    healthBusy ? "pending" : healthResponse?.ok === true ? "ok" : healthResponse !== null ? "error" : "pending";
  const zoteroState: IndicatorState =
    healthBusy ? "pending" : healthResponse?.preflight.ok === true ? "ok" : healthResponse !== null ? "error" : "pending";
  const llmState: IndicatorState = hasAnyLlmKey(config) ? "ok" : "error";

  const showExtras = config.apiKey.trim().length === 0;

  return createElement(
    "div",
    { className: "agt-health-strip" },
    createElement(
      "div",
      { className: "agt-health-row" },
      createElement(Indicator, { label: "Backend", state: backendState }),
      createElement("span", { className: "agt-health-sep" }, "·"),
      createElement(Indicator, { label: "Zotero", state: zoteroState }),
      createElement("span", { className: "agt-health-sep" }, "·"),
      createElement(Indicator, { label: "LLM", state: llmState }),
    ),
    showExtras
      ? createElement(
          "div",
          { className: "agt-health-extras" },
          "+ S2 key → faster results",
        )
      : null,
  );
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd zotero-addon && npm run test -- HealthStrip
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Add CSS**

In `section.css`, after the titlebar section, add:

```css
/* ── Health Strip (Zone 2) ───────────────────────────────── */
.agt-health-strip {
  border-bottom: 0.5px solid var(--agt-border);
  flex-shrink: 0;
  padding: 5px 14px;
}

.agt-health-row {
  align-items: center;
  display: flex;
  gap: 6px;
}

.agt-health-indicator {
  font-size: 0.72rem;
}

.agt-health-ok    { color: var(--agt-green); }
.agt-health-error { color: var(--agt-danger); }
.agt-health-pending { color: var(--agt-text-muted); }

.agt-health-sep {
  color: var(--agt-border-strong);
  font-size: 0.72rem;
}

.agt-health-extras {
  color: var(--agt-text-muted);
  font-size: 0.68rem;
  margin-top: 2px;
}
```

- [ ] **Step 6: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors.

- [ ] **Step 7: Commit**

```bash
git add zotero-addon/src/ui/components/HealthStrip.tsx zotero-addon/src/ui/components/HealthStrip.test.ts zotero-addon/src/ui/section.css
git commit -m "feat(ui): add HealthStrip component (zone 2)"
```

---

## Task 4: `AdvancedFilters` component

**Files:**
- Create: `zotero-addon/src/ui/components/AdvancedFilters.tsx`
- Create: `zotero-addon/src/ui/components/AdvancedFilters.test.ts`

### Background — FilterEditContract shape

Collapsible panel under the idle form. Fields map to `FilterEditContract`:
- Author → `authors[0]` (single string for the UI, stored as first element)
- Must include keywords → `include_keywords` (comma-separated string ↔ string[])
- Exclude keywords → `exclude_keywords` (same)
- Min citations → `min_citations` (number)
- Open access only → `open_access_only` (boolean)
- Venue → `venues[0]` (single string for the UI)

`FilterEditContract` interface (from `src/shared/contracts.ts`):

```typescript
interface FilterEditContract {
  original_query: string;
  source_policy: SourceCapability[];
  result_limit: number;
  min_citations: number;
  open_access_only: boolean;
  include_keywords: string[];
  exclude_keywords: string[];
  authors: string[];
  venues: string[];
  seed_dois: string[];
  // ... other fields
}
```

- [ ] **Step 1: Write the failing test**

Create `zotero-addon/src/ui/components/AdvancedFilters.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AdvancedFilters } from "./AdvancedFilters";
import type { FilterEditContract } from "../../shared/contracts";
import { buildDefaultFilterEdit } from "../../shared/contracts";

function makeFilter(overrides: Partial<FilterEditContract> = {}): FilterEditContract {
  return { ...buildDefaultFilterEdit("test query", null, 0, false), ...overrides };
}

function render(props: {
  filter: FilterEditContract;
  isOpen: boolean;
  onToggle: () => void;
  onChange: (update: Partial<FilterEditContract>) => void;
}): string {
  return renderToStaticMarkup(createElement(AdvancedFilters, props));
}

describe("AdvancedFilters", () => {
  it("renders collapsed toggle when isOpen is false", () => {
    const html = render({ filter: makeFilter(), isOpen: false, onToggle: vi.fn(), onChange: vi.fn() });
    expect(html).toContain("agt-advanced-toggle");
    expect(html).not.toContain("agt-advanced-panel");
  });

  it("renders expanded panel when isOpen is true", () => {
    const html = render({ filter: makeFilter(), isOpen: true, onToggle: vi.fn(), onChange: vi.fn() });
    expect(html).toContain("agt-advanced-panel");
  });

  it("shows author field when expanded", () => {
    const html = render({ filter: makeFilter({ authors: ["LeCun"] }), isOpen: true, onToggle: vi.fn(), onChange: vi.fn() });
    expect(html).toContain("LeCun");
  });

  it("shows include_keywords as comma-separated string", () => {
    const html = render({
      filter: makeFilter({ include_keywords: ["attention", "graph"] }),
      isOpen: true,
      onToggle: vi.fn(),
      onChange: vi.fn(),
    });
    expect(html).toContain("attention, graph");
  });

  it("shows exclude_keywords as comma-separated string", () => {
    const html = render({
      filter: makeFilter({ exclude_keywords: ["survey"] }),
      isOpen: true,
      onToggle: vi.fn(),
      onChange: vi.fn(),
    });
    expect(html).toContain("survey");
  });

  it("shows min_citations value", () => {
    const html = render({ filter: makeFilter({ min_citations: 50 }), isOpen: true, onToggle: vi.fn(), onChange: vi.fn() });
    expect(html).toContain("50");
  });

  it("shows venue", () => {
    const html = render({ filter: makeFilter({ venues: ["NeurIPS"] }), isOpen: true, onToggle: vi.fn(), onChange: vi.fn() });
    expect(html).toContain("NeurIPS");
  });

  it("shows open_access_only checkbox as checked", () => {
    const html = render({ filter: makeFilter({ open_access_only: true }), isOpen: true, onToggle: vi.fn(), onChange: vi.fn() });
    expect(html).toContain('checked=""');
  });
});
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd zotero-addon && npm run test -- AdvancedFilters
```

Expected: FAIL.

- [ ] **Step 3: Implement `AdvancedFilters`**

Create `zotero-addon/src/ui/components/AdvancedFilters.tsx`:

```typescript
import { createElement } from "react";
import type { FilterEditContract } from "../../shared/contracts";

export interface AdvancedFiltersProps {
  filter: FilterEditContract;
  isOpen: boolean;
  onToggle: () => void;
  onChange: (update: Partial<FilterEditContract>) => void;
}

function splitKeywords(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

export function AdvancedFilters({ filter, isOpen, onToggle, onChange }: AdvancedFiltersProps) {
  return createElement(
    "div",
    { className: "agt-advanced-filters" },
    createElement(
      "button",
      { className: "agt-advanced-toggle", type: "button", onClick: onToggle },
      isOpen ? "▾ Advanced filters" : "▸ Advanced filters (author, keywords, citations…)",
    ),
    isOpen
      ? createElement(
          "div",
          { className: "agt-advanced-panel" },
          createElement(
            "label",
            { className: "agt-field" },
            createElement("span", { className: "agt-field-label" }, "Author"),
            createElement("input", {
              className: "agt-input",
              type: "text",
              value: filter.authors[0] ?? "",
              placeholder: "e.g. LeCun",
              onChange: (e: { target: { value: string } }) =>
                onChange({ authors: e.target.value.trim() ? [e.target.value] : [] }),
            }),
          ),
          createElement(
            "label",
            { className: "agt-field" },
            createElement("span", { className: "agt-field-label" }, "Must include keywords"),
            createElement("input", {
              className: "agt-input",
              type: "text",
              value: filter.include_keywords.join(", "),
              placeholder: "attention, transformer",
              onChange: (e: { target: { value: string } }) =>
                onChange({ include_keywords: splitKeywords(e.target.value) }),
            }),
          ),
          createElement(
            "label",
            { className: "agt-field" },
            createElement("span", { className: "agt-field-label" }, "Exclude keywords"),
            createElement("input", {
              className: "agt-input",
              type: "text",
              value: filter.exclude_keywords.join(", "),
              placeholder: "survey, review",
              onChange: (e: { target: { value: string } }) =>
                onChange({ exclude_keywords: splitKeywords(e.target.value) }),
            }),
          ),
          createElement(
            "div",
            { className: "agt-field-row" },
            createElement(
              "label",
              { className: "agt-field agt-field--half" },
              createElement("span", { className: "agt-field-label" }, "Min citations"),
              createElement("input", {
                className: "agt-input",
                type: "number",
                min: "0",
                value: filter.min_citations,
                onChange: (e: { target: { value: string } }) =>
                  onChange({ min_citations: Math.max(0, parseInt(e.target.value, 10) || 0) }),
              }),
            ),
            createElement(
              "label",
              { className: "agt-field agt-field--half agt-field--checkbox" },
              createElement("input", {
                type: "checkbox",
                checked: filter.open_access_only,
                onChange: (e: { target: { checked: boolean } }) =>
                  onChange({ open_access_only: e.target.checked }),
              }),
              " Open access only",
            ),
          ),
          createElement(
            "label",
            { className: "agt-field" },
            createElement("span", { className: "agt-field-label" }, "Venue / journal"),
            createElement("input", {
              className: "agt-input",
              type: "text",
              value: filter.venues[0] ?? "",
              placeholder: "NeurIPS, Nature…",
              onChange: (e: { target: { value: string } }) =>
                onChange({ venues: e.target.value.trim() ? [e.target.value] : [] }),
            }),
          ),
        )
      : null,
  );
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd zotero-addon && npm run test -- AdvancedFilters
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Add CSS**

In `section.css`, add:

```css
/* ── Advanced Filters ───────────────────────────────────────── */
.agt-advanced-filters {
  margin-top: 6px;
}

.agt-advanced-toggle {
  background: none;
  border: none;
  color: var(--agt-accent);
  cursor: pointer;
  font-size: 0.78rem;
  padding: 0;
}

.agt-advanced-panel {
  background: var(--agt-surface-raised);
  border: 0.5px solid var(--agt-border);
  border-radius: var(--agt-radius-sm);
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
  padding: 8px 10px;
}

.agt-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agt-field-label {
  color: var(--agt-text-muted);
  font-size: 0.68rem;
}

.agt-field-row {
  display: flex;
  gap: 8px;
}

.agt-field--half { flex: 1; }

.agt-field--checkbox {
  flex-direction: row;
  align-items: center;
  font-size: 0.78rem;
  padding-top: 14px;
}
```

- [ ] **Step 6: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors.

- [ ] **Step 7: Commit**

```bash
git add zotero-addon/src/ui/components/AdvancedFilters.tsx zotero-addon/src/ui/components/AdvancedFilters.test.ts zotero-addon/src/ui/section.css
git commit -m "feat(ui): add AdvancedFilters collapsible panel"
```

---

## Task 5: `IdleView` extracted component

**Files:**
- Create: `zotero-addon/src/ui/components/IdleView.tsx`

### Background — existing IdleView logic

Replaces the `IdleView` function currently defined inline in `App.tsx`. The controller already exposes: `query`, `onQueryChange`, `collectionName`, `onCollectionChange`, `filterDraft`, `onFilterDraftChange`, `onSubmitSearch`, `canSubmitSearch`, `onExtractKeywords`, `onAcceptCorrection`.

The `onAcceptCorrection` callback accepts the corrected query string and applies it. The existing `IdleView` in `App.tsx` already renders spell-check suggestions — look at lines after `function IdleView` in `App.tsx` before extracting to understand what logic to preserve.

Year dropdown options: `null` (Any) / `2024` / `2022` / `2020`. Map to `filterDraft.min_year` on `onFilterDraftChange`. If `filterDraft` is null, initialise with `buildDefaultFilterEdit(query, null, 0, false)` from `contracts.ts`.

- [ ] **Step 1: Read current IdleView in App.tsx**

Read `zotero-addon/src/ui/App.tsx` and find the `function IdleView(` definition. Note every prop access and JSX element used. You will port all of them to the new file.

- [ ] **Step 2: Create `IdleView.tsx`**

Create `zotero-addon/src/ui/components/IdleView.tsx` with this structure (fill in the internal JSX from your reading of the original):

```typescript
import { createElement, useState } from "react";
import { buildDefaultFilterEdit } from "../../shared/contracts";
import type { FilterEditContract } from "../../shared/contracts";
import { AdvancedFilters } from "./AdvancedFilters";
import type { SciAgentController } from "../App";

const YEAR_OPTIONS: Array<{ label: string; value: number | null }> = [
  { label: "Any year", value: null },
  { label: "≥ 2024", value: 2024 },
  { label: "≥ 2022", value: 2022 },
  { label: "≥ 2020", value: 2020 },
];

export function IdleView({ controller }: { controller: SciAgentController }) {
  const [filtersOpen, setFiltersOpen] = useState(false);

  const filter: FilterEditContract =
    controller.filterDraft ??
    buildDefaultFilterEdit(controller.query, null, 0, false);

  // ... port all JSX from the existing inline IdleView
  // Additions vs existing:
  // 1. Year dropdown: onChange calls controller.onFilterDraftChange({ min_year: value })
  // 2. Below the year dropdown, render <AdvancedFilters filter={filter} isOpen={filtersOpen}
  //      onToggle={() => setFiltersOpen(!filtersOpen)}
  //      onChange={(u) => controller.onFilterDraftChange(u)} />
  // 3. Spell-check icon button (ABC✓) beside Search: onClick={() => controller.onExtractKeywords()}
  //    Note: onExtractKeywords extracts from current Zotero item. The ⚑ icon does keyword extraction.
  //    The ABC✓ button calls the spell-check: look at controller.spellSuggestion and onAcceptCorrection.
  //    Check what the existing IdleView does with these and preserve the same logic.
}
```

> **Important:** Do not skip the port of existing logic — spell-check suggestion display, `searchDisabledReason`, and the first-run banner must all be preserved. Read the full existing `IdleView` body and copy it over before adding the new elements.

- [ ] **Step 3: Export `SciAgentController` type from App.tsx**

In `App.tsx`, find the line `type SciAgentController = ReturnType<typeof useSciAgentController>;` and add `export` to it:

```typescript
export type SciAgentController = ReturnType<typeof useSciAgentController>;
```

- [ ] **Step 4: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors. Fix any type mismatches before continuing.

- [ ] **Step 5: Commit**

```bash
git add zotero-addon/src/ui/components/IdleView.tsx zotero-addon/src/ui/App.tsx
git commit -m "feat(ui): extract IdleView with advanced filters and year dropdown"
```

---

## Task 6: `PipelineTracker` component

**Files:**
- Create: `zotero-addon/src/ui/components/PipelineTracker.tsx`
- Create: `zotero-addon/src/ui/components/PipelineTracker.test.ts`

### Background — pipeline stages

Shows the five pipeline stages with a status icon per stage. During `running` phase, only the "Fetch sources" stage is marked active (the API does not expose intermediate stage progress). The stage that's active is determined by passing a `activeStage` prop.

Stages (in order): `spell_check` | `rewrite` | `fetch` | `merge` | `rank`.

- [ ] **Step 1: Write the failing test**

Create `zotero-addon/src/ui/components/PipelineTracker.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PipelineTracker } from "./PipelineTracker";

type Stage = "spell_check" | "rewrite" | "fetch" | "merge" | "rank";

function render(activeStage: Stage, rewrottenQuery: string | null = null): string {
  return renderToStaticMarkup(
    createElement(PipelineTracker, { activeStage, rewrittenQuery: rewrottenQuery }),
  );
}

describe("PipelineTracker", () => {
  it("marks stages before activeStage as completed", () => {
    const html = render("fetch");
    const spellIdx = html.indexOf("agt-stage--done");
    const fetchIdx = html.indexOf("agt-stage--active");
    expect(spellIdx).toBeGreaterThan(-1);
    expect(fetchIdx).toBeGreaterThan(spellIdx);
  });

  it("marks activeStage as active", () => {
    const html = render("rewrite");
    expect(html).toContain("agt-stage--active");
  });

  it("marks stages after activeStage as pending", () => {
    const html = render("spell_check");
    expect(html).toContain("agt-stage--pending");
  });

  it("shows rewritten query when provided", () => {
    const html = render("fetch", "graph attention node classification");
    expect(html).toContain("graph attention node classification");
  });

  it("does not show rewritten query when null", () => {
    const html = render("fetch", null);
    expect(html).not.toContain("→ rewritten");
  });

  it("renders all five stage labels", () => {
    const html = render("rank");
    expect(html).toContain("Spell-check");
    expect(html).toContain("LLM rewrite");
    expect(html).toContain("Fetch sources");
    expect(html).toContain("Merge");
    expect(html).toContain("Rank");
  });
});
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd zotero-addon && npm run test -- PipelineTracker
```

Expected: FAIL.

- [ ] **Step 3: Implement `PipelineTracker`**

Create `zotero-addon/src/ui/components/PipelineTracker.tsx`:

```typescript
import { createElement } from "react";

export type PipelineStage = "spell_check" | "rewrite" | "fetch" | "merge" | "rank";

const STAGES: Array<{ id: PipelineStage; label: string }> = [
  { id: "spell_check", label: "Spell-check query" },
  { id: "rewrite", label: "LLM rewrite" },
  { id: "fetch", label: "Fetch sources" },
  { id: "merge", label: "Merge & deduplicate" },
  { id: "rank", label: "Rank & rerank" },
];

const STAGE_ORDER: ReadonlyMap<PipelineStage, number> = new Map(
  STAGES.map((s, i) => [s.id, i]),
);

export interface PipelineTrackerProps {
  activeStage: PipelineStage;
  rewrittenQuery: string | null;
}

export function PipelineTracker({ activeStage, rewrittenQuery }: PipelineTrackerProps) {
  const activeIdx = STAGE_ORDER.get(activeStage) ?? 0;

  return createElement(
    "div",
    { className: "agt-pipeline" },
    ...STAGES.map(({ id, label }) => {
      const idx = STAGE_ORDER.get(id) ?? 0;
      const stageClass =
        idx < activeIdx
          ? "agt-stage--done"
          : idx === activeIdx
            ? "agt-stage--active"
            : "agt-stage--pending";
      const icon = idx < activeIdx ? "✓" : idx === activeIdx ? "⟳" : "○";

      return createElement(
        "div",
        { key: id, className: `agt-stage ${stageClass}` },
        createElement("span", { className: "agt-stage-icon" }, icon),
        createElement("span", { className: "agt-stage-label" }, label),
        id === "rewrite" && rewrittenQuery !== null
          ? createElement(
              "span",
              { className: "agt-stage-detail" },
              `→ rewritten: "${rewrittenQuery}"`,
            )
          : null,
      );
    }),
  );
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd zotero-addon && npm run test -- PipelineTracker
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Add CSS**

In `section.css`, add:

```css
/* ── Pipeline Tracker ───────────────────────────────────────── */
.agt-pipeline {
  background: var(--agt-surface-raised);
  border: 0.5px solid var(--agt-border);
  border-radius: var(--agt-radius-sm);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.agt-stage {
  align-items: center;
  border-bottom: 0.5px solid var(--agt-border);
  display: flex;
  font-size: 0.78rem;
  gap: 6px;
  padding: 5px 10px;
}

.agt-stage:last-child { border-bottom: none; }

.agt-stage-icon { width: 14px; text-align: center; }

.agt-stage--done   { color: var(--agt-text-muted); }
.agt-stage--done .agt-stage-icon { color: var(--agt-green); }
.agt-stage--active { background: var(--agt-green-dim); color: var(--agt-text); }
.agt-stage--active .agt-stage-icon { color: var(--agt-amber); }
.agt-stage--pending { color: var(--agt-text-muted); opacity: 0.6; }

.agt-stage-detail {
  color: var(--agt-text-muted);
  font-size: 0.7rem;
  font-style: italic;
  margin-left: auto;
}
```

- [ ] **Step 6: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors.

- [ ] **Step 7: Commit**

```bash
git add zotero-addon/src/ui/components/PipelineTracker.tsx zotero-addon/src/ui/components/PipelineTracker.test.ts zotero-addon/src/ui/section.css
git commit -m "feat(ui): add PipelineTracker component"
```

---

## Task 7: `RunningView` extracted & enhanced

**Files:**
- Create: `zotero-addon/src/ui/components/RunningView.tsx`

### Background — source status from hook

Replaces the inline `RunningView` in `App.tsx`. Shows: query echo (original + rewritten), PipelineTracker, and per-source status from `controller.sourceBuckets`.

`sourceBuckets` type (from `buildSourceBuckets` in `contracts.ts`): `SourceBuckets | null`, where `SourceBuckets` is `Record<string, NormalizedPaper[]>`. Each key is a source name (e.g. `"openalex"`, `"s2"`) and the value is the array of papers from that source.

During running, `sourceBuckets` will be null (no results yet). Show all sources from `controller.searchPlan?.source_policy` as "fetching…". When `sourceBuckets` is non-null (should not happen in running phase but handle gracefully), show counts.

The `activeStage` for PipelineTracker while the phase is `running` is `"fetch"`. While `submitting` it is `"spell_check"`.

The rewritten query is `controller.searchPlan?.original_query ?? null` — if it differs from `controller.query`, it was rewritten by the LLM.

- [ ] **Step 1: Create `RunningView.tsx`**

Create `zotero-addon/src/ui/components/RunningView.tsx`:

```typescript
import { createElement } from "react";
import { PipelineTracker } from "./PipelineTracker";
import type { PipelineStage } from "./PipelineTracker";
import type { SciAgentController } from "../App";

const SOURCE_DISPLAY_NAMES: Record<string, string> = {
  s2: "S2",
  openalex: "OpenAlex",
  arxiv: "arXiv",
  pubmed: "PubMed",
  core: "CORE",
  europepmc: "EPMC",
  crossref: "Crossref",
  base: "BASE",
};

export function RunningView({ controller }: { controller: SciAgentController }) {
  const phase = controller.runView.phase;
  const activeStage: PipelineStage = phase === "submitting" ? "spell_check" : "fetch";

  const originalQuery = controller.query;
  const rewrittenQuery = controller.searchPlan?.original_query ?? null;
  const showRewrite =
    rewrittenQuery !== null && rewrittenQuery.trim() !== originalQuery.trim()
      ? rewrittenQuery
      : null;

  const sources = controller.searchPlan?.source_policy ?? [];

  return createElement(
    "div",
    { className: "agt-running-view" },
    createElement(
      "div",
      { className: "agt-query-echo" },
      createElement("span", { className: "agt-query-echo-label" }, "Searching for"),
      createElement("span", { className: "agt-query-echo-text" }, `"${originalQuery}"`),
      showRewrite !== null
        ? createElement("span", { className: "agt-query-echo-rewrite" }, `→ rewritten: "${showRewrite}"`)
        : null,
    ),
    createElement("p", { className: "agt-section-label" }, "Pipeline"),
    createElement(PipelineTracker, { activeStage, rewrittenQuery: showRewrite }),
    sources.length > 0
      ? createElement(
          "div",
          null,
          createElement("p", { className: "agt-section-label" }, "Sources"),
          createElement(
            "div",
            { className: "agt-source-status-list" },
            ...sources.map((src) => {
              const displayName = SOURCE_DISPLAY_NAMES[src.name] ?? src.name;
              const bucketCount = controller.sourceBuckets?.[src.name]?.length;
              const status =
                bucketCount !== undefined
                  ? `✓ ${bucketCount} papers`
                  : "⟳ fetching…";
              const statusClass =
                bucketCount !== undefined ? "agt-source-status--done" : "agt-source-status--active";
              return createElement(
                "div",
                { key: src.name, className: "agt-source-status-row" },
                createElement("span", { className: "agt-source-status-name" }, displayName),
                createElement("span", { className: `agt-source-status-state ${statusClass}` }, status),
              );
            }),
          ),
        )
      : null,
  );
}
```

- [ ] **Step 2: Add CSS**

In `section.css`, add:

```css
/* ── Running View ───────────────────────────────────────────── */
.agt-running-view {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 14px;
}

.agt-query-echo {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agt-query-echo-label { color: var(--agt-text-muted); font-size: 0.72rem; }
.agt-query-echo-text  { font-style: italic; font-size: 0.82rem; }
.agt-query-echo-rewrite { color: var(--agt-text-muted); font-size: 0.72rem; }

.agt-section-label {
  color: var(--agt-text-muted);
  font-size: 0.68rem;
  letter-spacing: 0.05em;
  margin: 0 0 4px;
  text-transform: uppercase;
}

.agt-source-status-list {
  background: var(--agt-surface-raised);
  border: 0.5px solid var(--agt-border);
  border-radius: var(--agt-radius-sm);
  overflow: hidden;
}

.agt-source-status-row {
  align-items: center;
  border-bottom: 0.5px solid var(--agt-border);
  display: flex;
  font-size: 0.78rem;
  justify-content: space-between;
  padding: 4px 10px;
}

.agt-source-status-row:last-child { border-bottom: none; }

.agt-source-status-name { color: var(--agt-text-muted); }
.agt-source-status--done   { color: var(--agt-green); }
.agt-source-status--active { color: var(--agt-amber); }
.agt-source-status--error  { color: var(--agt-danger); }
```

- [ ] **Step 3: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add zotero-addon/src/ui/components/RunningView.tsx zotero-addon/src/ui/section.css
git commit -m "feat(ui): add verbose RunningView with pipeline tracker and source status"
```

---

## Task 8: `PaperCard` component

**Files:**
- Create: `zotero-addon/src/ui/components/PaperCard.tsx`
- Create: `zotero-addon/src/ui/components/PaperCard.test.ts`

### Background — NormalizedPaper fields

Renders one row in the review list. Replaces the existing inline paper rows in `ResultsList` / review view. A score of ≥ 0.8 → ★★★, ≥ 0.5 → ★★☆, else ★☆☆. Abstract snippet shown for ★★★ and ★★☆ papers (score ≥ 0.5).

`NormalizedPaper` key fields: `title`, `authors` (string[] | NormalizedAuthor[]), `year`, `venue`, `source`, `citation_count`, `open_access`, `abstract`, `score`, `doi`, `url`.

- [ ] **Step 1: Write the failing test**

Create `zotero-addon/src/ui/components/PaperCard.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PaperCard } from "./PaperCard";
import type { NormalizedPaper } from "../../shared/contracts";

function makePaper(overrides: Partial<NormalizedPaper> = {}): NormalizedPaper {
  return {
    title: "Test Paper",
    year: 2024,
    doi: null,
    arxiv_id: null,
    abstract: null,
    authors: [],
    url: null,
    pdf_url: null,
    source: "openalex",
    index: 1,
    semantic_score: 0.5,
    citation_count: 0,
    influential_citation_count: 0,
    open_access: false,
    summary: null,
    score: 0.5,
    explanation: null,
    venue: null,
    item_type: null,
    volume: null,
    issue: null,
    pages: null,
    ...overrides,
  };
}

function render(paper: NormalizedPaper, selected: boolean): string {
  return renderToStaticMarkup(
    createElement(PaperCard, { paper, selected, onToggle: vi.fn() }),
  );
}

describe("PaperCard stars", () => {
  it("shows 3 stars when score >= 0.8", () => {
    const html = render(makePaper({ score: 0.85 }), true);
    expect(html).toContain("★★★");
  });

  it("shows 2 stars when score >= 0.5 and < 0.8", () => {
    const html = render(makePaper({ score: 0.6 }), true);
    expect(html).toContain("★★☆");
  });

  it("shows 1 star when score < 0.5", () => {
    const html = render(makePaper({ score: 0.3 }), true);
    expect(html).toContain("★☆☆");
  });
});

describe("PaperCard abstract", () => {
  it("shows abstract for 3-star paper", () => {
    const html = render(makePaper({ score: 0.9, abstract: "This is the abstract." }), true);
    expect(html).toContain("This is the abstract");
  });

  it("shows abstract for 2-star paper", () => {
    const html = render(makePaper({ score: 0.6, abstract: "Abstract text." }), true);
    expect(html).toContain("Abstract text");
  });

  it("hides abstract for 1-star paper", () => {
    const html = render(makePaper({ score: 0.3, abstract: "Hidden abstract." }), true);
    expect(html).not.toContain("Hidden abstract");
  });
});

describe("PaperCard badges", () => {
  it("shows OA badge when open_access is true", () => {
    const html = render(makePaper({ open_access: true }), true);
    expect(html).toContain("agt-badge--oa");
  });

  it("hides OA badge when open_access is false", () => {
    const html = render(makePaper({ open_access: false }), true);
    expect(html).not.toContain("agt-badge--oa");
  });

  it("shows citation count", () => {
    const html = render(makePaper({ citation_count: 142 }), true);
    expect(html).toContain("142");
  });

  it("shows venue", () => {
    const html = render(makePaper({ venue: "NeurIPS" }), true);
    expect(html).toContain("NeurIPS");
  });

  it("shows source badge", () => {
    const html = render(makePaper({ source: "openalex" }), true);
    expect(html).toContain("agt-badge--source");
  });
});

describe("PaperCard selection", () => {
  it("adds selected modifier when selected is true", () => {
    const html = render(makePaper(), true);
    expect(html).toContain("agt-paper-card--selected");
  });

  it("does not add selected modifier when selected is false", () => {
    const html = render(makePaper(), false);
    expect(html).not.toContain("agt-paper-card--selected");
  });

  it("shows checkbox", () => {
    const html = render(makePaper(), true);
    expect(html).toContain('type="checkbox"');
  });
});
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd zotero-addon && npm run test -- PaperCard
```

Expected: FAIL.

- [ ] **Step 3: Implement `PaperCard`**

Create `zotero-addon/src/ui/components/PaperCard.tsx`:

```typescript
import { createElement } from "react";
import type { NormalizedPaper } from "../../shared/contracts";

const SOURCE_LABELS: Record<string, string> = {
  s2: "S2",
  openalex: "OAlex",
  arxiv: "arXiv",
  pubmed: "PubMed",
  core: "CORE",
  europepmc: "EPMC",
  crossref: "Crossref",
  base: "BASE",
};

function stars(score: number): string {
  if (score >= 0.8) return "★★★";
  if (score >= 0.5) return "★★☆";
  return "★☆☆";
}

function authorString(authors: NormalizedPaper["authors"]): string {
  if (authors.length === 0) return "";
  const first = authors[0];
  const name = typeof first === "string" ? first : first.name;
  return authors.length > 1 ? `${name} et al.` : name;
}

function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max)}…`;
}

export interface PaperCardProps {
  paper: NormalizedPaper;
  selected: boolean;
  onToggle: () => void;
}

export function PaperCard({ paper, selected, onToggle }: PaperCardProps) {
  const score = paper.score ?? paper.semantic_score ?? 0;
  const showAbstract = score >= 0.5 && paper.abstract !== null;
  const href = paper.doi ? `https://doi.org/${paper.doi}` : (paper.url ?? undefined);

  return createElement(
    "div",
    {
      className: `agt-paper-card${selected ? " agt-paper-card--selected" : ""}`,
      onClick: onToggle,
    },
    createElement("input", {
      type: "checkbox",
      checked: selected,
      onChange: onToggle,
      onClick: (e: { stopPropagation: () => void }) => e.stopPropagation(),
      className: "agt-paper-card-checkbox",
    }),
    createElement(
      "div",
      { className: "agt-paper-card-body" },
      createElement(
        "div",
        { className: "agt-paper-card-title" },
        href
          ? createElement("a", { href, target: "_blank", rel: "noreferrer" }, paper.title)
          : paper.title,
      ),
      createElement(
        "div",
        { className: "agt-paper-card-meta" },
        [authorString(paper.authors), paper.year, paper.venue].filter(Boolean).join(" · "),
      ),
      createElement(
        "div",
        { className: "agt-paper-card-badges" },
        createElement("span", { className: "agt-paper-card-stars" }, stars(score)),
        createElement("span", { className: "agt-badge agt-badge--source" }, SOURCE_LABELS[paper.source] ?? paper.source),
        paper.citation_count > 0
          ? createElement("span", { className: "agt-paper-card-citations" }, `${paper.citation_count.toLocaleString()} cit.`)
          : null,
        paper.open_access
          ? createElement("span", { className: "agt-badge agt-badge--oa" }, "OA")
          : null,
      ),
      showAbstract
        ? createElement("div", { className: "agt-paper-card-abstract" }, truncate(paper.abstract!, 160))
        : null,
    ),
  );
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd zotero-addon && npm run test -- PaperCard
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Add CSS**

In `section.css`, add:

```css
/* ── Paper Card ─────────────────────────────────────────────── */
.agt-paper-card {
  border: 0.5px solid var(--agt-border);
  border-radius: var(--agt-radius-sm);
  cursor: pointer;
  display: flex;
  gap: 8px;
  margin-bottom: 5px;
  opacity: 0.65;
  padding: 7px 10px;
}

.agt-paper-card--selected {
  background: var(--agt-green-dim);
  border-color: var(--agt-green);
  opacity: 1;
}

.agt-paper-card-checkbox {
  flex-shrink: 0;
  margin-top: 2px;
}

.agt-paper-card-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.agt-paper-card-title {
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.3;
}

.agt-paper-card-title a {
  color: inherit;
  text-decoration: none;
}

.agt-paper-card-title a:hover { text-decoration: underline; }

.agt-paper-card-meta {
  color: var(--agt-text-muted);
  font-size: 0.72rem;
}

.agt-paper-card-badges {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.agt-paper-card-stars { font-size: 0.75rem; }
.agt-paper-card-citations { color: var(--agt-text-muted); font-size: 0.7rem; }

.agt-badge {
  border-radius: 3px;
  font-size: 0.65rem;
  padding: 1px 5px;
}

.agt-badge--source {
  background: var(--agt-accent-dim);
  color: var(--agt-accent);
}

.agt-badge--oa {
  background: rgba(29, 107, 191, 0.15);
  color: #5b9bd5;
}

.agt-paper-card-abstract {
  color: var(--agt-text-muted);
  font-size: 0.72rem;
  line-height: 1.4;
}
```

- [ ] **Step 6: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors.

- [ ] **Step 7: Commit**

```bash
git add zotero-addon/src/ui/components/PaperCard.tsx zotero-addon/src/ui/components/PaperCard.test.ts zotero-addon/src/ui/section.css
git commit -m "feat(ui): add PaperCard component"
```

---

## Task 9: `ReviewView` extracted & enhanced

**Files:**
- Create: `zotero-addon/src/ui/components/ReviewView.tsx`

### Background — ReviewView from App.tsx

Replaces the inline `ReviewView` in `App.tsx`. Key additions vs existing:
1. **Summary bar** with collection editable text input at review time
2. **Quick-select buttons** (all / top-ranked / none)
3. **PaperCard** per paper instead of the existing row rendering
4. **Sticky action bar** at bottom with live checked count

Controller fields used:
- `controller.papers` — `NormalizedPaper[]`
- `controller.selectedIndices` — `number[]`
- `controller.onToggleSelection(index: number)` — toggles a paper
- `controller.onApprove()` — submits selected papers
- `controller.collectionName` — current collection string
- `controller.onCollectionChange(name: string)` — updates collection

For quick-select "★★★" (all papers with score ≥ 0.8), call `controller.onToggleSelection` to deselect all below threshold and select all above. Use `getPaperIndex(paper, i)` from `contracts.ts` for the canonical index.

Read the existing inline `ReviewView` in `App.tsx` carefully before writing — preserve conflict-paper handling and any existing logic.

- [ ] **Step 1: Read the existing inline ReviewView in App.tsx**

Find `function ReviewView(` in `zotero-addon/src/ui/App.tsx`. Read every line. Note how it handles: conflicted papers, the write result display, and how `onApprove` is called.

- [ ] **Step 2: Create `ReviewView.tsx`**

Create `zotero-addon/src/ui/components/ReviewView.tsx`:

```typescript
import { createElement } from "react";
import { getPaperIndex } from "../../shared/contracts";
import { PaperCard } from "./PaperCard";
import type { SciAgentController } from "../App";

export function ReviewView({ controller }: { controller: SciAgentController }) {
  const { papers, selectedIndices } = controller;
  const selectedCount = selectedIndices.length;

  function selectAll(): void {
    papers.forEach((p, i) => {
      const idx = getPaperIndex(p, i);
      if (!selectedIndices.includes(idx)) controller.onToggleSelection(idx);
    });
  }

  function selectNone(): void {
    papers.forEach((p, i) => {
      const idx = getPaperIndex(p, i);
      if (selectedIndices.includes(idx)) controller.onToggleSelection(idx);
    });
  }

  function selectTopRanked(): void {
    papers.forEach((p, i) => {
      const idx = getPaperIndex(p, i);
      const score = p.score ?? p.semantic_score ?? 0;
      const shouldBeSelected = score >= 0.8;
      const isSelected = selectedIndices.includes(idx);
      if (shouldBeSelected !== isSelected) controller.onToggleSelection(idx);
    });
  }

  return createElement(
    "div",
    { className: "agt-review-view" },
    // Summary bar
    createElement(
      "div",
      { className: "agt-review-summary" },
      createElement(
        "span",
        { className: "agt-review-count" },
        `Found ${papers.length} · ${selectedCount} selected`,
      ),
      createElement(
        "div",
        { className: "agt-review-quick-select" },
        createElement("button", { type: "button", onClick: selectAll }, "all"),
        createElement("button", { type: "button", onClick: selectTopRanked }, "★★★"),
        createElement("button", { type: "button", onClick: selectNone }, "none"),
      ),
    ),
    // Collection picker row
    createElement(
      "div",
      { className: "agt-review-collection-row" },
      createElement("span", { className: "agt-review-collection-label" }, "→ Collection:"),
      createElement("input", {
        className: "agt-input agt-review-collection-input",
        type: "text",
        value: controller.collectionName,
        onChange: (e: { target: { value: string } }) => controller.onCollectionChange(e.target.value),
        placeholder: "Inbox",
      }),
    ),
    // Paper list
    createElement(
      "div",
      { className: "agt-review-list" },
      ...papers.map((paper, i) => {
        const idx = getPaperIndex(paper, i);
        return createElement(PaperCard, {
          key: idx,
          paper,
          selected: selectedIndices.includes(idx),
          onToggle: () => controller.onToggleSelection(idx),
        });
      }),
    ),
    // Action bar
    createElement(
      "div",
      { className: "agt-review-actions" },
      createElement(
        "button",
        {
          className: "agt-button agt-button--primary agt-review-approve",
          type: "button",
          disabled: selectedCount === 0,
          onClick: () => controller.onApprove(),
        },
        `✓ Add ${selectedCount} to Zotero`,
      ),
      createElement(
        "button",
        {
          className: "agt-button agt-review-new-search",
          type: "button",
          onClick: () => controller.onNewSearch?.(),
        },
        "↩ New search",
      ),
    ),
  );
}
```

> **Note:** Check if `controller.onNewSearch` exists. If not, look for a reset/clear function in the hook that returns the phase to idle, and use that instead.

- [ ] **Step 3: Add CSS**

In `section.css`, add:

```css
/* ── Review View ─────────────────────────────────────────────── */
.agt-review-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.agt-review-summary {
  align-items: center;
  background: var(--agt-surface-raised);
  border-bottom: 0.5px solid var(--agt-border);
  display: flex;
  flex-shrink: 0;
  justify-content: space-between;
  padding: 6px 14px;
}

.agt-review-count { font-size: 0.78rem; }

.agt-review-quick-select {
  display: flex;
  gap: 4px;
}

.agt-review-quick-select button {
  background: none;
  border: 0.5px solid var(--agt-border-strong);
  border-radius: 3px;
  color: var(--agt-text-muted);
  cursor: pointer;
  font-size: 0.7rem;
  padding: 1px 6px;
}

.agt-review-collection-row {
  align-items: center;
  border-bottom: 0.5px solid var(--agt-border);
  display: flex;
  flex-shrink: 0;
  gap: 6px;
  padding: 5px 14px;
}

.agt-review-collection-label {
  color: var(--agt-text-muted);
  flex-shrink: 0;
  font-size: 0.75rem;
}

.agt-review-collection-input { flex: 1; }

.agt-review-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 14px;
}

.agt-review-actions {
  background: var(--agt-surface-raised);
  border-top: 0.5px solid var(--agt-border);
  display: flex;
  flex-shrink: 0;
  gap: 6px;
  padding: 8px 14px;
}

.agt-review-approve { flex: 1; }

.agt-review-new-search {
  flex-shrink: 0;
}
```

- [ ] **Step 4: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors. Fix any missing controller method references.

- [ ] **Step 5: Commit**

```bash
git add zotero-addon/src/ui/components/ReviewView.tsx zotero-addon/src/ui/section.css
git commit -m "feat(ui): add ReviewView with PaperCard list and collection picker"
```

---

## Task 10: `DoneView` extracted & enhanced

**Files:**
- Create: `zotero-addon/src/ui/components/DoneView.tsx`

### Background — WriteResult shape

Replaces the inline `DoneView` in `App.tsx`. Shows: confirmation tick, count added, count skipped (already in library), elapsed time, and two action buttons (New search / View in Zotero).

The write result is available via `controller.writeResult`. `WriteResult` shape (from `contracts.ts`): `{ outcomes: WriteOutcome[]; elapsed_ms: number }`. Each `WriteOutcome` has a `status` field — `"added"` | `"skipped"` | `"failed"`.

Read the existing `DoneView` inline function in `App.tsx` before writing to preserve any existing logic.

- [ ] **Step 1: Read the existing inline DoneView in App.tsx**

Find `function DoneView(` in `zotero-addon/src/ui/App.tsx` and read it fully.

- [ ] **Step 2: Create `DoneView.tsx`**

Create `zotero-addon/src/ui/components/DoneView.tsx`:

```typescript
import { createElement } from "react";
import type { SciAgentController } from "../App";

export function DoneView({ controller }: { controller: SciAgentController }) {
  const writeResult = controller.writeResult;
  const outcomes = writeResult?.outcomes ?? [];
  const addedCount = outcomes.filter((o) => o.status === "added").length;
  const skippedCount = outcomes.filter((o) => o.status === "skipped").length;
  const elapsedSec = writeResult?.elapsed_ms !== undefined
    ? (writeResult.elapsed_ms / 1000).toFixed(1)
    : null;

  const handleViewInZotero = (): void => {
    // Attempt to focus the collection in the main Zotero pane.
    // This is best-effort; the host API may not support it in all versions.
    controller.onViewInZotero?.();
  };

  return createElement(
    "div",
    { className: "agt-done-view" },
    createElement("div", { className: "agt-done-tick" }, "✓"),
    createElement(
      "p",
      { className: "agt-done-headline" },
      `${addedCount} paper${addedCount !== 1 ? "s" : ""} added to Zotero`,
    ),
    createElement("p", { className: "agt-done-collection" }, `in collection: ${controller.collectionName}`),
    createElement(
      "div",
      { className: "agt-done-stats" },
      `📄 ${addedCount} added · ${skippedCount} skipped (already in library)`,
      elapsedSec !== null
        ? createElement("span", null, ` · ⏱ ${elapsedSec}s`)
        : null,
    ),
    createElement(
      "div",
      { className: "agt-done-actions" },
      createElement(
        "button",
        {
          className: "agt-button agt-button--primary",
          type: "button",
          onClick: () => controller.onNewSearch?.(),
        },
        "New search",
      ),
      createElement(
        "button",
        {
          className: "agt-button",
          type: "button",
          onClick: handleViewInZotero,
        },
        "View in Zotero",
      ),
    ),
  );
}
```

- [ ] **Step 3: Add CSS**

In `section.css`, add:

```css
/* ── Done View ───────────────────────────────────────────────── */
.agt-done-view {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
  min-height: 200px;
  padding: 20px 14px;
  text-align: center;
}

.agt-done-tick {
  color: var(--agt-green);
  font-size: 2rem;
}

.agt-done-headline {
  color: var(--agt-green);
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0;
}

.agt-done-collection {
  color: var(--agt-text-muted);
  font-size: 0.75rem;
  margin: 0;
}

.agt-done-stats {
  background: var(--agt-surface-raised);
  border: 0.5px solid var(--agt-border);
  border-radius: var(--agt-radius-sm);
  color: var(--agt-text-muted);
  font-size: 0.75rem;
  padding: 6px 12px;
}

.agt-done-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  width: 100%;
}

.agt-done-actions .agt-button { flex: 1; }
```

- [ ] **Step 4: Run typecheck**

```bash
cd zotero-addon && npm run typecheck
```

Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add zotero-addon/src/ui/components/DoneView.tsx zotero-addon/src/ui/section.css
git commit -m "feat(ui): add DoneView confirmation screen"
```

---

## Task 11: Wire the three-zone shell in `App.tsx`

**Files:**
- Modify: `zotero-addon/src/ui/App.tsx`

### Background — AppContent wiring

This is the wiring task. Replace the existing `AppContent` render tree with the three-zone shell using the new components. Remove the now-extracted inline views (IdleView, RunningView, ReviewView, DoneView). Remove the old `StatusPill` function. Keep the `ErrorBoundary`.

The existing `AppContent` function renders:
- A `<div className="agt-root">` with a `<div className="agt-shell">` containing a `<header>` and phase views.

Replace the body with the new layout.

`uiState` derivation (already in App.tsx, preserve the logic):
- `"idle"` when `phase === "idle" || phase === "error"`  
- `"running"` when `phase === "submitting" || phase === "running"`
- `"review"` when `phase === "awaiting_approval"`
- `"done"` when `phase === "completed" || phase === "rejected" || phase === "resuming"`

For `onOpenSettings`: call `services.openPreferences()` if that method exists on `AddonUiServices`, otherwise use `(globalThis as { Zotero?: { openPreferences(pane?: string): void } }).Zotero?.openPreferences("SciAgent")`.

- [ ] **Step 1: Check `AddonUiServices` for openPreferences**

Read `zotero-addon/src/ui/serviceTypes.ts` (or wherever `AddonUiServices` is defined). Check whether it has an `openPreferences` method. If not, you will call the Zotero global directly.

- [ ] **Step 2: Replace AppContent in App.tsx**

In `App.tsx`, replace the `function AppContent(...)` body. Keep the `export type SciAgentController` and `ErrorBoundary` class. Remove the old `StatusPill` function, and remove the inline `IdleView`, `RunningView`, `ReviewView`, `DoneView` functions. Import the new components:

```typescript
import { HeaderBar } from "./components/HeaderBar";
import { HealthStrip } from "./components/HealthStrip";
import { IdleView } from "./components/IdleView";
import { RunningView } from "./components/RunningView";
import { ReviewView } from "./components/ReviewView";
import { DoneView } from "./components/DoneView";
```

New `AppContent` body:

```typescript
function AppContent({ services }: { services: AddonUiServices }) {
  const controller = useSciAgentController(services);
  const phase = controller.runView.phase;

  const uiState: "idle" | "running" | "review" | "done" =
    phase === "submitting" || phase === "running"
      ? "running"
      : phase === "awaiting_approval"
        ? "review"
        : phase === "completed" || phase === "resuming"
          ? "done"
          : "idle";

  function openSettings(): void {
    (globalThis as { Zotero?: { openPreferences(pane?: string): void } })
      .Zotero?.openPreferences("SciAgent");
  }

  return createElement(
    "div",
    { className: "agt-root" },
    createElement(
      "div",
      { className: "agt-shell" },
      createElement(HeaderBar, {
        phase,
        isMinConfigMissing: controller.isMinConfigMissing,
        onOpenSettings: openSettings,
        onCancel: controller.onCancel,
      }),
      createElement(HealthStrip, {
        healthResponse: controller.healthResponse,
        healthBusy: controller.healthBusy,
        config: controller.config,
      }),
      createElement(
        "div",
        { className: "agt-content" },
        uiState === "idle" && createElement(IdleView, { controller, addonVersion: services.addonVersion }),
        uiState === "running" && createElement(RunningView, { controller }),
        uiState === "review" && createElement(ReviewView, { controller }),
        uiState === "done" && createElement(DoneView, { controller }),
      ),
    ),
  );
}
```

- [ ] **Step 3: Add `.agt-content` CSS**

In `section.css`, add:

```css
.agt-content {
  flex: 1;
  overflow-y: auto;
}
```

- [ ] **Step 4: Run full quality gates**

```bash
cd zotero-addon && npm ci && npm run lint && npm run build && npm run typecheck && npm run test
```

Expected: all pass with zero errors. Fix any remaining type or lint issues before committing.

- [ ] **Step 5: Final commit**

```bash
git add zotero-addon/src/ui/App.tsx zotero-addon/src/ui/section.css
git commit -m "feat(ui): wire three-zone shell — HeaderBar + HealthStrip + phase views"
```

---

## Self-Review Checklist

After all tasks are complete, verify against the spec:

- [ ] Zone 1 header always visible with status pill and ⚙/cancel button *(Task 2)*
- [ ] ⚙ button turns red when backend URL, Zotero key, or all LLM keys are missing *(Task 1, 2)*
- [ ] ⚙ button opens Zotero preferences to SciAgent tab *(Task 11)*
- [ ] Health strip always visible with Backend · Zotero · LLM indicators *(Task 3)*
- [ ] Optional S2 key nudge hidden when apiKey is set *(Task 3)*
- [ ] Advanced filters collapse/expand; all 6 fields present *(Task 4)*
- [ ] Year dropdown applies to `filterDraft.min_year` *(Task 5)*
- [ ] ABC✓ spell-check and ⚑ keyword-extract buttons present in idle view *(Task 5)*
- [ ] Running state shows pipeline tracker with per-stage icons *(Tasks 6, 7)*
- [ ] Running state shows per-source status rows *(Task 7)*
- [ ] Paper cards show title, authors/year/venue, stars, source badge, citation count, OA badge *(Task 8)*
- [ ] Abstract shown for ★★★ and ★★☆ only *(Task 8)*
- [ ] Review summary bar has quick-select buttons and live count *(Task 9)*
- [ ] Review collection picker defaults to current collection and is editable *(Task 9)*
- [ ] "Add to Zotero" label reflects live checked count *(Task 9)*
- [ ] Done screen shows added/skipped counts and elapsed time *(Task 10)*
- [ ] All quality gates pass: `npm run lint && npm run build && npm run typecheck && npm run test` *(Task 11)*
