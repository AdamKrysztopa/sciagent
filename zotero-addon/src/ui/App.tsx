import type { HealthResponse, WriteResult } from "../shared/contracts";
import { getPaperIndex } from "../shared/contracts";
import type { NativeWriteResult } from "../host/zoteroWriter";

import { Component, type ErrorInfo, type ReactNode, useEffect, useRef, useState } from "react";
import type { AddonUiServices } from "./serviceTypes";
import { BackendFailurePanel } from "./components/BackendFailurePanel";
import { CapabilityBanner } from "./components/CapabilityBanner";
import { ConfigPanel } from "./components/ConfigPanel";
import { FilterEditor } from "./components/FilterEditor";
import { FirstRunConfigCard } from "./components/FirstRunConfigCard";
import { FirstRunDialog } from "./components/FirstRunDialog";
import { HealthStatus } from "./components/HealthStatus";
import { LibraryDoctor } from "./components/LibraryDoctor";
import { ResultsList } from "./components/ResultsList";
import { SearchCoveragePanel } from "./components/SearchCoveragePanel";
import { SourcePresets } from "./components/SourcePresets";
import { SourceToggles } from "./components/SourceToggles";
import { WatchList } from "./components/WatchList";
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

function IdleView({ controller, addonVersion }: { controller: SciAgentController; addonVersion?: string }) {
  const disabledReason = searchDisabledReason(controller);

  return (
    <div className="agt-state-view">
      {controller.healthError !== null && controller.healthResponse === null ? (
        <BackendFailurePanel
          error={controller.healthError}
          onRetry={controller.onRefreshHealth}
          backendMode={controller.config.backendMode}
        />
      ) : null}

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

      {!controller.config.bannerDismissed &&
      (controller.healthResponse !== null || controller.healthError !== null) ? (
        <CapabilityBanner
          backendOk={controller.healthResponse !== null && controller.healthError === null}
          llmProviderOk={
            controller.capabilities?.active_provider !== undefined &&
            controller.capabilities.active_provider !== ""
          }
          zoteroWriteOk={controller.healthResponse?.preflight.can_write === true}
          pdfImportOk={controller.capabilities?.pdf_import_supported === true}
          onDismiss={controller.onDismissBanner}
        />
      ) : null}

      <SourcePresets
        disabled={false}
        filterDraft={controller.filterDraft}
        onChange={controller.onFilterDraftChange}
        searchDepth={controller.searchDepth}
        onDepthChange={controller.onDepthChange}
      />

      <FilterEditor
        disabled={false}
        filterDraft={controller.filterDraft}
        onChange={controller.onFilterDraftChange}
        onReset={controller.onResetFilters}
        onSuggestAuthors={controller.onSuggestAuthors}
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
        addonVersion={addonVersion}
        config={controller.config}
        onChange={controller.onConfigChange}
        onSave={controller.onSaveConfig}
        saveError={controller.saveError}
        saveState={controller.saveState}
        onValidateKey={controller.validateKey}
      />

      <LibraryDoctor
        collectionName={controller.collectionName}
        error={controller.doctorError}
        onScan={controller.onLibraryDoctor}
        report={controller.doctorReport}
        scanning={controller.doctorScanning}
      />

      <section className="agt-card agt-card--soft">
        <div className="agt-section-heading">
          <h2>Gap Finder</h2>
          <button
            className="agt-button agt-button--ghost"
            disabled={controller.gapRunning || controller.healthResponse === null}
            onClick={controller.onGapFinder}
            type="button"
          >
            {controller.gapRunning ? "Analysing…" : "Find Gaps"}
          </button>
        </div>
        <p className="agt-small-note">
          Suggests missing seminal papers, recent follow-ups, and reviews for the current collection.
        </p>
        {controller.gapError !== null ? (
          <div className="agt-error">{controller.gapError}</div>
        ) : null}
        {controller.gapResult !== null ? (
          <>
            <p className="agt-small-note">{controller.gapResult.reasoning}</p>
            {controller.gapResult.papers.length === 0 ? (
              <p className="agt-empty-state">No gaps found.</p>
            ) : (
              <ul className="agt-gap-list">
                {controller.gapResult.papers.map((paper, i) => (
                  <li className="agt-gap-item" key={paper.doi ?? paper.title ?? i}>
                    {paper.url !== null ? (
                      <a href={paper.url} rel="noreferrer" target="_blank">{paper.title}</a>
                    ) : (
                      paper.title
                    )}
                    {paper.year !== null ? <span className="agt-gap-year"> ({paper.year})</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : null}
      </section>

      <WatchList
        canSave={controller.query.trim().length > 0}
        error={controller.watchesError}
        lastRerun={controller.lastWatchRerun}
        loading={controller.watchesLoading}
        onDelete={controller.onDeleteWatch}
        onRerun={controller.onRerunWatch}
        onSaveWatch={controller.onSaveWatch}
        onWatchNameChange={controller.onWatchNameChange}
        rerunningId={controller.rerunningWatchId}
        saveError={controller.watchSaveError}
        saving={controller.watchSaving}
        watchName={controller.watchName}
        watches={controller.watches}
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
  const conflictedPapers = controller.papers
    .filter((p, i) => controller.selectedIndices.includes(getPaperIndex(p, i)))
    .filter((p) => p.conflicts != null && p.conflicts.length > 0);
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
        onSuggestAuthors={controller.onSuggestAuthors}
        searchPlan={controller.searchPlan}
      />

      {controller.searchMetadata !== null ? (
        <section className="agt-card agt-card--soft">
          <div className="agt-section-heading">
            <h2>Search Info</h2>
            <span className="agt-pill agt-pill--muted">
              {controller.searchMetadata.mode === "llm_rewrite" ? "LLM rewrite" : "regex"}
            </span>
          </div>
          <div className="agt-key-value">
            {controller.searchMetadata.rewritten_query !== null &&
            controller.searchMetadata.rewritten_query !== controller.searchMetadata.original_query ? (
              <>
                <span>Rewritten query</span>
                <span>{controller.searchMetadata.rewritten_query}</span>
              </>
            ) : null}
            <span>Fetched</span>
            <span>{controller.searchMetadata.total_fetched}</span>
            <span>After filters</span>
            <span>{controller.searchMetadata.total_after_filter}</span>
          </div>
        </section>
      ) : null}

      <ResultsList
        disabled={controller.runView.phase === "resuming"}
        onToggle={controller.onToggleSelection}
        papers={controller.papers}
        selectedIndices={controller.selectedIndices}
      />

      {controller.searchMetadata !== null &&
      Object.keys(controller.searchMetadata.source_states).length > 0 ? (
        <SearchCoveragePanel
          sourceStates={controller.searchMetadata.source_states}
          baselineMode={controller.searchMetadata.baseline_mode}
          providers={controller.providers}
        />
      ) : null}

      {currentState !== null ? (
        <div className="agt-card">
          <div className="agt-section-heading">
            <h2>Approval</h2>
            {currentState.collection_name !== null ? (
              <span className="agt-pill agt-pill--muted">→ {currentState.collection_name}</span>
            ) : null}
          </div>
          {conflictedPapers.length > 0 ? (
            <div className="agt-conflict-warning" role="alert">
              <strong>⚠ {conflictedPapers.length} selected paper{conflictedPapers.length > 1 ? "s have" : " has"} field conflicts:</strong>
              <ul className="agt-conflict-list">
                {conflictedPapers.flatMap((p) =>
                  (p.conflicts ?? []).map((c) => (
                    <li key={`${p.doi ?? p.title}-${c.field}`}>
                      <strong>{p.title.slice(0, 40)}{p.title.length > 40 ? "…" : ""}</strong>
                      {": "}
                      <span className="agt-conflict-field">{c.field}</span>
                      {" — "}
                      {c.values.map((v) => `${v.provider}: ${String(v.value)}`).join(" vs ")}
                    </li>
                  ))
                )}
              </ul>
            </div>
          ) : null}
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

  // Binary check: runs once after prefs load confirms backendMode="local" (P9.0 default).
  // If the binary is missing, shows FirstRunDialog to download it.
  // On completion, triggers a health re-check so the pill turns green without manual action.
  const [binarySetup, setBinarySetup] = useState<"ready" | "needed">("ready");
  const binaryCheckDoneRef = useRef(false);
  const binaryWasNeededRef = useRef(false);

  useEffect(() => {
    if (binaryCheckDoneRef.current) return;
    if (controller.config.backendMode !== "local") return;
    if (services.checkBinaryInstalled === undefined) {
      binaryCheckDoneRef.current = true;
      return;
    }
    binaryCheckDoneRef.current = true;
    void services.checkBinaryInstalled().then((installed) => {
      if (!installed) {
        binaryWasNeededRef.current = true;
        setBinarySetup("needed");
      }
    });
  }, [controller.config.backendMode, services]);

  // After download completes and binarySetup returns to "ready", refresh health
  // so the pill updates without the user pressing "Retry".
  useEffect(() => {
    if (binarySetup === "ready" && binaryWasNeededRef.current) {
      binaryWasNeededRef.current = false;
      controller.onRefreshHealth();
    }
  }, [binarySetup, controller]);

  // First-run config card: shown when binary is ready but no LLM key is configured.
  const [firstRunConfigDone, setFirstRunConfigDone] = useState(false);
  const hasLlmKey =
    controller.config.openaiApiKey.length > 0 ||
    controller.config.anthropicApiKey.length > 0 ||
    controller.config.xaiApiKey.length > 0 ||
    controller.config.groqApiKey.length > 0;
  const showFirstRunConfig = binarySetup === "ready" && !hasLlmKey && !firstRunConfigDone;

  if (binarySetup === "needed") {
    return (
      <div className="agt-root">
        <div className="agt-shell">
          <header className="agt-titlebar">
            <span className="agt-title">SciAgent</span>
          </header>
          <FirstRunDialog
            onComplete={() => setBinarySetup("ready")}
            onSkip={() => setBinarySetup("ready")}
            services={services}
          />
        </div>
      </div>
    );
  }

  if (showFirstRunConfig) {
    return (
      <div className="agt-root">
        <div className="agt-shell">
          <header className="agt-titlebar">
            <span className="agt-title">SciAgent</span>
          </header>
          <FirstRunConfigCard
            config={controller.config}
            onSave={(update) => { controller.onSaveFirstRunConfig(update); }}
            onSkip={() => { setFirstRunConfigDone(true); }}
          />
        </div>
      </div>
    );
  }

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

        {uiState === "idle" && <IdleView addonVersion={services.addonVersion} controller={controller} />}
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

