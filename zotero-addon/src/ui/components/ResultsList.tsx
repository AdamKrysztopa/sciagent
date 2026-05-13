import type { NormalizedPaper } from "../../shared/contracts";
import { getAuthorName, getPaperIndex } from "../../shared/contracts";

const MISSING_REASON_LABELS: Record<string, string> = {
  provider_did_not_return: "Provider was queried but did not return this field",
  not_supported_by_any_queried_provider: "No queried provider supports this field",
  missing_key: "Only key-gated providers support this field; add a key to unlock",
  provider_failed: "A capable provider failed or was rate-limited",
  not_requested_at_depth: "Not fetched at the current search depth",
};

export function getMissingHintTitle(
  reasons: Record<string, string> | undefined,
  field: string,
): string | null {
  if (reasons === undefined) return null;
  const code = reasons[field];
  if (code === undefined) return null;
  return MISSING_REASON_LABELS[code] ?? code;
}

interface ResultsListProps {
  disabled: boolean;
  onToggle(index: number): void;
  papers: NormalizedPaper[];
  selectedIndices: number[];
}

export function ResultsList({ disabled, onToggle, papers, selectedIndices }: ResultsListProps) {
  if (papers.length === 0) {
    return (
      <section className="agt-card agt-card--soft">
        <div className="agt-section-heading">
          <h2>Results</h2>
        </div>
        <p className="agt-empty-state">No candidate list loaded yet.</p>
      </section>
    );
  }

  const selected = new Set(selectedIndices);

  return (
    <section className="agt-card">
      <div className="agt-section-heading">
        <h2>Results</h2>
        <span className="agt-pill agt-pill--muted">{papers.length} papers</span>
      </div>
      <div className="agt-result-list">
        {papers.map((paper, fallbackIndex) => {
          const paperIndex = getPaperIndex(paper, fallbackIndex);
          const scorePercent = Math.min(1, Math.max(0, paper.score)) * 100;
          const abstractHint = getMissingHintTitle(paper.missing_reasons, "abstract");
          const venueHint = getMissingHintTitle(paper.missing_reasons, "venue");
          const doiHint = getMissingHintTitle(paper.missing_reasons, "doi");
          const yearHint = getMissingHintTitle(paper.missing_reasons, "year");
          return (
            <article className="agt-result-card" key={paperIndex}>
              <div className="agt-result-header">
                <label className="agt-checkbox-row">
                  <input
                    checked={selected.has(paperIndex)}
                    disabled={disabled}
                    onChange={() => onToggle(paperIndex)}
                    type="checkbox"
                  />
                  <span className="agt-result-title">
                    {paperIndex}.{" "}
                    {paper.url !== null ? (
                      <a href={paper.url} rel="noreferrer" target="_blank">{paper.title}</a>
                    ) : (
                      paper.title
                    )}
                    {paper.citation_relation === "references" ? (
                      <span
                        className="agt-citation-badge agt-citation-badge--references"
                        title="This paper is cited by your seed DOI (outgoing reference)"
                        role="img"
                        aria-label="cited by seed"
                      >
                        ↓ ref
                      </span>
                    ) : paper.citation_relation === "cited_by" ? (
                      <span
                        className="agt-citation-badge agt-citation-badge--cited-by"
                        title="This paper cites your seed DOI (incoming citation)"
                        role="img"
                        aria-label="cites seed"
                      >
                        ↑ cites
                      </span>
                    ) : null}
                  </span>
                </label>
                {paper.conflicts != null && paper.conflicts.length > 0 ? (
                  <span
                    className="agt-conflict-dot"
                    title={`${paper.conflicts.length} field conflict${paper.conflicts.length > 1 ? "s" : ""}`}
                    role="img"
                    aria-label={`${paper.conflicts.length} field conflict${paper.conflicts.length > 1 ? "s" : ""}`}
                  >⚠</span>
                ) : null}
                <span className="agt-pill agt-pill--muted">{paper.source}</span>
              </div>
              {paper.sources != null && paper.sources.length > 1 ? (
                <div className="agt-source-chips">
                  {paper.sources.map((src) => (
                    <span className="agt-chip agt-chip--muted" key={src}>{src}</span>
                  ))}
                </div>
              ) : null}
              {paper.library_status != null ? (
                <span className={`agt-lib-badge agt-lib-badge--${paper.library_status}`}>
                  {paper.library_status === "in_library"
                    ? "Already in library"
                    : paper.library_status === "possible_duplicate"
                      ? "Possible duplicate"
                      : "New"}
                </span>
              ) : null}
              {paper.watch_status != null ? (
                <span className={`agt-lib-badge agt-lib-badge--watch-${paper.watch_status}`}>
                  {paper.watch_status === "new" ? "New in watch" : "Previously seen"}
                </span>
              ) : null}
              {paper.authors.length > 0 ? (
                <p className="agt-result-authors">
                  {paper.authors.map((author, i) => {
                    const authorName = getAuthorName(author);
                    const oaId = typeof author !== "string" ? author.openalex_id : null;
                    const orcid = typeof author !== "string" ? author.orcid : null;
                    const href =
                      oaId != null
                        ? `https://openalex.org/authors/${oaId}`
                        : orcid != null
                          ? `https://orcid.org/${orcid}`
                          : null;
                    const authorKey =
                      typeof author === "string"
                        ? author
                        : `${author.name}|${author.openalex_id ?? ""}|${author.orcid ?? ""}`;
                    return (
                      <span key={authorKey}>
                        {i > 0 ? ", " : ""}
                        {href != null ? (
                          <a className="agt-author-chip" href={href} rel="noreferrer" target="_blank">
                            {authorName}
                          </a>
                        ) : (
                          authorName
                        )}
                      </span>
                    );
                  })}
                </p>
              ) : null}
              {paper.venue !== null ? (
                <p className="agt-result-venue">
                  {paper.venue}
                  {paper.volume !== null ? `, vol. ${paper.volume}` : null}
                  {paper.issue !== null ? ` no. ${paper.issue}` : null}
                  {paper.pages !== null ? `, pp. ${paper.pages}` : null}
                </p>
              ) : venueHint !== null ? (
                <span
                  className="agt-missing-hint"
                  role="img"
                  title={venueHint}
                  aria-label={`Venue missing: ${venueHint}`}
                >ℹ</span>
              ) : null}
              {paper.abstract !== null ? (
                <p className="agt-result-abstract">{paper.abstract}</p>
              ) : abstractHint !== null ? (
                <span
                  className="agt-missing-hint"
                  role="img"
                  title={abstractHint}
                  aria-label={`Abstract missing: ${abstractHint}`}
                >ℹ</span>
              ) : null}
              <div className="agt-result-meta">
                {paper.year !== null ? (
                  <span>Year: {paper.year}</span>
                ) : yearHint !== null ? (
                  <span
                    className="agt-missing-hint"
                    role="img"
                    title={yearHint}
                    aria-label={`Year missing: ${yearHint}`}
                  >ℹ</span>
                ) : null}
                <span>Citations: {paper.citation_count}</span>
                {paper.influential_citation_count > 0 ? (
                  <span>{paper.influential_citation_count} influential</span>
                ) : null}
                <span>Score: {paper.score.toFixed(2)}</span>
                {paper.open_access ? <span className="agt-oa-badge">Open Access</span> : null}
                {paper.doi !== null ? (
                  <a
                    className="agt-doi-badge"
                    href={`https://doi.org/${paper.doi}`}
                    rel="noreferrer"
                    target="_blank"
                  >
                    DOI ↗
                  </a>
                ) : doiHint !== null ? (
                  <span
                    className="agt-missing-hint"
                    role="img"
                    title={doiHint}
                    aria-label={`DOI missing: ${doiHint}`}
                  >ℹ</span>
                ) : null}
                {paper.pdf_url !== null ? (
                  <a
                    className="agt-pdf-badge"
                    href={paper.pdf_url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    PDF ↗
                  </a>
                ) : null}
              </div>
              <div className="agt-score-bar">
                <div className="agt-score-fill" style={{ width: `${scorePercent}%` }} />
              </div>
              {paper.explanation !== null ? (
                <p className="agt-result-explanation">{paper.explanation}</p>
              ) : null}
              {paper.summary !== null ? <p className="agt-result-summary">{paper.summary}</p> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

