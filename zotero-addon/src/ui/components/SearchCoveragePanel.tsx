import type { SourceTerminalState } from "../../shared/contracts";
import { useState } from "react";

const SOURCE_LABELS: Record<string, string> = {
  semantic_scholar: "Semantic Scholar",
  openalex: "OpenAlex",
  crossref: "Crossref",
  pubmed: "PubMed",
  europe_pmc: "Europe PMC",
  arxiv: "arXiv",
  base: "BASE",
  core: "CORE",
  dimensions: "Dimensions",
  google_scholar: "Google Scholar",
  opencitations: "OpenCitations",
};

const STATE_CHIP_CLASS: Record<SourceTerminalState, string> = {
  queried: "agt-chip--ok",
  zero_results: "agt-chip--warn",
  rate_limited: "agt-chip--warn",
  failed: "agt-chip--danger",
  skipped_no_key: "agt-chip",
  skipped_disabled: "agt-chip",
};

const STATE_LABEL: Record<SourceTerminalState, string> = {
  queried: "queried",
  zero_results: "0 results",
  rate_limited: "rate limited",
  failed: "failed",
  skipped_no_key: "no key",
  skipped_disabled: "skipped",
};

interface SearchCoveragePanelProps {
  sourceStates: Record<string, SourceTerminalState>;
}

export function SearchCoveragePanel({ sourceStates }: SearchCoveragePanelProps) {
  const [expanded, setExpanded] = useState(false);
  const entries = Object.entries(sourceStates);
  if (entries.length === 0) return null;

  const queriedCount = entries.filter(([, s]) => s === "queried").length;
  const failedCount = entries.filter(([, s]) => s === "failed" || s === "rate_limited").length;

  return (
    <section className="agt-card agt-card--soft">
      <button
        className="agt-section-heading agt-section-heading--clickable"
        onClick={() => setExpanded((v) => !v)}
        type="button"
      >
        <h2>Search Coverage</h2>
        <span className="agt-pill agt-pill--muted">
          {queriedCount}/{entries.length}
          {failedCount > 0 ? ` · ${failedCount} failed` : null}
        </span>
        <span className="agt-expand-icon">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded ? (
        <div className="agt-coverage-grid">
          {entries.map(([source, state]) => (
            <div className="agt-coverage-row" key={source}>
              <span className="agt-coverage-name">{SOURCE_LABELS[source] ?? source}</span>
              <span className={`agt-chip ${STATE_CHIP_CLASS[state]}`}>{STATE_LABEL[state]}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
