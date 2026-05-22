# Spec A+E — Admin Service & Security Hardening

**Date:** 2026-05-22
**Status:** Approved — ready for implementation planning
**Scope:** Python backend (`src/agt/`), Zotero addon (`zotero-addon/src/`), new admin panel (`admin-panel/`).
**Supersedes:** Spec A (Security Hardening) and Spec E (User Management Portal).
**New runtime dependency:** `google-cloud-secret-manager` (GCP SDK, backend only).

---

## 1. Problem Statement

SciAgent is a shared GCP-hosted service. The current auth model has critical gaps:

1. **Single shared secret** — one key for everyone. Leaking or revoking affects all users.
2. **Unvalidated client identity** — `X-AGT-Client-ID` is self-reported; rate limits and run
   ownership can be spoofed.
3. **No credit isolation** — the hosted DeepSeek key has no per-user cap.
4. **No admin tooling** — no way to manage users, monitor usage, or communicate without
   SSH/gcloud access.

Secondary gaps: no HTTPS enforcement in the addon, and FastAPI's default error handlers echo
request field values.

---

## 2. Solution Overview

Three independently deployable phases:

| Phase | Delivers | Closes |
|---|---|---|
| **1 — Security Foundation** | Per-user keys via GCP Secret Manager, auth, rate limiting, credit caps, HTTPS enforcement, error sanitisation, admin REST API | All security gaps. Admin manages keys via curl/httpie against REST endpoints. |
| **2 — Admin Panel** | React SPA at `/portal/` calling Phase 1's admin API | Key management UI, usage dashboard, health monitoring, per-user budget overrides |
| **3 — Communication** | In-addon banners + email notifications | Admin-to-user messaging for announcements, budget alerts, maintenance notices |

---

## 3. Threat Model

| Threat | Impact | Mitigated by |
|---|---|---|
| Leaked shared key | High | Per-user keys; revoke one without touching others |
| Spoofed client ID | High | Identity derived from validated key |
| One user exhausts shared LLM budget | High | Per-user spend cap |
| Credentials sent over HTTP | High | HTTPS enforcement in addon |
| Key fragment leaked in error response | Medium | Sanitised exception handlers |
| Excessively large query | Medium | Input length limits |

Out of scope: GCP network-layer controls (Cloud Armor, VPC), Zotero credential storage
hardening (Spec B).

---

## 4. Phase 1 — Security Foundation

### 4.1 Key format

```
agt_<slug>_<32 lowercase hex chars>
```

- `slug` — 1-32 chars, `[a-z0-9_-]`, identifies the user in logs and rate-limit buckets.
- 32 hex chars = 128 bits of entropy via `secrets.token_hex(16)`.

### 4.2 User registry in GCP Secret Manager

A single secret (`agt-user-registry`) stores the full user registry as JSON:

```json
{
  "alice": {
    "key": "agt_alice_3f8b2c1d4e5f678901234567890abcde",
    "email": "alice@example.com",
    "budget_usd": 2.00,
    "is_admin": true,
    "created_at": "2026-05-22T10:00:00Z"
  },
  "bob": {
    "key": "agt_bob_9a2c1d3e4f5678901234567890abcdef",
    "email": "bob@university.edu",
    "budget_usd": 2.00,
    "is_admin": false,
    "created_at": "2026-05-22T11:00:00Z"
  }
}
```

**Secret Manager client** (`src/agt/secrets.py`):

- `get_user_registry() -> dict[str, UserEntry]` — returns cached registry.
- `update_user_registry(registry) -> None` — writes new secret version.
- `_refresh_cache() -> None` — called by background task every `AGT_SECRET_CACHE_TTL_SECONDS`
  (default 60). Key revocations take effect within one TTL cycle.

### 4.3 Backward compatibility

When `AGT_GCP_PROJECT` is **not** set (local dev, CI):

- Falls back to `AGT_BACKEND_API_KEY` (single-key mode, slug `"default"`, `is_admin=true`).
- No Secret Manager access needed.
- Startup log line indicates which auth mode is active.

Once `AGT_GCP_PROJECT` is set, `AGT_BACKEND_API_KEY` is ignored and a warning is logged if
still present.

