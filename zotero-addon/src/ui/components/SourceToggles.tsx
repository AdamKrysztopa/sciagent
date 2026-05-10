import type { SourceCapability } from "../../shared/contracts";

export interface SourceTogglesProps {
  /** Source capabilities from backend /capabilities — empty until first health check. */
  sourcePolicy: SourceCapability[];
}

const TIER_LABEL: Record<string, string> = {
  primary: "Primary",
  fallback: "Fallback",
};

export function SourceToggles({ sourcePolicy }: SourceTogglesProps) {
  if (sourcePolicy.length === 0) {
    return null;
  }

  return (
    <section className="agt-source-toggles" aria-label="Source availability">
      <h4 className="agt-section-heading">Available Sources</h4>
      <ul className="agt-source-list" role="list">
        {sourcePolicy.map((src) => (
          <li key={src.name} className={`agt-source-item agt-source-${src.tier}`}>
            <span className="agt-source-name">{src.name}</span>
            <span className="agt-source-tier" aria-label={`tier: ${src.tier}`}>
              {TIER_LABEL[src.tier] ?? src.tier}
            </span>
            {src.supports_year_filter && (
              <span className="agt-source-chip" title="Supports year filter">
                year
              </span>
            )}
            {src.supports_open_access_filter && (
              <span className="agt-source-chip" title="Supports open access filter">
                OA
              </span>
            )}
            <span
              className={`agt-source-status agt-source-status-${src.enabled ? "enabled" : "disabled"}`}
              aria-label={src.enabled ? "enabled" : "disabled"}
            >
              {src.enabled ? "✓" : "✗"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
