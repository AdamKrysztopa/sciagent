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

  it("returns a human-readable message for 401", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ detail: "invalid_api_key" }, 401));
    const client = createBackendClient({ apiKey: "bad", baseUrl: "http://localhost:8000", clientId: "c", fetchImpl });
    await expect(client.health()).rejects.toMatchObject({
      message: "API key rejected. Check Settings → Connection.",
      status: 401,
    });
  });

  it("returns a human-readable message for 403", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ detail: "forbidden" }, 403));
    const client = createBackendClient({ apiKey: "k", baseUrl: "http://localhost:8000", clientId: "c", fetchImpl });
    await expect(client.run({ query: "rag", collection_name: "Inbox" })).rejects.toMatchObject({
      message: "Origin not allowed.",
      status: 403,
    });
  });

  it("returns a rate-limit message for 429 without Retry-After", async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 429 }));
    const client = createBackendClient({ apiKey: "k", baseUrl: "http://localhost:8000", clientId: "c", fetchImpl });
    await expect(client.health()).rejects.toMatchObject({ message: "Rate limit hit.", status: 429 });
  });

  it("includes retry countdown in 429 message when Retry-After is set", async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { headers: { "Retry-After": "30" }, status: 429 }));
    const client = createBackendClient({ apiKey: "k", baseUrl: "http://localhost:8000", clientId: "c", fetchImpl });
    await expect(client.health()).rejects.toMatchObject({ message: "Rate limit hit. Retry in 30s.", status: 429 });
  });

  it("returns a not-responding message for 5xx", async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 503 }));
    const client = createBackendClient({ apiKey: "k", baseUrl: "http://localhost:8000", clientId: "c", fetchImpl });
    await expect(client.health()).rejects.toMatchObject({ message: "Backend not responding.", status: 503 });
  });

  it("treats a reachable OpenAPI document as online when /health is absent", async () => {
    const calls: string[] = [];
    const fetchImpl = vi.fn(async (url: RequestInfo | URL) => {
      calls.push(String(url));
      if (String(url).endsWith("/health")) {
        return jsonResponse({ detail: "not found" }, 404);
      }
      return jsonResponse({ info: { title: "SciAgent API", version: "0.1.0" }, paths: {} });
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "sidebar-d",
      fetchImpl,
    });

    const result = await client.health();

    expect(calls).toEqual(["http://localhost:8000/health", "http://localhost:8000/openapi.json"]);
    expect(result.ok).toBe(true);
    expect(result.message).toContain("reachable");
    expect(result.preflight.message).toBe("/openapi.json responded successfully.");
  });

  it("falls back to /docs when both /health and /openapi.json are absent", async () => {
    const calls: string[] = [];
    const fetchImpl = vi.fn(async (url: RequestInfo | URL) => {
      calls.push(String(url));
      if (String(url).endsWith("/docs")) {
        return new Response("<html><title>SciAgent API</title></html>", {
          headers: { "Content-Type": "text/html" },
          status: 200,
        });
      }
      return jsonResponse({ detail: "not found" }, 404);
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "sidebar-e",
      fetchImpl,
    });

    const result = await client.health();

    expect(calls).toEqual([
      "http://localhost:8000/health",
      "http://localhost:8000/openapi.json",
      "http://localhost:8000/docs",
    ]);
    expect(result.ok).toBe(true);
    expect(result.preflight.message).toBe("/docs responded successfully.");
  });

  it("calls /correct-query and returns the response", async () => {
    const calls: Array<{ url: RequestInfo | URL }> = [];
    const fetchImpl = vi.fn(async (url: RequestInfo | URL) => {
      calls.push({ url });
      return jsonResponse({ original: "wrod", corrected: "word", changed: true });
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "sidebar-g",
      fetchImpl,
    });

    const result = await client.correctQuery("wrod");
    expect(result.original).toBe("wrod");
    expect(result.corrected).toBe("word");
    expect(result.changed).toBe(true);
    expect(String(calls[0]?.url)).toBe("http://localhost:8000/correct-query?q=wrod");
  });

  it("calls /library-doctor and returns the DoctorReport", async () => {
    const reportResponse = {
      collection_name: "Inbox",
      total_items: 10,
      issues: [
        {
          item_key: "ABC123",
          title: "A paper with no DOI",
          issue_types: ["missing_doi"],
          duplicate_of: null,
        },
      ],
      duplicate_pairs: [],
    };
    const calls: Array<{ init?: RequestInit; url: RequestInfo | URL }> = [];
    const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init, url });
      return jsonResponse(reportResponse);
    });
    const client = createBackendClient({
      apiKey: "key",
      baseUrl: "http://localhost:8000",
      clientId: "sidebar-h",
      fetchImpl,
    });

    const result = await client.libraryDoctor("Inbox");
    expect(String(calls[0]?.url)).toBe("http://localhost:8000/library-doctor");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(calls[0]?.init?.body).toBe(JSON.stringify({ collection_name: "Inbox" }));
    expect(result.collection_name).toBe("Inbox");
    expect(result.total_items).toBe(10);
    expect(result.issues).toHaveLength(1);
    expect(result.issues[0]?.issue_types).toContain("missing_doi");
  });

  it("calls /gap-finder and returns the GapFinderResponse", async () => {
    const gapResponse = {
      reasoning: "Your collection is missing foundational transformer papers.",
      papers: [
        {
          title: "Attention Is All You Need",
          year: 2017,
          doi: "10.48550/arXiv.1706.03762",
          arxiv_id: "1706.03762",
          abstract: null,
          authors: ["Vaswani et al."],
          url: "https://arxiv.org/abs/1706.03762",
          pdf_url: null,
          source: "arxiv",
          index: null,
          semantic_score: 0.95,
          citation_count: 80000,
          influential_citation_count: 5000,
          open_access: true,
          summary: null,
          score: 0.95,
          explanation: null,
        },
      ],
    };
    const calls: Array<{ init?: RequestInit; url: RequestInfo | URL }> = [];
    const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init, url });
      return jsonResponse(gapResponse);
    });
    const client = createBackendClient({
      apiKey: "key",
      baseUrl: "http://localhost:8000",
      clientId: "sidebar-i",
      fetchImpl,
    });

    const result = await client.gapFinder("Inbox");
    expect(String(calls[0]?.url)).toBe("http://localhost:8000/gap-finder");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(calls[0]?.init?.body).toBe(JSON.stringify({ collection_name: "Inbox" }));
    expect(result.reasoning).toContain("transformer");
    expect(result.papers).toHaveLength(1);
    expect(result.papers[0]?.title).toBe("Attention Is All You Need");
  });

  it("sends Zotero credential headers when configured", async () => {
    const calls: Array<{ init?: RequestInit }> = [];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init });
      return jsonResponse({ run_id: "r1", thread_id: "r1", status: "awaiting_approval" });
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "c",
      fetchImpl,
      zoteroApiKey: "zotero-key-123",
      zoteroLibraryId: "9876543",
      zoteroLibraryType: "user",
    });

    await client.run({ query: "rag", collection_name: "Inbox" });

    const headers = calls[0]?.init?.headers as Headers;
    expect(headers.get("X-Zotero-API-Key")).toBe("zotero-key-123");
    expect(headers.get("X-Zotero-Library-ID")).toBe("9876543");
    expect(headers.get("X-Zotero-Library-Type")).toBe("user");
  });

  it("does not send Zotero headers when credentials are empty", async () => {
    const calls: Array<{ init?: RequestInit }> = [];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init });
      return jsonResponse({ ok: true, message: "ok" });
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "c",
      fetchImpl,
    });

    await client.health();

    const headers = calls[0]?.init?.headers as Headers;
    expect(headers.get("X-Zotero-API-Key")).toBeNull();
    expect(headers.get("X-Zotero-Library-ID")).toBeNull();
    expect(headers.get("X-Zotero-Library-Type")).toBeNull();
  });

  it("sends LLM override headers when useCustomLlm is true and key is set", async () => {
    const calls: Array<{ init?: RequestInit }> = [];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init });
      return jsonResponse({ run_id: "r2", thread_id: "r2", status: "awaiting_approval" });
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "c",
      fetchImpl,
      useCustomLlm: true,
      customLlmApiKey: "my-llm-key",
      customLlmProvider: "deepseek",
      customLlmBaseUrl: "https://api.deepseek.com/v1",
      customLlmModel: "deepseek-chat",
    });

    await client.run({ query: "rag", collection_name: "Inbox" });

    const headers = calls[0]?.init?.headers as Headers;
    expect(headers.get("X-LLM-API-Key")).toBe("my-llm-key");
    expect(headers.get("X-LLM-Provider")).toBe("deepseek");
    expect(headers.get("X-LLM-Base-URL")).toBe("https://api.deepseek.com/v1");
    expect(headers.get("X-LLM-Model")).toBe("deepseek-chat");
  });

  it("does not send LLM headers when useCustomLlm is false", async () => {
    const calls: Array<{ init?: RequestInit }> = [];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init });
      return jsonResponse({ ok: true, message: "ok" });
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "c",
      fetchImpl,
      useCustomLlm: false,
      customLlmApiKey: "my-llm-key",
      customLlmProvider: "deepseek",
    });

    await client.health();

    const headers = calls[0]?.init?.headers as Headers;
    expect(headers.get("X-LLM-API-Key")).toBeNull();
    expect(headers.get("X-LLM-Provider")).toBeNull();
  });

  it("does not send LLM headers when useCustomLlm is true but key is empty", async () => {
    const calls: Array<{ init?: RequestInit }> = [];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ init });
      return jsonResponse({ ok: true, message: "ok" });
    });
    const client = createBackendClient({
      apiKey: "",
      baseUrl: "http://localhost:8000",
      clientId: "c",
      fetchImpl,
      useCustomLlm: true,
      customLlmApiKey: "",
    });

    await client.health();

    const headers = calls[0]?.init?.headers as Headers;
    expect(headers.get("X-LLM-API-Key")).toBeNull();
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
      clientId: "sidebar-f",
      fetchImpl,
    });

    const result = await client.capabilities();
    expect(result.api_contract_version).toBe("2026-05");
    expect(result.source_policy).toHaveLength(1);
    expect(result.source_policy[0]?.name).toBe("semantic_scholar");
    expect(result.pdf_import_supported).toBe(true);
  });
});
