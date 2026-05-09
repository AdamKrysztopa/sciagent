import type {
  HealthResponse,
  ResumeRequest,
  RunAcceptedResponse,
  RunRequest,
  StatusResponse,
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

export interface BackendClientConfig {
  apiKey: string;
  baseUrl: string;
  clientId: string;
  fetchImpl?: FetchImplementation;
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

export class SciAgentBackendClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly clientId: string;
  private readonly fetchImpl: FetchImplementation;

  constructor(config: BackendClientConfig) {
    this.apiKey = config.apiKey.trim();
    this.baseUrl = normalizeBaseUrl(config.baseUrl);
    this.clientId = config.clientId.trim() || "anonymous";
    this.fetchImpl = config.fetchImpl ?? fetch;
  }

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health", { method: "GET" });
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
    return headers;
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const hasBody = typeof init.body === "string";
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers: this.buildHeaders(hasBody),
    });

    if (!response.ok) {
      const detail = await parseErrorPayload(response);
      const message = typeof detail === "string" ? detail : `backend_request_failed:${response.status}`;
      throw new BackendClientError(message, response.status, detail);
    }

    return response.json() as Promise<T>;
  }
}

export function createBackendClient(config: BackendClientConfig): SciAgentBackendClient {
  return new SciAgentBackendClient(config);
}
