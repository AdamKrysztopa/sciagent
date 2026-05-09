import { describe, expect, it } from "vitest";

import {
  REQUIRED_API_CONTRACT_VERSION,
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
