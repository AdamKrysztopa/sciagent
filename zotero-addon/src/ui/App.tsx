import type { WriteResult } from "../shared/contracts";

import type { AddonUiServices } from "./serviceTypes";
import { ConfigPanel } from "./components/ConfigPanel";
import { FilterEditor } from "./components/FilterEditor";
import { HealthStatus } from "./components/HealthStatus";
import { ResultsList } from "./components/ResultsList";
import { useSciAgentController } from "./hooks/useSciAgentController";

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

export function App({ services }: { services: AddonUiServices }) {
  const controller = useSciAgentController(services);
  const currentState = controller.runView.snapshot?.state ?? null;

  return (
    <div className="agt-shell">
      <header className="agt-header">
        <div className="agt-title-wrap">
          <h1>SciAgent</h1>
          <p>Native Zotero pane with backend-delegated search, approval, and write flow.</p>
        </div>
        <span className={`agt-pill ${controller.runView.phase === "awaiting_approval" ? "agt-pill--loading" : controller.runView.phase === "completed" ? "agt-pill--ok" : controller.runView.phase === "failed" || controller.runView.phase === "error" ? "agt-pill--error" : "agt-pill--muted"}`}>
          {controller.runView.phase.replaceAll("_", " ")}
        </span>
      </header>

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

      <section className="agt-card">
        <div className="agt-section-heading">
          <h2>Search</h2>
          <div className="agt-action-cluster">
            <button
              className="agt-button agt-button--warn"
              disabled={controller.runView.phase === "submitting" || controller.query.trim().length === 0}
              onClick={controller.onSubmitSearch}
              type="button"
            >
              {controller.runView.phase === "submitting" ? "Searching..." : controller.filterDraft === null ? "Search" : "Re-run Search"}
            </button>
            <button
              className="agt-button agt-button--ghost"
              disabled={controller.searchPlan === null}
              onClick={controller.onResetFilters}
              type="button"
            >
              Reset Filters
            </button>
          </div>
        </div>
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
        <p className="agt-hint">
          First run the natural-language query. The pane then loads the backend search plan from <code>/status</code> and exposes the parsed filters for review and edit.
        </p>
        {controller.runView.error !== null ? <div className="agt-error">{controller.runView.error}</div> : null}
      </section>

      <FilterEditor
        disabled={controller.runView.phase === "submitting" || controller.runView.phase === "resuming"}
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

      <section className="agt-card agt-card--soft">
        <div className="agt-section-heading">
          <h2>Run State</h2>
          {controller.runView.snapshot !== null ? (
            <span className="agt-pill agt-pill--muted">{controller.runView.snapshot.run_id}</span>
          ) : null}
        </div>
        {currentState !== null ? (
          <div className="agt-key-value">
            <span>Request ID</span>
            <span>{currentState.request_id}</span>
            <span>Thread ID</span>
            <span>{currentState.thread_id}</span>
            <span>Decision</span>
            <span>{currentState.decision}</span>
            <span>Collection</span>
            <span>{currentState.collection_name ?? "Inbox"}</span>
          </div>
        ) : (
          <p className="agt-empty-state">Search state appears here after the first backend round-trip.</p>
        )}
        {controller.sourceBuckets !== null ? (
          <>
            <div className="agt-chip-list">
              {controller.sourceBuckets.used.map((source) => (
                <span className="agt-chip agt-chip--ok" key={`used-${source}`}>
                  used: {source}
                </span>
              ))}
              {controller.sourceBuckets.failed.map((source) => (
                <span className="agt-chip agt-chip--danger" key={`failed-${source}`}>
                  failed: {source}
                </span>
              ))}
              {controller.sourceBuckets.skipped.map((source) => (
                <span className="agt-chip agt-chip--warn" key={`skipped-${source}`}>
                  skipped: {source}
                </span>
              ))}
              {controller.sourceBuckets.unavailable_optional.map((source) => (
                <span className="agt-chip" key={`missing-${source}`}>
                  optional key missing: {source}
                </span>
              ))}
            </div>
            <p className="agt-summary-copy">
              Sources used, failed, skipped, and unavailable optional providers are derived from the backend search metadata and source policy.
            </p>
          </>
        ) : null}
        {currentState !== null ? (
          <div className="agt-card">
            <div className="agt-section-heading">
              <h3>Approval</h3>
            </div>
            <div className="agt-action-cluster">
              <button
                className="agt-button agt-button--warn"
                disabled={!controller.canApprove || controller.runView.phase === "resuming"}
                onClick={controller.onApprove}
                type="button"
              >
                {controller.runView.phase === "resuming" ? "Applying..." : "Approve Selected"}
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
        <div className="agt-card">
          <div className="agt-section-heading">
            <h3>Write Result</h3>
          </div>
          {renderWriteResult(currentState?.write_result ?? null)}
        </div>
      </section>
    </div>
  );
}
