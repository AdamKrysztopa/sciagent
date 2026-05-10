import { describe, expect, it, vi } from "vitest";

import { BackendClientError, createBackendClient } from "./backendClient";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

describe("SciAgentBackendClient", () => {
  it("adds required auth headers and normalizes the base URL", async () => {
    const calls: Array<{ init?: RequestInit; url: RequestInfo | URL }> = [];
    const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init, url });
      return jsonResponse({ ok: true, message: "ok" });
    });
    const client = createBackendClient({
      apiKey: "secret-key",
      baseUrl: "http://127.0.0.1:8000/",
      clientId: "sidebar-a",
      fetchImpl,
    });

    await client.health();

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(String(calls[0]?.url)).toBe("http://127.0.0.1:8000/health");

    const headers = calls[0]?.init?.headers;
    expect(headers).toBeInstanceOf(Headers);
    expect((headers as Headers).get("X-AGT-API-Key")).toBe("secret-key");
    expect((headers as Headers).get("X-AGT-Client-ID")).toBe("sidebar-a");
  });

  it("serializes JSON bodies and omits an empty API key", async () => {
    const calls: Array<{ init?: RequestInit; url: RequestInfo | URL }> = [];
    const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init, url });
      return jsonResponse({ run_id: "run-1", thread_id: "run-1", status: "awaiting_approval" });
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "sidebar-b",
      fetchImpl,
    });

    await client.run({ collection_name: "Inbox", query: "rag" });

    const headers = calls[0]?.init?.headers as Headers;
    expect(headers.get("X-AGT-API-Key")).toBeNull();
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(calls[0]?.init?.body).toBe(
      JSON.stringify({ collection_name: "Inbox", query: "rag" }),
    );
  });

  it("raises a typed error when the backend returns a failure", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ detail: "invalid_api_key" }, 401));
    const client = createBackendClient({
      apiKey: "bad",
      baseUrl: "http://localhost:8000",
      clientId: "sidebar-c",
      fetchImpl,
    });

    await expect(client.health()).rejects.toBeInstanceOf(BackendClientError);
    await expect(client.health()).rejects.toMatchObject({ status: 401 });
  });

  it("calls /capabilities and returns the response", async () => {
    const capResponse = {
      api_contract_version: "2026-05",
      source_policy: [
        { name: "semantic_scholar", tier: "primary", enabled: true, supports_year_filter: true, supports_open_access_filter: false },
      ],
      filter_support: { year_filter: ["semantic_scholar"] },
      pdf_import_supported: true,
    };
    const fetchImpl = vi.fn(async () => jsonResponse(capResponse));
    const client = createBackendClient({
      apiKey: "key",
      baseUrl: "http://localhost:8000",
      clientId: "sidebar-d",
      fetchImpl,
    });

    const result = await client.capabilities();
    expect(result.api_contract_version).toBe("2026-05");
    expect(result.source_policy).toHaveLength(1);
    expect(result.source_policy[0]?.name).toBe("semantic_scholar");
    expect(result.pdf_import_supported).toBe(true);
  });
});