### 4.4 Authentication dependency

`src/agt/api/auth.py` replaces `_api_key_header` and `_client_id_header`:

```python
def _authenticate(
    x_api_key: str | None = Header(default=None, alias="X-AGT-API-Key"),
    request: Request = None,
    settings: Settings = Depends(get_settings),
) -> str:
    """Validate X-AGT-API-Key, return user slug."""
    registry = get_user_registry()
    candidate = x_api_key or ""
    matched_slug: str | None = None
    for slug, entry in registry.items():
        if hmac.compare_digest(candidate, entry["key"]):
            matched_slug = slug
    if matched_slug is None:
        raise HTTPException(status_code=401, detail="invalid_api_key")
    if request is not None:
        request.state.user_slug = matched_slug
        request.state.is_admin = registry[matched_slug].get("is_admin", False)
    return matched_slug
```

All endpoints switch from `Depends(_api_key_header)` + `Depends(_client_id_header)` to
`slug: str = Depends(_authenticate)`.

### 4.5 Admin guard

```python
def _require_admin(request: Request) -> None:
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(status_code=403, detail="admin_required")
```

Applied via `Depends(_require_admin)` on all admin endpoints.

### 4.6 X-AGT-Client-ID removal

The header is no longer accepted. The authenticated `slug` becomes the `owner` on `RunRecord`,
`WatchRecord`, and all rate-limit buckets. Existing run records keyed by the old `client_id`
are unaffected (read-only history).

### 4.7 Per-user rate limiting

slowapi `Limiter` key function changes from IP to slug:

```python
def _get_user_key(request: Request) -> str:
    return getattr(request.state, "user_slug", request.client.host)
```

Unauthenticated paths (`/health`, `/docs`) keep IP-based limits.

### 4.8 Shared LLM credit cap

Setting: `AGT_SHARED_LLM_BUDGET_PER_USER_USD` (default `2.00`).

When a request uses the hosted LLM key (no `X-LLM-API-Key` header), `Guardrails` tracks spend
under `_shared_spend[slug]`. Per-user budget override from the registry takes precedence over
the default. When budget is exhausted:

- HTTP 402: `{"detail": "shared_llm_budget_exhausted", "hint": "Set your own LLM API key in the addon settings to continue."}`

In-memory tracking (resets on restart). When the user provides their own `X-LLM-API-Key`,
shared budget tracking is bypassed entirely.

### 4.9 Admin API endpoints

All protected by `Depends(_authenticate)` + `Depends(_require_admin)`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/keys` | Create key for user. Body: `{slug, email, budget_usd?}`. Returns generated key (shown once). |
| `DELETE` | `/admin/keys/{slug}` | Revoke user key. Removes from registry in Secret Manager. |
| `GET` | `/admin/keys` | List all users: slug, email, masked key, budget, created date. |
| `GET` | `/admin/usage` | Per-user spend: `{slug: {spend_usd, cap_usd, requests, last_seen}}`. |
| `PATCH` | `/admin/keys/{slug}` | Update user: budget override, admin flag. |

All write operations update Secret Manager via `update_user_registry()`.

### 4.10 HTTPS enforcement (addon)

`isInsecureUrl` helper in `src/host/prefs.ts`:

```typescript
export function isInsecureUrl(url: string): boolean {
  return url.startsWith("http://");
}
```

When `backendMode === "remote"` and URL is `http://`:

- `HealthStrip` shows red warning: "Insecure connection -- backend URL must use HTTPS."
- Search button is disabled with message: "Backend URL must use HTTPS. Update it in settings."
- `backendMode === "local"` is exempt (loopback is always HTTP).

`isInsecureUrl` is computed on the fly, not stored in `AddonConfig`.

### 4.11 Error response sanitisation

**Custom 422 handler:** `_safe_errors` strips `input` values from each error dict, keeping only
`loc`, `msg`, `type`. No field content (which might be a header value) is returned.

**Custom 500 handler:** Returns `{"detail": "internal_error"}`. Tracebacks logged server-side
only, never returned to the client.

### 4.12 Input validation

Pydantic `Field(max_length=...)` on request body models:

