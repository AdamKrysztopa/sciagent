import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { ProviderInfo, SourceTerminalState } from "../../shared/contracts";
import {
  BYOK_HINTS,
  DepthPlanPreview,
  SearchCoveragePanel,
  getByokHint,
  getDepthProviders,
  shouldShowBaselineBadge,
  shouldShowByokChip,
} from "./SearchCoveragePanel";

describe("BYOK_HINTS", () => {
  it("contains the correct hint for semantic_scholar", () => {
    expect(BYOK_HINTS.semantic_scholar).toBe(
      "Add AGT_SEMANTIC_SCHOLAR_API_KEY to remove rate limits.",
    );
  });

  it("contains the correct hint for core", () => {
    expect(BYOK_HINTS.core).toBe(
      "Add AGT_CORE_API_KEY to unlock CORE full-text indexing.",
    );
  });

  it("contains the correct hint for dimensions", () => {
    expect(BYOK_HINTS.dimensions).toBe(
      "Add AGT_DIMENSIONS_KEY to unlock Dimensions metadata.",
    );
  });

  it("contains the correct hint for google_scholar", () => {
    expect(BYOK_HINTS.google_scholar).toBe(
      "Add AGT_SERPAPI_KEY to unlock Google Scholar via SerpAPI.",
    );
  });
});

describe("getByokHint", () => {
  it("returns the known hint string for semantic_scholar", () => {
    expect(getByokHint("semantic_scholar")).toBe(
      "Add AGT_SEMANTIC_SCHOLAR_API_KEY to remove rate limits.",
    );
  });

  it("returns the known hint string for core", () => {
    expect(getByokHint("core")).toBe(
      "Add AGT_CORE_API_KEY to unlock CORE full-text indexing.",
    );
  });

  it("returns the known hint string for dimensions", () => {
    expect(getByokHint("dimensions")).toBe(
      "Add AGT_DIMENSIONS_KEY to unlock Dimensions metadata.",
    );
  });

  it("returns the known hint string for google_scholar", () => {
    expect(getByokHint("google_scholar")).toBe(
      "Add AGT_SERPAPI_KEY to unlock Google Scholar via SerpAPI.",
    );
  });

  it("returns the fallback hint for an unknown provider", () => {
    expect(getByokHint("openalex")).toBe("Add the provider API key to unlock.");
  });

  it("returns the fallback hint for an empty string source", () => {
    expect(getByokHint("")).toBe("Add the provider API key to unlock.");
  });

  it("returns a non-empty string for every known BYOK provider", () => {
    for (const [source, hint] of Object.entries(BYOK_HINTS)) {
      expect(hint.length).toBeGreaterThan(0);
      expect(getByokHint(source)).toBe(hint);
    }
  });
});

describe("shouldShowByokChip", () => {
  it("returns true for skipped_no_key — chip is rendered for this state", () => {
    expect(shouldShowByokChip("skipped_no_key")).toBe(true);
  });

  it("returns false for queried — chip is NOT rendered", () => {
    expect(shouldShowByokChip("queried")).toBe(false);
  });

  it("returns false for failed — chip is NOT rendered", () => {
    expect(shouldShowByokChip("failed")).toBe(false);
  });

  it("returns false for rate_limited — chip is NOT rendered", () => {
    expect(shouldShowByokChip("rate_limited")).toBe(false);
  });

  it("returns false for zero_results — chip is NOT rendered", () => {
    expect(shouldShowByokChip("zero_results")).toBe(false);
  });

  it("returns false for skipped_disabled — chip is NOT rendered", () => {
    expect(shouldShowByokChip("skipped_disabled")).toBe(false);
  });

  it("covers all SourceTerminalState variants exactly once", () => {
    const allStates: SourceTerminalState[] = [
      "queried",
      "skipped_no_key",
      "skipped_disabled",
      "rate_limited",
      "zero_results",
      "failed",
    ];
    const chipped = allStates.filter(shouldShowByokChip);
    expect(chipped).toEqual(["skipped_no_key"]);
  });
});

