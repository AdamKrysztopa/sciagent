import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { buildDefaultFilterEdit, type FilterEditContract, type NormalizedAuthor, type ResolvedVenue } from "../../shared/contracts";
import { FilterEditor } from "./FilterEditor";

const BASE_FILTER = buildDefaultFilterEdit();

function renderEditor(
  overrides: Partial<{
    filterDraft: FilterEditContract | null;
    onSuggestAuthors: (q: string) => Promise<NormalizedAuthor[]>;
    onSuggestVenues: (q: string) => Promise<ResolvedVenue[]>;
    disabled: boolean;
  }> = {},
): string {
  const filterDraft = "filterDraft" in overrides ? overrides.filterDraft ?? null : BASE_FILTER;
  return renderToStaticMarkup(
    createElement(FilterEditor, {
      disabled: overrides.disabled ?? false,
      filterDraft,
      onChange: vi.fn(),
      onReset: vi.fn(),
      onSuggestAuthors: overrides.onSuggestAuthors,
      onSuggestVenues: overrides.onSuggestVenues,
      searchPlan: null,
    }),
  );
}

describe("FilterEditor Seed Papers section (P9.10)", () => {
  it("renders Seed Papers textarea", () => {
    const html = renderEditor();
    expect(html).toContain("Seed Papers (DOI, one per line)");
    expect(html).toContain("agt-textarea");
    expect(html).toContain("10.1038/nature12373");
  });

  it("renders seed DOI values in textarea", () => {
    const filterWithDois: FilterEditContract = {
      ...BASE_FILTER,
      seed_dois: ["10.1038/nature12373", "10.1126/science.1234567"],
    };
    const html = renderEditor({ filterDraft: filterWithDois });
    expect(html).toContain("10.1038/nature12373");
    expect(html).toContain("10.1126/science.1234567");
  });

  it("renders hint text for seed DOIs", () => {
    const html = renderEditor();
    expect(html).toContain("Papers whose citation graph to include");
  });

  it("renders seed DOIs textarea when filterDraft has empty seed_dois", () => {
    const filterEmpty: FilterEditContract = { ...BASE_FILTER, seed_dois: [] };
    const html = renderEditor({ filterDraft: filterEmpty });
    expect(html).toContain("Seed Papers (DOI, one per line)");
  });
});

describe("FilterEditor Author section (P9.8)", () => {
  it("renders Author Filter field when onSuggestAuthors is provided", () => {
    const html = renderEditor({ onSuggestAuthors: vi.fn().mockResolvedValue([]) });
    expect(html).toContain("Author Filter");
  });

  it("does not render Author Filter when onSuggestAuthors is omitted", () => {
    const html = renderEditor();
    expect(html).not.toContain("Author Filter");
  });

  it("renders the author text input when suggest is provided", () => {
    const html = renderEditor({ onSuggestAuthors: vi.fn().mockResolvedValue([]) });
    expect(html).toContain("agt-author-input");
    expect(html).toContain("agt-suggest-wrap");
    expect(html).toContain('placeholder="Type author name…"');
  });

  it("renders existing author chips", () => {
    const filterWithAuthor: FilterEditContract = {
      ...BASE_FILTER,
      authors: [{ name: "Jane Doe", openalex_id: "A123", orcid: null, s2_author_id: null }],
    };
    const html = renderEditor({
      filterDraft: filterWithAuthor,
      onSuggestAuthors: vi.fn().mockResolvedValue([]),
    });
    expect(html).toContain("Jane Doe");
    expect(html).toContain("agt-chip--removable");
    expect(html).toContain("agt-chip-remove");
  });

  it("renders OA badge for author with openalex_id", () => {
    const filterWithAuthor: FilterEditContract = {
      ...BASE_FILTER,
      authors: [{ name: "Jane Doe", openalex_id: "A123", orcid: null, s2_author_id: null }],
    };
    const html = renderEditor({
      filterDraft: filterWithAuthor,
      onSuggestAuthors: vi.fn().mockResolvedValue([]),
    });
    expect(html).toContain("OA");
  });

  it("renders ORC badge for author with orcid", () => {
    const filterWithAuthor: FilterEditContract = {
      ...BASE_FILTER,
      authors: [{ name: "Jane Doe", openalex_id: null, orcid: "0000-0001-2345-6789", s2_author_id: null }],
    };
    const html = renderEditor({
      filterDraft: filterWithAuthor,
      onSuggestAuthors: vi.fn().mockResolvedValue([]),
    });
    expect(html).toContain("ORC");
  });

  it("renders no chips when authors array is empty", () => {
    const html = renderEditor({ onSuggestAuthors: vi.fn().mockResolvedValue([]) });
    expect(html).not.toContain("agt-chip--removable");
  });

  it("renders loading state: null filterDraft shows empty state", () => {
    const html = renderEditor({ filterDraft: null });
    expect(html).toContain("Pre-Search Filters");
    expect(html).toContain("Loading saved filter defaults…");
  });

  it("renders standard filter fields alongside author section", () => {
    const html = renderEditor({ onSuggestAuthors: vi.fn().mockResolvedValue([]) });
    expect(html).toContain("Result Limit");
    expect(html).toContain("Min Year");
    expect(html).toContain("Author Filter");
  });
});

describe("FilterEditor Venue section (P9.9)", () => {
  it("renders Venue / Journal Filter field when onSuggestVenues is provided", () => {
    const html = renderEditor({ onSuggestVenues: vi.fn().mockResolvedValue([]) });
    expect(html).toContain("Venue / Journal Filter");
  });

  it("does not render Venue filter when onSuggestVenues is omitted", () => {
    const html = renderEditor();
    expect(html).not.toContain("Venue / Journal Filter");
  });

  it("renders existing venue chips", () => {
    const filterWithVenue: FilterEditContract = {
      ...BASE_FILTER,
      venues: [{ name: "Nature", openalex_id: "S137773608", issn: "1476-4687" }],
    };
    const html = renderEditor({
      filterDraft: filterWithVenue,
      onSuggestVenues: vi.fn().mockResolvedValue([]),
    });
    expect(html).toContain("Nature");
    expect(html).toContain("agt-chip--removable");
    expect(html).toContain("agt-chip-remove");
  });

  it("renders OA badge for venue with openalex_id", () => {
    const filterWithVenue: FilterEditContract = {
      ...BASE_FILTER,
      venues: [{ name: "Nature", openalex_id: "S137773608", issn: null }],
    };
    const html = renderEditor({
      filterDraft: filterWithVenue,
      onSuggestVenues: vi.fn().mockResolvedValue([]),
    });
    expect(html).toContain("OA");
  });
});