| Field | Limit |
|---|---|
| `query` | 2000 |
| `filter_edit.authors[*]` | 200 each |
| `filter_edit.include_keywords[*]` | 500 each |
| `filter_edit.exclude_keywords[*]` | 500 each |
| `filter_edit.venues[*]` | 200 each |
| `filter_edit.seed_dois[*]` | 100 each |
| `watch.name` | 200 |
| `watch.query` | 2000 |

---

## 5. Phase 2 — Admin Panel

### 5.1 Architecture

React SPA in `admin-panel/` at repo root (same level as `zotero-addon/`). Built with Vite.
FastAPI serves the built static files at `/portal/`.

### 5.2 Admin authentication

The admin logs in with their API key (same key used for API access). The SPA stores the key in
`sessionStorage` and sends it as `X-AGT-API-Key` on every request. The `_require_admin` guard
on admin endpoints ensures only admin users access the panel. No separate password or session
system needed.

### 5.3 Pages

| Page | Route | Description |
|---|---|---|
| Login | `/portal/login` | API key input. Validates against `GET /admin/keys`. |
| Dashboard | `/portal/` | Overview: active users, total spend, service health summary. |
| Users | `/portal/users` | User table with inline actions: revoke, edit budget. |
| Create User | `/portal/users/new` | Form: slug, email, budget. Shows generated key once. |
| Health | `/portal/health` | Backend status, active runs, error rate. |
| Messages | `/portal/messages` | Compose and send messages (wired in Phase 3). |

### 5.4 Tech stack

- React 18+ with TypeScript (strict mode)
- Vite for build tooling
- TanStack Query for server-state management
- Tailwind CSS for styling

### 5.5 Backend additions

- `src/agt/api/app.py` mounts static file serving for `/portal/`
- `GET /admin/health` endpoint: active run count, error count (last hour), uptime

---

## 6. Phase 3 — Communication

### 6.1 In-addon banners

New endpoint `GET /user/messages` (authenticated, not admin-only). Returns pending messages
for the authenticated user:

```json
[
  {"id": "msg_1", "type": "info", "text": "Budget reset for June.", "created_at": "..."},
  {"id": "msg_2", "type": "warning", "text": "Maintenance tonight.", "created_at": "..."}
]
```

Types: `info`, `warning`, `critical`.

The Zotero addon polls on sidebar open. Users dismiss messages via
`POST /user/messages/{id}/dismiss`.

### 6.2 Email notifications

Transactional email via SendGrid or Resend (free tier). API key stored in Secret Manager
(`agt-email-api-key`).

Admin composes from the portal Messages page:

- Select recipients: individual, all, or custom list
- Message text (plain text)
- Delivery channel: banner only, email only, or both

### 6.3 Message storage

Firestore (recommended) or an additional Secret Manager secret for low-volume use. Decision
deferred to Phase 3 implementation planning.

### 6.4 User email collection

Captured at key creation time (`POST /admin/keys` body includes `email`). Stored in the user
registry JSON.

---

## 7. Settings Changes

New fields in `src/agt/config.py`:

| Field | Env var | Default | Phase |
|---|---|---|---|
| `gcp_project` | `AGT_GCP_PROJECT` | `None` | 1 |
| `gcp_secret_name` | `AGT_GCP_SECRET_NAME` | `"agt-user-registry"` | 1 |
| `secret_cache_ttl_seconds` | `AGT_SECRET_CACHE_TTL_SECONDS` | `60` | 1 |
| `shared_llm_budget_per_user_usd` | `AGT_SHARED_LLM_BUDGET_PER_USER_USD` | `2.00` | 1 |

Existing `AGT_BACKEND_API_KEY` retained as local-dev fallback.

---

## 8. Component Map

### Phase 1

