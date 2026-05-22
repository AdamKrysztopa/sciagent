import type {
  CapabilitiesResponse,
  CorrectQueryResponse,
  DoctorReport,
  ExtractKeywordsResponse,
  FilterEditContract,
  GapFinderResponse,
  HealthResponse,
  KeyValidateResponse,
  NormalizedAuthor,
  PreflightStatus,
  ProviderInfo,
  ResolvedVenue,
  ResumeRequest,
  RunAcceptedResponse,
  RunRequest,
  StatusResponse,
  UserMessage,
  Watch,
  WatchRerunResponse,
} from "../shared/contracts";

export class BackendClientError extends Error {
  readonly detail: unknown;
  readonly status: number;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "BackendClientError";
    this.status = status;
    this.detail = detail;
  }
}

type FetchImplementation = typeof fetch;

const HEALTH_FALLBACK_MESSAGE = "Backend is reachable, but /health is not available.";

export interface BackendClientConfig {
  apiKey: string;
  baseUrl: string;
  clientId: string;
  fetchImpl?: FetchImplementation;
  // Zotero credentials for remote mode (MU2)
  zoteroApiKey?: string;
  zoteroLibraryId?: string;
  zoteroLibraryType?: string;
  // LLM override for remote mode (MU2)
  useCustomLlm?: boolean;
  customLlmProvider?: string;
  customLlmBaseUrl?: string;
  customLlmModel?: string;
  customLlmApiKey?: string;
}

function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim();
  return trimmed.replace(/\/+$/, "") || "http://127.0.0.1:8000";
}

async function parseErrorPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

function endpointCanUseReachabilityFallback(error: BackendClientError): boolean {
  return error.status === 404 || error.status === 405;
}

function cloudErrorMessage(response: Response): string | null {
  if (response.status === 401) return "API key rejected. Check Settings → Connection.";
  if (response.status === 403) return "Origin not allowed.";
  if (response.status === 429) {
    const retryAfter = response.headers.get("Retry-After");
    return retryAfter ? `Rate limit hit. Retry in ${retryAfter}s.` : "Rate limit hit.";
  }
  if (response.status >= 500) return "Backend not responding.";
  return null;
}

