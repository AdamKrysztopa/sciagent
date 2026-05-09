import { describe, expect, it } from "vitest";

import {
  REQUIRED_API_CONTRACT_VERSION,
  buildDefaultFilterEdit,
  validateContractVersion,
  type HealthResponse,
} from "./contracts";

function makeHealthResponse(overrides?: Partial<HealthResponse>): HealthResponse {
  return {
    api_contract_version: undefined,
    fallback_provider: null,
    message: "ok",
    ok: true,
    preflight: { ok: true },
    provider: "semantic_scholar",
    ...overrides,
  };
}

describe("validateContractVersion", () => {
  it("returns 'compatible' when api_contract_version matches required version", () => {
    const response = makeHealthResponse({ api_contract_version: REQUIRED_API_CONTRACT_VERSION });
    expect(validateContractVersion(response)).toBe("compatible");
  });

  it("returns 'missing' when response is null", () => {
    expect(validateContractVersion(null)).toBe("missing");
  });

  it("returns 'missing' when api_contract_version is undefined", () => {
    const response = makeHealthResponse({ api_contract_version: undefined });
    expect(validateContractVersion(response)).toBe("missing");
  });

  it("returns 'mismatch' when api_contract_version differs from required", () => {
    const response = makeHealthResponse({ api_contract_version: "2025-12" });
    expect(validateContractVersion(response)).toBe("mismatch");
  });

  it("returns 'mismatch' when api_contract_version is an empty string", () => {
    const response = makeHealthResponse({ api_contract_version: "" });
    expect(validateContractVersion(response)).toBe("mismatch");
  });
});

describe("buildDefaultFilterEdit", () => {
  it("returns a FilterEditContract with defaults when called with no arguments", () => {
    const draft = buildDefaultFilterEdit();
    expect(draft.original_query).toBe("");
    expect(draft.hard_filters.min_year).toBeNull();
    expect(draft.hard_filters.max_year).toBeNull();
    expect(draft.hard_filters.min_citations).toBe(0);
    expect(draft.hard_filters.open_access_only).toBe(false);
    expect(draft.soft_preferences.min_semantic_score).toBe(0);
    expect(draft.result_limit).toBe(10);
  });

  it("applies provided year, citation, and OA values", () => {
    const draft = buildDefaultFilterEdit(2020, 2025, 5, true);
    expect(draft.hard_filters.min_year).toBe(2020);
    expect(draft.hard_filters.max_year).toBe(2025);
    expect(draft.hard_filters.min_citations).toBe(5);
    expect(draft.hard_filters.open_access_only).toBe(true);
  });

  it("leaves include/exclude keyword lists empty", () => {
    const draft = buildDefaultFilterEdit();
    expect(draft.hard_filters.include_keywords).toEqual([]);
    expect(draft.hard_filters.exclude_keywords).toEqual([]);
  });
});
