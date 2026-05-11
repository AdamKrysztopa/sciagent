import type { DoctorReport } from "../../shared/contracts";

interface LibraryDoctorProps {
  collectionName: string;
  onScan(): void;
  scanning: boolean;
  report: DoctorReport | null;
  error: string | null;
}

export function LibraryDoctor({
  collectionName,
  error,
  onScan,
  report,
  scanning,
}: LibraryDoctorProps) {
  return (
    <section className="agt-card agt-card--soft">
      <div className="agt-section-heading">
        <h2>Library Doctor</h2>
        <button
          className="agt-button agt-button--ghost"
          disabled={scanning || collectionName.trim().length === 0}
          onClick={onScan}
          type="button"
        >
          {scanning ? "Scanning…" : "Scan"}
        </button>
      </div>
      {error !== null ? (
        <div className="agt-error">{error}</div>
      ) : null}
      {report !== null ? (
        <div>
          <p className="agt-small-note">
            {report.total_items} items — {report.issues.length} with issues,{" "}
            {report.duplicate_pairs.length} duplicates
          </p>
          {report.issues.length === 0 && report.duplicate_pairs.length === 0 ? (
            <p className="agt-empty-state">No issues found.</p>
          ) : (
            <>
              {report.issues.length > 0 ? (
                <ul className="agt-source-list">
                  {report.issues.map((issue) => (
                    <li className="agt-source-item" key={issue.item_key}>
                      <span className="agt-source-name">{issue.title}</span>
                      <span className="agt-chip-list">
                        {issue.issue_types.map((type) => (
                          <span className="agt-source-chip" key={type}>{type}</span>
                        ))}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {report.duplicate_pairs.length > 0 ? (
                <ul className="agt-source-list">
                  {report.duplicate_pairs.map(([keyA, keyB]) => (
                    <li className="agt-source-item" key={`${keyA}-${keyB}`}>
                      <span className="agt-source-chip">Duplicate item pair detected (keys: {keyA} ↔ {keyB})</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
