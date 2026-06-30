# SciAgent Security Model

## Authentication

All API endpoints optionally require an `X-AGT-API-Key` header when
`AGT_BACKEND_API_KEY` is set. Without a configured key the backend is
open (suitable for local single-user use only).

**Checklist:**

- [ ] Set `AGT_BACKEND_API_KEY` to a random secret before exposing the
      backend to a network.
- [ ] Rotate the key if it is ever exposed in logs or config files.

## CORS (Cross-Origin Resource Sharing)

The backend enforces an origin allowlist controlled by
`AGT_CORS_ALLOWED_ORIGINS` (JSON array). The default is `["*"]` which
allows any origin — acceptable only for localhost-only deployments.

**Checklist:**

- [ ] For non-local deployments set `AGT_CORS_ALLOWED_ORIGINS` to the
      exact origins that are allowed, e.g.
      `'["https://your-domain.example"]'`.
- [ ] Never use `["*"]` in production with `allow_credentials=true`.

## Rate Limiting

All endpoints share a global rate limit configured via
`AGT_API_RATE_LIMIT` (default `200/minute` per IP). Exceeding the limit
returns HTTP 429.

**Checklist:**

- [ ] Tune `AGT_API_RATE_LIMIT` for your environment (e.g. `50/minute`
      for a single-user setup).

## HTTPS

The backend listens on plain HTTP by default. In any networked deployment
traffic should be TLS-terminated by a reverse proxy (nginx, Caddy, or the
docker-compose example in `docker-compose.yml`).

**Checklist:**

- [ ] Place the backend behind a TLS-terminating proxy before exposing it
      over any non-loopback interface.
- [ ] Verify that `HTTPS_ONLY=true` or equivalent is set in your proxy.

## Secret Redaction

All secrets (API keys, tokens, passwords) are redacted from structured logs
via `RedactionFilter` and `_redaction_processor` in `src/agt/config.py`.
Review new log call sites to ensure no new secret patterns are added without
corresponding redaction.

## Future: Multi-User Auth

The current model is single-user with an optional static API key. A future
path to multi-user delegated auth would add per-user JWT tokens issued by
an identity provider, with the backend validating the JWT on every request.
Thread-isolation (`X-AGT-Client-ID` header) already separates run state per
client but does not yet prevent cross-client reads without the API key.