export class SciAgentBackendClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly clientId: string;
  private readonly fetchImpl: FetchImplementation;
  private readonly zoteroApiKey: string;
  private readonly zoteroLibraryId: string;
  private readonly zoteroLibraryType: string;
  private readonly useCustomLlm: boolean;
  private readonly customLlmProvider: string;
  private readonly customLlmBaseUrl: string;
  private readonly customLlmModel: string;
  private readonly customLlmApiKey: string;

  constructor(config: BackendClientConfig) {
    this.apiKey = config.apiKey.trim();
    this.baseUrl = normalizeBaseUrl(config.baseUrl);
    this.clientId = config.clientId.trim() || "anonymous";
    this.fetchImpl = config.fetchImpl ?? fetch;
    this.zoteroApiKey = (config.zoteroApiKey ?? "").trim();
    this.zoteroLibraryId = (config.zoteroLibraryId ?? "").trim();
    this.zoteroLibraryType = (config.zoteroLibraryType ?? "user").trim();
    this.useCustomLlm = config.useCustomLlm ?? false;
    this.customLlmProvider = (config.customLlmProvider ?? "").trim();
    this.customLlmBaseUrl = (config.customLlmBaseUrl ?? "").trim();
    this.customLlmModel = (config.customLlmModel ?? "").trim();
    this.customLlmApiKey = (config.customLlmApiKey ?? "").trim();
  }

  async health(): Promise<HealthResponse> {
    try {
      return await this.request<HealthResponse>("/health", { method: "GET" });
    } catch (error) {
      if (error instanceof BackendClientError && endpointCanUseReachabilityFallback(error)) {
        return this.healthFromReachableApiDocs(error);
      }
      throw error;
    }
  }

  async preflight(): Promise<PreflightStatus> {
    return this.request<PreflightStatus>("/preflight", { method: "POST" });
  }

  async capabilities(): Promise<CapabilitiesResponse> {
    return this.request<CapabilitiesResponse>("/capabilities", { method: "GET" });
  }

  async providers(): Promise<Record<string, ProviderInfo>> {
    return this.request<Record<string, ProviderInfo>>("/providers", { method: "GET" });
  }

  async run(payload: RunRequest): Promise<RunAcceptedResponse> {
    return this.request<RunAcceptedResponse>("/run", {
      body: JSON.stringify(payload),
      method: "POST",
    });
  }

  async resume(payload: ResumeRequest): Promise<RunAcceptedResponse> {
    return this.request<RunAcceptedResponse>("/resume", {
      body: JSON.stringify(payload),
      method: "POST",
    });
  }

  async status(runId: string): Promise<StatusResponse> {
    const encodedRunId = encodeURIComponent(runId.trim());
    return this.request<StatusResponse>(`/status/${encodedRunId}`, { method: "GET" });
  }

  async correctQuery(q: string): Promise<CorrectQueryResponse> {
    return this.request<CorrectQueryResponse>(
      `/correct-query?q=${encodeURIComponent(q)}`,
      { method: "GET" },
    );
  }

  async extractKeywords(query: string): Promise<ExtractKeywordsResponse> {
    return this.request<ExtractKeywordsResponse>("/extract-keywords", {
      body: JSON.stringify({ query }),
      method: "POST",
    });
  }

  async libraryDoctor(collectionName: string): Promise<DoctorReport> {
    return this.request<DoctorReport>("/library-doctor", {
      body: JSON.stringify({ collection_name: collectionName }),
      method: "POST",
    });
  }

  async gapFinder(collectionName: string): Promise<GapFinderResponse> {
    return this.request<GapFinderResponse>("/gap-finder", {
      body: JSON.stringify({ collection_name: collectionName }),
      method: "POST",
    });
  }

  // ── Watch List (SCI-0401/0402) ─────────────────────────────────────────

  async createWatch(
    name: string,
    query: string,
    collectionName: string | null,
    filterEdit: FilterEditContract | null,
  ): Promise<Watch> {
    return this.request<Watch>("/watches", {
      body: JSON.stringify({
        name,
        query,
        collection_name: collectionName,
        filter_edit: filterEdit,
      }),
      method: "POST",
    });
  }

  async listWatches(): Promise<Watch[]> {
    return this.request<Watch[]>("/watches", { method: "GET" });
  }

  async deleteWatch(watchId: string): Promise<void> {
    await this.requestVoid(`/watches/${encodeURIComponent(watchId)}`, { method: "DELETE" });
  }

  async rerunWatch(watchId: string): Promise<WatchRerunResponse> {
    return this.request<WatchRerunResponse>(
      `/watches/${encodeURIComponent(watchId)}/rerun`,
      { method: "POST" },
    );
  }

  async validateKey(provider: string, apiKey: string): Promise<KeyValidateResponse> {
    return this.request<KeyValidateResponse>("/keys/validate", {
      body: JSON.stringify({ provider, api_key: apiKey }),
      method: "POST",
    });
  }

  async suggestAuthors(q: string, limit = 5): Promise<NormalizedAuthor[]> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return this.request<NormalizedAuthor[]>(`/authors/suggest?${params.toString()}`, {
      method: "GET",
    });
  }

  async suggestVenues(q: string, limit = 5): Promise<ResolvedVenue[]> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return this.request<ResolvedVenue[]>(`/venues/suggest?${params.toString()}`, {
      method: "GET",
    });
  }

  async fetchMessages(): Promise<UserMessage[]> {
    return this.request<UserMessage[]>("/user/messages", { method: "GET" });
  }

  async dismissMessage(messageId: string): Promise<void> {
    return this.requestVoid(`/user/messages/${messageId}/dismiss`, {
      method: "POST",
    });
  }

  private buildHeaders(withJsonBody: boolean): Headers {
    const headers = new Headers();
    headers.set("Accept", "application/json");
    headers.set("X-AGT-Client-ID", this.clientId);
    if (this.apiKey.length > 0) {
      headers.set("X-AGT-API-Key", this.apiKey);
    }
    if (withJsonBody) {
      headers.set("Content-Type", "application/json");
    }
    if (this.zoteroApiKey.length > 0) {
      headers.set("X-Zotero-API-Key", this.zoteroApiKey);
    }
    if (this.zoteroLibraryId.length > 0) {
      headers.set("X-Zotero-Library-ID", this.zoteroLibraryId);
      headers.set("X-Zotero-Library-Type", this.zoteroLibraryType || "user");
    }
    if (this.useCustomLlm && this.customLlmApiKey.length > 0) {
      headers.set("X-LLM-API-Key", this.customLlmApiKey);
      if (this.customLlmProvider.length > 0) headers.set("X-LLM-Provider", this.customLlmProvider);
      if (this.customLlmBaseUrl.length > 0) headers.set("X-LLM-Base-URL", this.customLlmBaseUrl);
      if (this.customLlmModel.length > 0) headers.set("X-LLM-Model", this.customLlmModel);
    }
    return headers;
  }

  private async requestVoid(path: string, init: RequestInit): Promise<void> {
    const hasBody = typeof init.body === "string";
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers: this.buildHeaders(hasBody),
    });
    if (!response.ok) {
      const cloud = cloudErrorMessage(response);
      if (cloud !== null) throw new BackendClientError(cloud, response.status, null);
      const detail = await parseErrorPayload(response);
      const message = typeof detail === "string" ? detail : `backend_request_failed:${response.status}`;
      throw new BackendClientError(message, response.status, detail);
    }
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const hasBody = typeof init.body === "string";
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers: this.buildHeaders(hasBody),
    });

    if (!response.ok) {
      const cloud = cloudErrorMessage(response);
      if (cloud !== null) throw new BackendClientError(cloud, response.status, null);
      const detail = await parseErrorPayload(response);
      const message = typeof detail === "string" ? detail : `backend_request_failed:${response.status}`;
      throw new BackendClientError(message, response.status, detail);
    }

    return response.json() as Promise<T>;
  }

  private async healthFromReachableApiDocs(originalError: BackendClientError): Promise<HealthResponse> {
    const openApiResponse = await this.fetchImpl(`${this.baseUrl}/openapi.json`, {
      headers: this.buildHeaders(false),
      method: "GET",
    });

    if (openApiResponse.ok) {
      return {
        fallback_provider: null,
        message: HEALTH_FALLBACK_MESSAGE,
        ok: true,
        preflight: {
          message: "/openapi.json responded successfully.",
          ok: true,
        },
        provider: "unknown",
      };
    }

    if (!endpointCanUseReachabilityFallback(new BackendClientError("openapi_unavailable", openApiResponse.status, null))) {
      throw originalError;
    }

    const docsResponse = await this.fetchImpl(`${this.baseUrl}/docs`, {
      headers: this.buildHeaders(false),
      method: "GET",
    });

    if (docsResponse.ok) {
      return {
        fallback_provider: null,
        message: HEALTH_FALLBACK_MESSAGE,
        ok: true,
        preflight: {
          message: "/docs responded successfully.",
          ok: true,
        },
        provider: "unknown",
      };
    }

    throw originalError;
  }
}

export function createBackendClient(config: BackendClientConfig): SciAgentBackendClient {
  return new SciAgentBackendClient(config);
}