| Component | File | Change |
|---|---|---|
| Secret Manager client | `src/agt/secrets.py` (new) | Registry CRUD, cache with TTL |
| Auth dependency | `src/agt/api/auth.py` (new) | `_authenticate`, `_require_admin` |
| Admin endpoints | `src/agt/api/admin.py` (new) | Key CRUD, usage, budget endpoints |
| Settings | `src/agt/config.py` | Add GCP + budget fields |
| App wiring | `src/agt/api/app.py` | Replace old auth, add error handlers, mount admin routes |
| Guardrails | `src/agt/guardrails.py` | Per-user spend tracking with budget override |
| Prefs | `zotero-addon/src/host/prefs.ts` | `isInsecureUrl` helper |
| HealthStrip | `zotero-addon/src/ui/components/HealthStrip.tsx` | Insecure URL warning |
| IdleView | `zotero-addon/src/ui/components/IdleView.tsx` | Block search on insecure URL |
| Docs | `.env.example`, `docs/settings.md` | Document new env vars |

### Phase 2

| Component | File | Change |
|---|---|---|
| React SPA | `admin-panel/` (new) | Login, dashboard, users, health pages |
| Static serving | `src/agt/api/app.py` | Mount `/portal/` static files |
| Health endpoint | `src/agt/api/admin.py` | `GET /admin/health` |

### Phase 3

| Component | File | Change |
|---|---|---|
| Message endpoints | `src/agt/api/admin.py` | `POST /admin/messages`, `GET /user/messages` |
| Message storage | `src/agt/comms.py` (new) | Firestore or Secret Manager backed |
| Email sender | `src/agt/email.py` (new) | SendGrid/Resend integration |
| Banner component | `zotero-addon/src/ui/components/` | Message banner in sidebar |
| Compose UI | `admin-panel/src/` | Message compose page |

---

## 9. Acceptance Criteria

### Phase 1 — Security Foundation

- [x] Backend reads user registry from GCP Secret Manager when `AGT_GCP_PROJECT` is set.
- [x] Registry is cached with configurable TTL; refreshes in background.
- [x] `AGT_BACKEND_API_KEY` works as fallback when `AGT_GCP_PROJECT` is unset.
- [x] `POST /admin/keys` creates a user, writes to Secret Manager, returns the key.
- [x] `DELETE /admin/keys/{slug}` revokes a user, updates Secret Manager.
- [x] `GET /admin/keys` lists users with masked keys.
- [x] `GET /admin/usage` returns per-user spend and request counts.
- [x] `PATCH /admin/keys/{slug}` updates budget and admin flag.
- [x] Admin endpoints return 403 for non-admin users.
- [x] Valid per-user key is accepted; slug matches the registered user.
- [x] Invalid or missing key returns 401 `{"detail": "invalid_api_key"}`.
- [x] `X-AGT-Client-ID` is ignored; run ownership uses authenticated slug.
- [x] Per-user rate limits apply by slug for authenticated endpoints.
- [x] Shared LLM budget exhaustion returns 402 with hint.
- [x] Per-user budget override from registry takes precedence over default.
- [x] Own `X-LLM-API-Key` bypasses shared budget tracking.
- [x] Addon blocks search and shows warning on insecure remote URL.
- [x] 422 responses contain no field input values.
- [x] 500 responses return only `{"detail": "internal_error"}`.
- [x] Query > 2000 chars returns 422.
- [x] All Python quality gates pass.
- [x] Addon quality gates pass.

### Phase 2 — Admin Panel

- [ ] Admin can log in to `/portal/` with their API key.
- [ ] Dashboard shows active users, total spend, health summary.
- [ ] Users page lists all users with inline actions (revoke, edit budget).
- [ ] Create User page generates and displays key once.
- [ ] Health page shows backend status and active runs.
- [ ] Non-admin keys cannot access the portal.
- [ ] `admin-panel/` builds and passes lint + typecheck.

### Phase 3 — Communication

- [ ] Admin can compose and send messages from the portal.
- [ ] Messages appear as banners in the Zotero addon sidebar.
- [ ] Users can dismiss banner messages.
- [ ] Email notifications sent via transactional email provider.
- [ ] Admin can choose delivery channel: banner, email, or both.

---

## 10. Out of Scope

- Persistent credit tracking across restarts (Phase 1 uses in-memory).
- Key expiry / rotation enforcement.
- GCP Cloud Armor / WAF rules.
- Self-service user registration (admin creates all accounts).
- OAuth / SSO.
- Per-user billing / Stripe integration.
- Mobile-responsive admin panel.
- Zotero credential storage hardening (Spec B).