describe("shouldShowBaselineBadge", () => {
  it("returns true when baselineMode is true", () => {
    expect(shouldShowBaselineBadge(true)).toBe(true);
  });

  it("returns false when baselineMode is false", () => {
    expect(shouldShowBaselineBadge(false)).toBe(false);
  });

  it("returns false when baselineMode is undefined", () => {
    expect(shouldShowBaselineBadge(undefined)).toBe(false);
  });

  it("returns false when called with no argument", () => {
    expect(shouldShowBaselineBadge()).toBe(false);
  });
});

describe("getDepthProviders", () => {
  it("quick returns openalex and arxiv but not crossref", () => {
    const providers = getDepthProviders("quick");
    expect(providers).toContain("openalex");
    expect(providers).toContain("arxiv");
    expect(providers).not.toContain("crossref");
  });

  it("balanced returns all 6 baseline providers", () => {
    const providers = getDepthProviders("balanced");
    for (const p of ["openalex", "crossref", "europe_pmc", "doaj", "pubmed", "arxiv"]) {
      expect(providers).toContain(p);
    }
    expect(providers).toHaveLength(6);
  });

  it("deep is a superset of the balanced set", () => {
    const balanced = getDepthProviders("balanced");
    const deep = getDepthProviders("deep");
    for (const p of balanced) {
      expect(deep).toContain(p);
    }
    expect(deep.length).toBeGreaterThan(balanced.length);
  });

  it("null falls back to balanced set", () => {
    expect(getDepthProviders(null)).toEqual(getDepthProviders("balanced"));
  });

  it("unknown string falls back to balanced set", () => {
    expect(getDepthProviders("unknown")).toEqual(getDepthProviders("balanced"));
  });
});

describe("DepthPlanPreview", () => {
  it("renders the depth label and provider names", () => {
    const html = renderToStaticMarkup(createElement(DepthPlanPreview, { depth: "quick" }));
    expect(html).toContain("Quick mode");
    expect(html).toContain("2 sources");
    expect(html).toContain("openalex");
    expect(html).toContain("arxiv");
  });

  it("falls back to balanced label when depth is null", () => {
    const html = renderToStaticMarkup(createElement(DepthPlanPreview, { depth: null }));
    expect(html).toContain("Balanced mode");
    expect(html).toContain("6 sources");
  });
});

function makeProvider(overrides: Partial<ProviderInfo> = {}): ProviderInfo {
  return {
    name: "openalex",
    requires_key: false,
    key_env_var: null,
    key_upgrade_hint: null,
    fields: { title: "full", abstract: "full" },
    notes: "OpenAlex is free and open.",
    health: {
      status: "available",
      reason: "",
      last_ok_at: null,
      last_error_at: null,
      consecutive_failures: 0,
      retry_after: null,
    },
    ...overrides,
  };
}

describe("SearchCoveragePanel providers rendering (P8.7-D)", () => {
  it("renders both provider names when providers map has 2 entries", () => {
    const providers: Record<string, ProviderInfo> = {
      openalex: makeProvider({ name: "openalex" }),
      crossref: makeProvider({ name: "crossref" }),
    };
    const html = renderToStaticMarkup(
      createElement(SearchCoveragePanel, {
        sourceStates: { openalex: "queried" },
        providers,
      }),
    );
    expect(html).toContain("openalex");
    expect(html).toContain("crossref");
  });

  it("applies agt-chip--muted class when provider requires_key is true", () => {
    const providers: Record<string, ProviderInfo> = {
      dimensions: makeProvider({ name: "dimensions", requires_key: true }),
    };
    const html = renderToStaticMarkup(
      createElement(SearchCoveragePanel, {
        sourceStates: { openalex: "queried" },
        providers,
      }),
    );
    expect(html).toContain("agt-chip--muted");
    expect(html).toContain("dimensions");
  });
});
