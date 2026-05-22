export interface UserSummary {
  slug: string;
  email: string;
  key_suffix: string;
  budget_usd: number;
  is_admin: boolean;
  created_at: string;
}

export interface CreateKeyRequest {
  slug: string;
  email: string;
  budget_usd?: number;
}

export interface CreateKeyResponse {
  slug: string;
  key: string;
  email: string;
  budget_usd: number;
}

export interface UsageEntry {
  spend_usd: number;
  cap_usd: number;
  requests: number;
}

export interface HealthResponse {
  ok: boolean;
  provider: string;
  fallback_provider: string | null;
  preflight: { ok: boolean; message: string | null };
}

async function apiFetch<T>(
  path: string,
  apiKey: string,
  init?: RequestInit,
): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: {
      "X-AGT-API-Key": apiKey,
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({})) as { detail?: string };
    throw new Error(body.detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  listKeys: (apiKey: string) =>
    apiFetch<UserSummary[]>("/admin/keys", apiKey),

  createKey: (apiKey: string, body: CreateKeyRequest) =>
    apiFetch<CreateKeyResponse>("/admin/keys", apiKey, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  revokeKey: (apiKey: string, slug: string) =>
    apiFetch<{ status: string }>(`/admin/keys/${slug}`, apiKey, {
      method: "DELETE",
    }),

  updateKey: (
    apiKey: string,
    slug: string,
    body: { budget_usd?: number; is_admin?: boolean },
  ) =>
    apiFetch<{ status: string }>(`/admin/keys/${slug}`, apiKey, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  getUsage: (apiKey: string) =>
    apiFetch<Record<string, UsageEntry>>("/admin/usage", apiKey),

  getHealth: (apiKey: string) =>
    apiFetch<HealthResponse>("/health", apiKey),
};
