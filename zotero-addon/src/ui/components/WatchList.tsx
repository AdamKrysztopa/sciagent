import type { Watch, WatchRerunResponse } from "../../shared/contracts";

interface WatchListProps {
  watches: Watch[];
  loading: boolean;
  error: string | null;
  // Save-as-watch inputs
  watchName: string;
  canSave: boolean;
  saving: boolean;
  saveError: string | null;
  onWatchNameChange(name: string): void;
  onSaveWatch(): void;
  // Per-watch actions
  onRerun(watchId: string): void;
  onDelete(watchId: string): void;
  rerunningId: string | null;
  lastRerun: WatchRerunResponse | null;
}

function formatDate(iso: string | null): string {
  if (iso === null) return "never";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function WatchList({
  canSave,
  error,
  lastRerun,
  loading,
  onDelete,
  onRerun,
  onSaveWatch,
  onWatchNameChange,
  rerunningId,
  saveError,
  saving,
  watchName,
  watches,
}: WatchListProps) {
  return (
    <section className="agt-card agt-card--soft">
      <div className="agt-section-heading">
        <h2>Watch List</h2>
        {loading ? <span className="agt-pill agt-pill--muted">loading…</span> : null}
      </div>

      <p className="agt-small-note">
        Save a search as a watch to quickly rerun it and see new papers.
      </p>

      {/* Save-as-watch form */}
      <div className="agt-watch-save-row">
        <input
          className="agt-input"
          disabled={!canSave || saving}
          onChange={(e) => onWatchNameChange(e.target.value)}
          placeholder="Watch name"
          type="text"
          value={watchName}
        />
        <button
          className="agt-button agt-button--ghost agt-button--sm"
          disabled={!canSave || saving || watchName.trim().length === 0}
          onClick={onSaveWatch}
          title={canSave ? "Save current query as a watch" : "Enter a query first"}
          type="button"
        >
          {saving ? "Saving…" : "Save Watch"}
        </button>
      </div>
      {saveError !== null ? (
        <span className="agt-small-note agt-small-note--error">{saveError}</span>
      ) : null}

      {error !== null ? <div className="agt-error">{error}</div> : null}

      {lastRerun !== null ? (
        <div className="agt-watch-rerun-banner">
          <span className="agt-chip agt-chip--ok">
            {lastRerun.new_count} new of {lastRerun.total_count}
          </span>
          <span className="agt-small-note"> — rerun complete; results loaded above</span>
        </div>
      ) : null}

      {watches.length === 0 && !loading ? (
        <p className="agt-empty-state">No watches saved yet.</p>
      ) : (
        <ul className="agt-source-list">
          {watches.map((watch) => (
            <li className="agt-source-item agt-watch-item" key={watch.id}>
              <div className="agt-watch-meta">
                <span className="agt-source-name">{watch.name}</span>
                <span className="agt-small-note agt-watch-query">{watch.query}</span>
                <span className="agt-small-note">
                  Last run: {formatDate(watch.last_run_at)} · {watch.seen_count} seen
                </span>
              </div>
              <div className="agt-watch-actions">
                <button
                  className="agt-button agt-button--ghost agt-button--sm"
                  disabled={rerunningId !== null}
                  onClick={() => onRerun(watch.id)}
                  title="Rerun this watch and see new papers"
                  type="button"
                >
                  {rerunningId === watch.id ? "Running…" : "Rerun"}
                </button>
                <button
                  className="agt-button agt-button--danger agt-button--sm"
                  disabled={rerunningId !== null}
                  onClick={() => onDelete(watch.id)}
                  title="Delete this watch"
                  type="button"
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
