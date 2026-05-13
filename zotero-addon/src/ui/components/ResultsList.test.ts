import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { NormalizedAuthor, NormalizedPaper } from "../../shared/contracts";
import { getMissingHintTitle, ResultsList } from "./ResultsList";

function makePaper(overrides: Partial<NormalizedPaper> = {}): NormalizedPaper {
  return {
    title: "Test Paper",
    year: 2024,
    doi: null,
    arxiv_id: null,
    abstract: null,
    authors: [],
    url: null,
    pdf_url: null,
    source: "openalex",
    index: 1,
    semantic_score: 0.5,
    citation_count: 0,
    influential_citation_count: 0,
    open_access: false,
    summary: null,
    score: 0.5,
    explanation: null,
    venue: null,
    item_type: null,
    volume: null,
    issue: null,
    pages: null,
    ...overrides,
  };
}

function renderList(papers: NormalizedPaper[]): string {
  return renderToStaticMarkup(
    createElement(ResultsList, {
      papers,
      selectedIndices: [],
      disabled: false,
      onToggle: () => {},
    }),
  );
}

describe("getMissingHintTitle", () => {
  it("returns the human-readable label for a known reason code", () => {
    const result = getMissingHintTitle({ abstract: "provider_did_not_return" }, "abstract");
    expect(result).toBe("Provider was queried but did not return this field");
  });

  it("returns a string containing 'key-gated' for missing_key reason", () => {
    const result = getMissingHintTitle({ abstract: "missing_key" }, "abstract");
    expect(result).toContain("key-gated");
  });

  it("returns null when reasons is undefined", () => {
    expect(getMissingHintTitle(undefined, "abstract")).toBeNull();
  });

  it("returns null when the field is not present in reasons", () => {
    expect(getMissingHintTitle({}, "abstract")).toBeNull();
  });

  it("falls back to the raw reason code for an unknown code", () => {
    const result = getMissingHintTitle({ doi: "some_unknown_code" }, "doi");
    expect(result).toBe("some_unknown_code");
  });
});

describe("ResultsList missing_reasons rendering", () => {
  it("renders ℹ span with correct title when abstract is null and missing_reasons has abstract", () => {
    const paper = makePaper({
      abstract: null,
      missing_reasons: { abstract: "provider_did_not_return" },
    });
    const html = renderList([paper]);
    expect(html).toContain("agt-missing-hint");
    expect(html).toContain("Provider was queried but did not return this field");
  });

  it("renders title containing 'key-gated' for missing_key reason on abstract", () => {
    const paper = makePaper({
      abstract: null,
      missing_reasons: { abstract: "missing_key" },
    });
    const html = renderList([paper]);
    expect(html).toContain("agt-missing-hint");
    expect(html).toContain("key-gated");
  });

  it("does not render ℹ span when missing_reasons is absent and abstract is null", () => {
    const paper = makePaper({ abstract: null });
    const html = renderList([paper]);
    expect(html).not.toContain("agt-missing-hint");
  });

  it("renders abstract text and does not render ℹ span when abstract is present", () => {
    const paper = makePaper({
      abstract: "Introduction to quantum computing",
      missing_reasons: { abstract: "provider_did_not_return" },
    });
    const html = renderList([paper]);
    expect(html).toContain("Introduction to quantum computing");
    expect(html).not.toContain("agt-missing-hint");
  });
});

function makeAuthor(overrides: Partial<NormalizedAuthor> = {}): NormalizedAuthor {
  return {
    name: "Test Author",
    family: null,
    given: null,
    orcid: null,
    openalex_id: null,
    s2_author_id: null,
    affiliation: null,
    source: "openalex",
    ...overrides,
  };
}

