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
});
