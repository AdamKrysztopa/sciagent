import { describe, expect, it } from "vitest";

import type { SourceTerminalState } from "../../shared/contracts";
import {
  BYOK_HINTS,
  getByokHint,
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