describe("ResultsList author rendering", () => {
  it("renders plain string author as text (backward compat)", () => {
    const paper = makePaper({ authors: ["Plain String Author"] });
    const html = renderList([paper]);
    expect(html).toContain("Plain String Author");
    expect(html).not.toContain("agt-author-chip");
  });

  it("renders NormalizedAuthor with openalex_id as a link to openalex.org", () => {
    const paper = makePaper({
      authors: [makeAuthor({ name: "Alice Smith", openalex_id: "A123" })],
    });
    const html = renderList([paper]);
    expect(html).toContain("Alice Smith");
    expect(html).toContain("agt-author-chip");
    expect(html).toContain("openalex.org/authors/A123");
  });

  it("renders NormalizedAuthor with orcid (no openalex_id) as a link to orcid.org", () => {
    const paper = makePaper({
      authors: [makeAuthor({ name: "Bob Jones", openalex_id: null, orcid: "0000-0001-2345-6789", source: "crossref" })],
    });
    const html = renderList([paper]);
    expect(html).toContain("Bob Jones");
    expect(html).toContain("agt-author-chip");
    expect(html).toContain("orcid.org/0000-0001-2345-6789");
  });

  it("renders NormalizedAuthor with no IDs as plain text (no link)", () => {
    const paper = makePaper({
      authors: [makeAuthor({ name: "Bob Jones", openalex_id: null, orcid: null, source: "crossref" })],
    });
    const html = renderList([paper]);
    expect(html).toContain("Bob Jones");
    expect(html).not.toContain("agt-author-chip");
  });
});

describe("ResultsList source chips (P8.7-B)", () => {
  it("renders source chips when paper has multiple sources", () => {
    const paper = makePaper({ sources: ["openalex", "crossref"] });
    const html = renderList([paper]);
    expect(html).toContain("agt-source-chips");
    expect(html).toContain("openalex");
    expect(html).toContain("crossref");
  });

  it("does not render source chips section when paper has a single source", () => {
    const paper = makePaper({ sources: ["openalex"] });
    const html = renderList([paper]);
    expect(html).not.toContain("agt-source-chips");
  });

  it("does not render source chips section when sources is undefined", () => {
    const paper = makePaper({});
    const html = renderList([paper]);
    expect(html).not.toContain("agt-source-chips");
  });
});

describe("ResultsList conflict dot (P8.7-C)", () => {
  it("renders conflict dot when paper has conflicts", () => {
    const paper = makePaper({
      conflicts: [
        {
          field: "year",
          values: [
            { provider: "crossref", value: 2021 },
            { provider: "openalex", value: 2022 },
          ],
        },
      ],
    });
    const html = renderList([paper]);
    expect(html).toContain("agt-conflict-dot");
    expect(html).toContain("1 field conflict");
  });

  it("does not render conflict dot when paper has empty conflicts array", () => {
    const paper = makePaper({ conflicts: [] });
    const html = renderList([paper]);
    expect(html).not.toContain("agt-conflict-dot");
  });

  it("does not render conflict dot when conflicts is undefined", () => {
    const paper = makePaper({});
    const html = renderList([paper]);
    expect(html).not.toContain("agt-conflict-dot");
  });
});

describe("ResultsList citation badge (P8.9-C)", () => {
  it("renders ↓ ref badge with aria-label when citation_relation is 'references'", () => {
    const paper = makePaper({ citation_relation: "references" });
    const html = renderList([paper]);
    expect(html).toContain("↓ ref");
    expect(html).toContain("aria-label=\"cited by seed\"");
    expect(html).toContain("agt-citation-badge--references");
  });

  it("renders ↑ cites badge with aria-label when citation_relation is 'cited_by'", () => {
    const paper = makePaper({ citation_relation: "cited_by" });
    const html = renderList([paper]);
    expect(html).toContain("↑ cites");
    expect(html).toContain("aria-label=\"cites seed\"");
    expect(html).toContain("agt-citation-badge--cited-by");
  });

  it("renders no citation badge when citation_relation is null", () => {
    const paper = makePaper({ citation_relation: null });
    const html = renderList([paper]);
    expect(html).not.toContain("agt-citation-badge");
  });

  it("renders no citation badge when citation_relation is absent", () => {
    const paper = makePaper({});
    const html = renderList([paper]);
    expect(html).not.toContain("agt-citation-badge");
  });
});
