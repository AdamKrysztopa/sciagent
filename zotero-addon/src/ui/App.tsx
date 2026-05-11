import type { HealthResponse, WriteResult } from "../shared/contracts";
import type { NativeWriteResult } from "../host/zoteroWriter";

import { Component, type ErrorInfo, type ReactNode } from "react";
import type { AddonUiServices } from "./serviceTypes";
import { ConfigPanel } from "./components/ConfigPanel";
import { FilterEditor } from "./components/FilterEditor";
import { HealthStatus } from "./components/HealthStatus";
import { ResultsList } from "./components/ResultsList";
import { SourcePresets } from "./components/SourcePresets";
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
        <div className="agt-root agt-root--error">
          <section className="agt-card agt-startup-error" role="alert">
            <h2>SciAgent UI Error</h2>
            <pre>{this.state.error.message}</pre>
          </section>
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
  healthError,
  healthResponse,
}: {
  phase: RunPhase;
  healthBusy: boolean;
  healthError: string | null;
  healthResponse: HealthResponse | null;
}) {
  const content = (className: string, label: string, title?: string) => (
    <output className={`agt-status-pill ${className}`} aria-live="polite" title={title ?? label}>
      <span className="agt-status-dot" aria-hidden="true" />
      {label}
    </output>
  );

  if (phase === "submitting" || phase === "resuming") {
    return content("agt-status-pill--loading", "searching…");
  }
  if (healthBusy) {
    return content("agt-status-pill--loading", "connecting…");
  }
  if (healthResponse?.ok === true) {
    return content("agt-status-pill--ok", "backend healthy");
  }
  if (healthResponse !== null) {
    return content(
      "agt-status-pill--warn",
      "backend reachable",
      healthResponse.preflight.message ?? healthResponse.message,
    );
  }
  if (healthError !== null) {
    return content("agt-status-pill--error", "backend offline", healthError);
  }
  return content("agt-status-pill--idle", "backend not checked");
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

function searchDisabledReason(controller: SciAgentController): string | null {
  if (controller.query.trim().length === 0) {
    return "Enter a query before searching.";
  }
  if (controller.healthBusy) {
    return "Checking the backend connection.";
  }
  if (controller.healthResponse?.ok === true) {
    return null;
  }
  if (controller.healthResponse !== null) {
    return null;
  }
  if (controller.healthError !== null) {
    return `Backend unavailable: ${controller.healthError}`;
  }
  return "Backend health has not been checked yet.";
}

function IdleView({ controller }: { controller: SciAgentController }) {
  const disabledReason = searchDisabledReason(controller);

  return (
    <div className="agt-state-view">
      <section className="agt-card">
        <div className="agt-section-heading">
          <h2>Search</h2>
          <button
            className="agt-button agt-button--warn"
            disabled={disabledReason !== null}
            onClick={controller.onSubmitSearch}
            title={disabledReason ?? "Run search"}
            type="button"
          >
            {controller.searchPlan === null ? "Search" : "Re-run Search"}
          </button>
        </div>
        {controller.runView.error !== null ? (
          <div className="agt-error">{controller.runView.error}</div>
        ) : null}
        <div className="agt-field">
          <div className="agt-field-header">
            <span>Query</span>
            <button
              className="agt-button agt-button--ghost agt-button--sm"
              disabled={controller.query.trim().length === 0 || controller.extracting || controller.healthResponse === null}
              onClick={controller.onExtractKeywords}
              title="Extract keywords and collection name from the query text"
              type="button"
            >
              {controller.extracting ? "Extracting…" : "Extract"}
            </button>
          </div>
          <textarea
            className="agt-textarea"
            onChange={(event) => controller.onQueryChange(event.target.value)}
            rows={3}
            value={controller.query}
          />
          {controller.extractError !== null ? (
            <span className="agt-small-note agt-small-note--error">{controller.extractError}</span>
          ) : null}
        </div>
        <label className="agt-field">
          <span>Collection Name</span>
          <input
            className="agt-input"
            onChange={(event) => controller.onCollectionChange(event.target.value)}
            type="text"
            value={controller.collectionName}
          />
        </label>
        {controller.correctedQuery !== null ? (
          <output className="agt-status-note agt-spell-suggestion" aria-live="polite">
            {"Did you mean: "}
            <button
              className="agt-link-button"
              onClick={controller.onAcceptCorrection}
              type="button"
            >
              {controller.correctedQuery}
            </button>
            {"?"}
          </output>
        ) : null}
        {disabledReason !== null && controller.query.trim().length > 0 ? (
          <output className="agt-status-note agt-status-note--warn" aria-live="polite">
            {disabledReason}
          </output>
        ) : null}
      </section>

      <SourcePresets
        disabled={false}
        filterDraft={controller.filterDraft}
        onChange={controller.onFilterDraftChange}
      />

      <FilterEditor
        disabled={false}
        filterDraft={controller.filterDraft}
        onChange={controller.onFilterDraftChange}
        onReset={controller.onResetFilters}
        searchPlan={controller.searchPlan}
      />

      {controller.sourcePolicy.length > 0 ? <SourceToggles sourcePolicy={controller.sourcePolicy} /> : null}

      <HealthStatus
        busy={controller.healthBusy}
        error={controller.healthError}
        onRefresh={controller.onRefreshHealth}
        response={controller.healthResponse}
      />

      <ConfigPanel
        config={controller.config}
        onChange={controller.onConfigChange}
        onSave={controller.onSaveConfig}
        saveError={controller.saveError}
        saveState={controller.saveState}
      />
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

function AppContent({ services }: { services: AddonUiServices }) {
  const controller = useSciAgentController(services);

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
    <div className="agt-root">
      <div className="agt-shell">
        <header className="agt-titlebar">
          <span className="agt-title">SciAgent</span>
          <StatusPill
            healthError={controller.healthError}
            healthBusy={controller.healthBusy}
            healthResponse={controller.healthResponse}
            phase={controller.runView.phase}
          />
        </header>

        {uiState === "idle" && <IdleView controller={controller} />}
        {uiState === "running" && <RunningView controller={controller} />}
        {uiState === "review" && <ReviewView controller={controller} />}
        {uiState === "done" && <DoneView controller={controller} />}
      </div>
    </div>
  );
}

export function App({ services }: { services: AddonUiServices }) {
  return (
    <ErrorBoundary>
      <AppContent services={services} />
    </ErrorBoundary>
  );
}

