import type { NormalizedPaper } from "../../shared/contracts";
import { getPaperIndex } from "../../shared/contracts";

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
                  </span>
                </label>
                <span className="agt-pill agt-pill--muted">{paper.source}</span>
              </div>
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
                <p className="agt-result-authors">{paper.authors.join(", ")}</p>
              ) : null}
              {paper.venue !== null ? (
                <p className="agt-result-venue">
                  {paper.venue}
                  {paper.volume !== null ? `, vol. ${paper.volume}` : null}
                  {paper.issue !== null ? ` no. ${paper.issue}` : null}
                  {paper.pages !== null ? `, pp. ${paper.pages}` : null}
                </p>
              ) : null}
              {paper.abstract !== null ? (
                <p className="agt-result-abstract">{paper.abstract}</p>
              ) : null}
              <div className="agt-result-meta">
                {paper.year !== null ? <span>Year: {paper.year}</span> : null}
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

