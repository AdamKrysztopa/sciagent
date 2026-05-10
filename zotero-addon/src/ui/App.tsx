import type { WriteResult } from "../shared/contracts";
import type { NativeWriteResult } from "../host/zoteroWriter";

import { Component, type ErrorInfo, type ReactNode } from "react";
import type { AddonUiServices } from "./serviceTypes";
import { ConfigPanel } from "./components/ConfigPanel";
import { FilterEditor } from "./components/FilterEditor";
import { HealthStatus } from "./components/HealthStatus";
import { ResultsList } from "./components/ResultsList";
import { SourceToggles } from "./components/SourceToggles";
import { type RunPhase, useSciAgentController } from "./hooks/useSciAgentController";

// ── Error Boundary ──────────────────────────────────────────────────────────

interface ErrorBoundaryState {
  error: Error | null;
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    try {
      const zotero = (globalThis as unknown as { Zotero?: { debug(msg: string): void } }).Zotero;
      zotero?.debug(`[SciAgent] React error boundary caught: ${error.message}\n${info.componentStack ?? ""}`);
    } catch {
      // Swallow — we are already in an error state.
    }
  }

  render(): ReactNode {
    if (this.state.error !== null) {
      return (
        <div style={{ background: "#fff", color: "#c0392b", fontFamily: "monospace", padding: "16px" }}>
          <strong>SciAgent UI Error</strong>
          <pre style={{ fontSize: "11px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {this.state.error.message}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── StatusPill ──────────────────────────────────────────────────────────────

function StatusPill({
  phase,
  healthBusy,
  healthOk,
}: {
  phase: RunPhase;
  healthBusy: boolean;
  healthOk: boolean;
}) {
  if (phase === "submitting" || phase === "resuming") {
    return <span className="agt-status-pill agt-status-pill--loading">searching…</span>;
  }
  if (!healthOk && !healthBusy) {
    return <span className="agt-status-pill agt-status-pill--error">backend offline</span>;
  }
  if (healthBusy) {
    return <span className="agt-status-pill agt-status-pill--loading">connecting…</span>;
  }
  return <span className="agt-status-pill agt-status-pill--ok">backend connected</span>;
}

// ── Write result helpers ────────────────────────────────────────────────────

function renderNativeWriteResult(nativeWriteResult: NativeWriteResult | null) {
  if (nativeWriteResult === null) {
    return null;
  }

  return (
    <div className="agt-outcomes">
      <p className="agt-meta">Collection: {nativeWriteResult.collectionName}</p>
      <div className="agt-chip-list">
        <span className="agt-chip agt-chip--ok">created: {nativeWriteResult.created}</span>
        <span className="agt-chip">unchanged: {nativeWriteResult.unchanged}</span>
        <span className="agt-chip agt-chip--danger">failed: {nativeWriteResult.failed}</span>
        {nativeWriteResult.pdfAttached > 0 ? (
          <span className="agt-chip agt-chip--ok">PDF attached: {nativeWriteResult.pdfAttached}</span>
        ) : null}
        {nativeWriteResult.pdfFailed > 0 ? (
          <span className="agt-chip agt-chip--danger">PDF failed: {nativeWriteResult.pdfFailed}</span>
        ) : null}
      </div>
      {nativeWriteResult.outcomes.map((outcome, idx) => (
        <div className="agt-outcome-row" key={`${outcome.paper.doi ?? ""}-${outcome.paper.title}`}>
          <span>{outcome.paper.index ?? idx + 1}</span>
          <span>
            <strong>{outcome.paper.title}</strong>
            {outcome.reason !== null ? <span className="agt-meta"> {outcome.reason}</span> : null}
            {outcome.pdfStatus === "attached" ? (
              <span className="agt-chip agt-chip--ok" style={{ marginLeft: "4px" }}>PDF ✓</span>
            ) : null}
            {outcome.pdfStatus === "failed" ? (
              <span className="agt-chip agt-chip--danger" style={{ marginLeft: "4px" }}>PDF failed</span>
            ) : null}
            {outcome.pdfStatus === "skipped" ? (
              <span className="agt-chip" style={{ marginLeft: "4px" }}>no PDF URL</span>
            ) : null}
          </span>
          <span>{outcome.status}</span>
        </div>
      ))}
    </div>
  );
}

function renderWriteResult(writeResult: WriteResult | null) {
  if (writeResult === null) {
    return <p className="agt-empty-state">No write attempt yet.</p>;
  }

  return (
    <div className="agt-outcomes">
      <div className="agt-chip-list">
        <span className="agt-chip agt-chip--ok">created: {writeResult.created}</span>
        <span className="agt-chip">unchanged: {writeResult.unchanged}</span>
        <span className="agt-chip agt-chip--danger">failed: {writeResult.failed}</span>
      </div>
      {writeResult.outcomes.map((outcome) => (
        <div className="agt-outcome-row" key={`${outcome.index}-${outcome.title}`}>
          <span>{outcome.index}</span>
          <span>
            <strong>{outcome.title}</strong>
            {outcome.reason !== null ? <span className="agt-meta"> {outcome.reason}</span> : null}
          </span>
          <span>{outcome.status}</span>
        </div>
      ))}
    </div>
  );
}

// ── State views ─────────────────────────────────────────────────────────────

type SciAgentController = ReturnType<typeof useSciAgentController>;

function IdleView({ controller }: { controller: SciAgentController }) {
  return (
    <div className="agt-state-view">
      <section className="agt-card">
        <div className="agt-section-heading">
          <h2>Search</h2>
          <button
            className="agt-button agt-button--warn"
            disabled={controller.query.trim().length === 0}
            onClick={controller.onSubmitSearch}
            type="button"
          >
            {controller.filterDraft === null ? "Search" : "Re-run Search"}
          </button>
        </div>
        {controller.runView.error !== null ? (
          <div className="agt-error">{controller.runView.error}</div>
        ) : null}
        <label className="agt-field">
          <span>Query</span>
          <textarea
            className="agt-textarea"
            onChange={(event) => controller.onQueryChange(event.target.value)}
            rows={3}
            value={controller.query}
          />
        </label>
        <label className="agt-field">
          <span>Collection Name</span>
          <input
            className="agt-input"
            onChange={(event) => controller.onCollectionChange(event.target.value)}
            type="text"
            value={controller.collectionName}
          />
        </label>
      </section>

      <FilterEditor
        disabled={false}
        filterDraft={controller.filterDraft}
        onChange={controller.onFilterDraftChange}
        onReset={controller.onResetFilters}
        searchPlan={controller.searchPlan}
      />

      {controller.sourcePolicy.length > 0 ? (
        <section className="agt-card agt-card--soft">
          <SourceToggles sourcePolicy={controller.sourcePolicy} />
        </section>
      ) : null}

      <section className="agt-card agt-card--soft">
        <div className="agt-section-heading">
          <h2>Backend</h2>
          <div className="agt-inline-actions">
            <button
              className="agt-button agt-button--ghost"
              disabled={controller.healthBusy}
              onClick={controller.onRefreshHealth}
              type="button"
            >
              {controller.healthBusy ? "Checking…" : "Refresh"}
            </button>
          </div>
        </div>
        <HealthStatus
          busy={controller.healthBusy}
          error={controller.healthError}
          onRefresh={controller.onRefreshHealth}
          response={controller.healthResponse}
        />
      </section>

      <section className="agt-card agt-card--soft">
        <ConfigPanel
          config={controller.config}
          onChange={controller.onConfigChange}
          onSave={controller.onSaveConfig}
          saveError={controller.saveError}
          saveState={controller.saveState}
        />
      </section>
    </div>
  );
}

function RunningView({ controller }: { controller: SciAgentController }) {
  return (
    <div className="agt-state-view">
      <div className="agt-spinner-wrap">
        <div className="agt-spinner" />
        <p className="agt-meta">Searching…</p>
      </div>
      {controller.query.trim().length > 0 ? (
        <div className="agt-running-query">{controller.query.trim()}</div>
      ) : null}
      {controller.searchPlan !== null ? (
        <section className="agt-card agt-card--soft">
          <div className="agt-section-heading">
            <h2>Search Plan</h2>
          </div>
          <div className="agt-chip-list">
            {controller.searchPlan.source_policy.map((src) => (
              <span className="agt-chip" key={src.name}>{src.name}</span>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function ReviewView({ controller }: { controller: SciAgentController }) {
  const currentState = controller.runView.snapshot?.state ?? null;
  return (
    <div className="agt-state-view">
      {controller.query.trim().length > 0 ? (
        <div className="agt-running-query">{controller.query.trim()}</div>
      ) : null}

      {controller.runView.error !== null ? (
        <div className="agt-error">{controller.runView.error}</div>
      ) : null}

      <FilterEditor
        disabled={true}
        filterDraft={controller.filterDraft}
        onChange={controller.onFilterDraftChange}
        onReset={controller.onResetFilters}
        searchPlan={controller.searchPlan}
      />

      <ResultsList
        disabled={controller.runView.phase === "resuming"}
        onToggle={controller.onToggleSelection}
        papers={controller.papers}
        selectedIndices={controller.selectedIndices}
      />

      {controller.sourceBuckets !== null ? (
        <section className="agt-card agt-card--soft">
          <div className="agt-section-heading">
            <h2>Sources</h2>
            {controller.runView.snapshot !== null ? (
              <span className="agt-pill agt-pill--muted">{controller.runView.snapshot.run_id}</span>
            ) : null}
          </div>
          <div className="agt-chip-list">
            {controller.sourceBuckets.used.map((source) => (
              <span className="agt-chip agt-chip--ok" key={`used-${source}`}>used: {source}</span>
            ))}
            {controller.sourceBuckets.failed.map((source) => (
              <span className="agt-chip agt-chip--danger" key={`failed-${source}`}>failed: {source}</span>
            ))}
            {controller.sourceBuckets.skipped.map((source) => (
              <span className="agt-chip agt-chip--warn" key={`skipped-${source}`}>skipped: {source}</span>
            ))}
            {controller.sourceBuckets.unavailable_optional.map((source) => (
              <span className="agt-chip" key={`missing-${source}`}>optional key missing: {source}</span>
            ))}
          </div>
        </section>
      ) : null}

      {currentState !== null ? (
        <div className="agt-card">
          <div className="agt-section-heading">
            <h2>Approval</h2>
            {currentState.collection_name !== null ? (
              <span className="agt-pill agt-pill--muted">→ {currentState.collection_name}</span>
            ) : null}
          </div>
          <div className="agt-action-cluster">
            <button
              className="agt-button agt-button--warn"
              disabled={!controller.canApprove || controller.runView.phase === "resuming"}
              onClick={controller.onApprove}
              type="button"
            >
              {controller.runView.phase === "resuming" ? "Applying…" : "Approve Selected"}
            </button>
            <button
              className="agt-button agt-button--danger"
              disabled={controller.runView.phase === "resuming" || controller.runView.phase !== "awaiting_approval"}
              onClick={controller.onReject}
              type="button"
            >
              Reject
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function DoneView({ controller }: { controller: SciAgentController }) {
  const currentState = controller.runView.snapshot?.state ?? null;
  return (
    <div className="agt-state-view">
      <section className="agt-card">
        <div className="agt-section-heading">
          <h2>Write Result</h2>
          <button
            className="agt-button agt-button--ghost"
            onClick={controller.onReset}
            type="button"
          >
            New Search
          </button>
        </div>
        {controller.nativeWriteResult !== null
          ? renderNativeWriteResult(controller.nativeWriteResult)
          : renderWriteResult(currentState?.write_result ?? null)}
      </section>
    </div>
  );
}

// ── App root ────────────────────────────────────────────────────────────────

export function App({ services }: { services: AddonUiServices }) {
  const controller = useSciAgentController(services);
  const healthOk = controller.healthResponse?.ok === true;

  const uiState: "idle" | "running" | "review" | "done" =
    controller.runView.phase === "submitting" || controller.runView.phase === "resuming"
      ? "running"
      : controller.runView.phase === "awaiting_approval"
        ? "review"
        : controller.runView.phase === "completed" &&
            (controller.nativeWriteResult !== null ||
              controller.runView.snapshot?.state?.write_result != null)
          ? "done"
          : "idle";

  return (
    <ErrorBoundary>
      <div className="agt-root">
        <div className="agt-shell">
          <header className="agt-titlebar">
            <span className="agt-title">SciAgent</span>
            <StatusPill
              healthBusy={controller.healthBusy}
              healthOk={healthOk}
              phase={controller.runView.phase}
            />
          </header>

          {uiState === "idle" && <IdleView controller={controller} />}
          {uiState === "running" && <RunningView controller={controller} />}
          {uiState === "review" && <ReviewView controller={controller} />}
          {uiState === "done" && <DoneView controller={controller} />}
        </div>
      </div>
    </ErrorBoundary>
  );
}

