import type { ProviderInfo, SourceTerminalState } from "../../shared/contracts";
import type React from "react";
import { useState } from "react";

export const BYOK_HINTS: Record<string, string> = {
  semantic_scholar: "Add AGT_SEMANTIC_SCHOLAR_API_KEY to remove rate limits.",
  core: "Add AGT_CORE_API_KEY to unlock CORE full-text indexing.",
  dimensions: "Add AGT_DIMENSIONS_KEY to unlock Dimensions metadata.",
  google_scholar: "Add AGT_SERPAPI_KEY to unlock Google Scholar via SerpAPI.",
};

const BYOK_HINT_FALLBACK = "Add the provider API key to unlock.";

export function getByokHint(source: string): string {
  return BYOK_HINTS[source] ?? BYOK_HINT_FALLBACK;
}

export function shouldShowByokChip(state: SourceTerminalState): boolean {
  return state === "skipped_no_key";
}

export function shouldShowBaselineBadge(baselineMode?: boolean): boolean {
  return baselineMode === true;
}

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
  baselineMode?: boolean;
  providers?: Record<string, ProviderInfo>;
}

export function SearchCoveragePanel({ sourceStates, baselineMode, providers }: SearchCoveragePanelProps) {
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
        {shouldShowBaselineBadge(baselineMode) ? (
          <span className="agt-chip agt-chip--muted">Baseline (6 sources)</span>
        ) : null}
        <span className="agt-expand-icon">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded ? (
        <div className="agt-coverage-grid">
          {entries.map(([source, state]) => (
            <div className="agt-coverage-row" key={source}>
              <span className="agt-coverage-name">{SOURCE_LABELS[source] ?? source}</span>
              <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                <span className={`agt-chip ${STATE_CHIP_CLASS[state]}`}>{STATE_LABEL[state]}</span>
                {shouldShowByokChip(state) ? (
                  <span
                    className="agt-chip agt-chip--muted"
                    title={getByokHint(source)}
                  >
                    API key optional
                  </span>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {providers != null && Object.keys(providers).length > 0 ? (
        <div className="agt-provider-caps">
          <h3 className="agt-subsection-heading">Provider Capabilities</h3>
          <div className="agt-chip-list">
            {Object.entries(providers).map(([name, info]) => (
              <span
                className={`agt-chip ${info.requires_key ? "agt-chip--muted" : ""}`}
                key={name}
                title={info.notes + (info.key_upgrade_hint != null ? ` ${info.key_upgrade_hint}` : "")}
              >
                {name}{info.requires_key ? " 🔑" : ""}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

const DEPTH_PROVIDER_SETS: Record<string, readonly string[]> = {
  quick: ["openalex", "arxiv"],
  balanced: ["openalex", "crossref", "europe_pmc", "doaj", "pubmed", "arxiv"],
  deep: [
    "openalex", "crossref", "europe_pmc", "doaj", "pubmed", "arxiv",
    "semantic_scholar", "core", "base", "opencitations",
  ],
} as const;

export function getDepthProviders(depth: string | null | undefined): readonly string[] {
  if (depth !== null && depth !== undefined && depth in DEPTH_PROVIDER_SETS) {
    return DEPTH_PROVIDER_SETS[depth];
  }
  return DEPTH_PROVIDER_SETS.balanced;
}

interface DepthPlanPreviewProps {
  depth: string | null | undefined;
}

export function DepthPlanPreview({ depth }: DepthPlanPreviewProps): React.JSX.Element {
  const providers = getDepthProviders(depth);
  const label = depth ?? "balanced";
  return (
    <div className="agt-depth-plan">
      <span className="agt-depth-plan__label">
        {label.charAt(0).toUpperCase() + label.slice(1)} mode ({providers.length} sources):
      </span>
      <span className="agt-depth-plan__providers">
        {providers.join(", ")}
      </span>
    </div>
  );
}
