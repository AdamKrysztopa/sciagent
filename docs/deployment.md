# SciAgent Deployment Guide

This document covers deployment options for SciAgent: local development, Docker/self-hosted, and future SaaS architecture.

---

## Current Deployment Options

### Local Development (M6 Status)

The M6 milestone delivers a **local-first architecture** with:

- Python backend running on `localhost:8000` via `uvicorn`
- Zotero 9 add-on installed locally via unsigned XPI
- User's own Zotero API key and library ID
- No shared backend, no multi-user isolation, no persistence beyond in-memory run state

**Prerequisites:**

- Python 3.13+ (3.14 recommended)
- `uv` package manager
- Node.js 20+ for add-on build
- Zotero 9.x desktop client
- Zotero API key with read/write permissions

**Setup:**

```bash
# Backend
uv sync
cp .env.example .env
# Edit .env with your Zotero credentials and LLM API key
uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000

# Add-on
cd zotero-addon
npm ci
npm run build
# Install build/sciagent-zotero-addon.xpi in Zotero via add-ons manager
```

**Use Case:**

- Individual researchers running SciAgent on their own machine
- Privacy-first: all data stays local
- Full control over API keys, rate limits, and LLM provider choice
- No shared state or user isolation concerns

**Limitations:**

- No persistence: stopping the backend clears all run state
- Single-user only: no multi-tenancy or user management
- Manual dependency management and environment setup
- No background/async job processing
- No automatic updates or centralized monitoring

---

### Docker and Docker Compose

The repository ships a `Dockerfile` and `docker-compose.yml` for containerized deployment.

**Current Status (P5):**

- ✅ Dockerfile builds a Python 3.14 image with `uv sync`
- ✅ FastAPI backend is the default CMD: `uvicorn agt.api.app:app --host 0.0.0.0 --port 8000`
- ✅ `docker-compose.yml` mounts `.env` and `~/.sciagent` for persistent data
- ✅ CORS and rate limiting configurable via `AGT_CORS_ALLOWED_ORIGINS` / `AGT_API_RATE_LIMIT`
- ❌ No multi-container orchestration (backend + worker + database) — local only
- ❌ No secrets management integration (Vault, AWS Secrets Manager)

**Quickstart with Docker Compose:**

```bash
# Copy environment template and fill in credentials
cp .env.example .env
# Edit .env: add AGT_OPENAI_API_KEY (or Groq/Anthropic), AGT_ZOTERO_API_KEY, AGT_ZOTERO_LIBRARY_ID

# Build and start
docker compose up --build -d

# Verify
curl http://localhost:8000/health
```

Sessions, watches, and cache are persisted to `~/.sciagent` on the host via volume mount.

**Manual Docker Run (without Compose):**

```bash
docker build -t sciagent:latest .
docker run -d \
  --name sciagent-backend \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  -v "${HOME}/.sciagent:/root/.sciagent" \
  sciagent:latest
```

**Use Case:**

- Self-hosted deployment on a VPS or internal server
- Reproducible environment across development and production
- Privacy-first: all data stays on your infrastructure

**Missing for Production Self-Hosting:**

1. **Persistent State**: In-memory `_RunStore` cleared on restart; file-backed sessions/watches
   survive (mounted via volume)
2. **Authentication**: Set `AGT_BACKEND_API_KEY` + TLS termination via reverse proxy
3. **Async Workers**: Long-running workflows run in-process; no background job queue (AGT-25)
4. **Multi-user**: Single shared API key; no per-user isolation beyond `X-AGT-Client-ID`

---

### Multi-User GCP Deployment (Secret Manager + Admin Panel)

The Phase 1–3 security hardening enables a multi-user hosted deployment using GCP Secret Manager
for the user registry and the React admin panel for key management.

**Prerequisites:**

- GCP project with billing enabled (`sciagent-496617` or your own project)
- `gcloud` CLI installed and authenticated:
  `gcloud auth login && gcloud auth application-default login`
- GCP APIs enabled: Secret Manager, Cloud Run, Artifact Registry, Cloud Build

**One-time setup:**

Run the following once per GCP project:

```bash
# Enable required GCP APIs
gcloud services enable \
  secretmanager.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project=sciagent-496617

# Create service account
gcloud iam service-accounts create sciagent-backend \
  --display-name="SciAgent Backend" \
  --project=sciagent-496617

SA="sciagent-backend@sciagent-496617.iam.gserviceaccount.com"

# Grant Secret Manager permissions
gcloud projects add-iam-policy-binding sciagent-496617 \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding sciagent-496617 \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretVersionAdder"

# Bootstrap first admin user — SAVE the printed key, it cannot be recovered
uv run python scripts/bootstrap_registry.py \
  --project sciagent-496617 \
  --slug admin \
  --email your@email.com

# Store LLM key as a secret (never embed in deploy.sh)
printf '%s' "${AGT_OPENAI_API_KEY}" | \
  gcloud secrets create agt-openai-key --data-file=- --project=sciagent-496617
gcloud run services update sciagent \
  --set-secrets="AGT_OPENAI_API_KEY=agt-openai-key:latest" \
  --project=sciagent-496617 --region=europe-west1
```

**Deploy:**

```bash
./scripts/deploy.sh
```

**Verify:**

```bash
SERVICE_URL=$(gcloud run services describe sciagent \
  --project=sciagent-496617 --region=europe-west1 \
  --format="value(status.url)")

curl "${SERVICE_URL}/health"
# → {"ok": true, ...}

curl -H "X-AGT-API-Key: <admin-key>" "${SERVICE_URL}/admin/keys"
# → [{"slug": "admin", ...}]
```

**Admin panel:** Open `${SERVICE_URL}/portal/` in a browser and log in with the admin API key.

**Add users:**

```bash
curl -X POST "${SERVICE_URL}/admin/keys" \
  -H "X-AGT-API-Key: <admin-key>" \
  -H "Content-Type: application/json" \
  -d '{"slug": "alice", "email": "alice@example.com", "budget_usd": 5.0}'
```

**Environment variables managed via Cloud Run:**

| Variable | Required | Source |
|---|---|---|
| `AGT_GCP_PROJECT` | Yes | Set in `deploy.sh` via `--set-env-vars` |
| `AGT_GCP_SECRET_NAME` | No | Set in `deploy.sh` (default: `agt-user-registry`) |
| `AGT_OPENAI_API_KEY` | Yes\* | GCP Secret via `--set-secrets` |
| `AGT_RESEND_API_KEY` | No | GCP Secret via `--set-secrets` |
| `AGT_EMAIL_FROM` | No | GCP Secret via `--set-secrets` |

\*At least one LLM provider key (`AGT_OPENAI_API_KEY`, `AGT_ANTHROPIC_API_KEY`, etc.) is required.

---

## Future SaaS Architecture

The planned **multi-user SaaS deployment** (post-M6) would enable:

- Hosted backend with centralized API and job processing
- Multi-user isolation with proper authentication and authorization
- Durable state persistence across restarts
- Background workers for long-running search/write workflows
- Zotero add-on as a thin client talking to a shared backend

### Proposed Architecture

```text
┌─────────────────────────────────────────────────────┐
│ Zotero Desktop (multiple users)                     │
│   └─ SciAgent Add-on (thin client)                  │
│       └─ Calls hosted API via HTTPS                 │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│ API Gateway / Load Balancer                         │
│   └─ TLS termination, rate limiting, auth check     │
└───────────────────┬─────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
┌──────────────────┐   ┌──────────────────┐
│ FastAPI Backend  │   │ FastAPI Backend  │
│ (stateless)      │   │ (stateless)      │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ Job Queue (Redis)    │
         │   └─ Async workflows │
         └──────────┬───────────┘
                    ▼
         ┌──────────────────────┐
         │ Worker Pool          │
         │   └─ Search + Write  │
         └──────────┬───────────┘
                    │
         ┌──────────┴───────────┐
         ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│ PostgreSQL       │   │ Redis Cache      │
│ (durable state)  │   │ (fast lookups)   │
└──────────────────┘   └──────────────────┘
```

### Key Components

#### 1. Stateless API Tier

- Multiple FastAPI instances behind a load balancer
- JWT-based authentication with OAuth2 (GitHub, Google, institutional SSO)
- User-scoped API keys for programmatic access
- Role-based access control (admin, user, read-only)

#### 2. Job Queue and Workers

- Redis or RabbitMQ for job dispatch
- Worker pool running `agt.graph.workflow` in background
- Job status polling via `/status/{run_id}`
- Optional webhook callbacks for completion notifications

#### 3. Durable State Store

- PostgreSQL for:
  - User accounts and API keys
  - Workflow run metadata (run ID, thread ID, user ID, status)
  - Approval decisions and selected paper indices
  - Search plans and filter edits
- Optional S3/blob storage for large payloads (paper PDFs, full-text)

#### 4. Secrets Management

- Vault, AWS Secrets Manager, or GCP Secret Manager
- Per-user Zotero API keys stored encrypted
- LLM provider keys rotated centrally
- No hardcoded secrets in code or environment

#### 5. Observability

- OpenTelemetry tracing for distributed workflows
- Prometheus metrics for API latency, job queue depth, LLM costs
- Grafana dashboards for monitoring and alerting
- Structured logging with ELK or Datadog

---

## Prerequisites for SaaS Readiness

Before launching a hosted multi-user SaaS, the following stories must be completed:

### 1. AGT-21: Security Checklist and Auth Hardening

**Status:** Done (implemented in Phases 1–3 of Admin Service & Security Hardening plan)

**Scope:**

- Replace `AGT_BACKEND_API_KEY` with JWT-based user auth
- Add OAuth2 flow for GitHub/Google/institutional SSO
- Implement user registration, login, password reset
- Add role-based access control (admin vs user)
- Encrypt Zotero API keys at rest
- Add CSRF protection for web UI
- Rate-limit API endpoints per user

**Acceptance Criteria:**

- No hardcoded secrets in environment variables
- User API keys scoped to user accounts
- Admin panel for user management
- Zotero keys stored with AES-256 encryption
- All public endpoints protected with rate limits

---

### 2. AGT-24: Durable Distributed Checkpointing

**Status:** Not Done

**Scope:**

- Migrate from in-memory `_RunStore` to PostgreSQL
- Store workflow state (papers, search plan, write results) in database
- Support resumption across backend restarts
- Add pagination for large result sets
- Implement state pruning/archival for old runs

**Acceptance Criteria:**

- Backend restarts do not lose pending workflows
- `/status/{run_id}` retrieves state from database
- Workflow state survives for 7 days minimum
- Old runs archived after 30 days
- Pagination for `/status` with 50-result pages

---

### 3. AGT-25: Background Job Queue

**Status:** Not Done

**Scope:**

- Integrate Redis or RabbitMQ for job dispatch
- Move search and write workflows to worker pool
- Return job ID immediately from `/run`
- Add `/jobs/{job_id}` polling endpoint
- Optional webhook support for job completion

**Acceptance Criteria:**

- `/run` returns in <200ms with job ID
- Worker pool scales independently of API tier
- Job status polls show progress updates
- Workers respect per-user rate limits
- Failed jobs retry with exponential backoff

---

### 4. AGT-26: Multi-User Isolation and Secrets

**Status:** Not Done

**Scope:**

- Add `users` table with encrypted Zotero credentials
- Scope all queries by `user_id`
- Prevent cross-user data leakage in API responses
- Add per-user LLM cost tracking and quota limits
- Integrate Vault or AWS Secrets Manager

**Acceptance Criteria:**

- User A cannot access User B's workflows
- Zotero API keys stored encrypted per user
- LLM cost tracked per user, enforced quotas
- No secrets in environment variables or logs
- Secrets rotated via external manager

---

### 5. ZAP-11: Signed XPI Release

**Status:** Not Done

**Scope:**

- Sign XPI with Mozilla Add-ons or custom signing
- Publish to Zotero add-ons repository or self-hosted catalog
- Add auto-update manifest for version checks
- Document manual install vs signed install flow

**Acceptance Criteria:**

- XPI passes Zotero 9 signature validation
- Auto-update manifest published
- Users can install without "Install from File" workaround
- Update checks work without manual re-download

---

## Risk Assessment

### Technical Risks

| Risk                                 | Likelihood | Impact | Mitigation                                              |
| ------------------------------------ | ---------- | ------ | ------------------------------------------------------- |
| LLM cost explosion with many users   | High       | High   | Per-user quotas, cost tracking, circuit breakers        |
| Zotero API rate limits hit           | Medium     | High   | Per-user rate limiting, queue backpressure              |
| Search latency unacceptable for SaaS | Medium     | Medium | Caching, async workers, result pagination               |
| Data leakage across users            | Low        | High   | Strict user isolation, security audit, penetration test |
| Worker pool scaling issues           | Medium     | Medium | Horizontal scaling, worker health checks, job retries   |

### Operational Risks

| Risk                                 | Likelihood | Impact | Mitigation                                                 |
| ------------------------------------ | ---------- | ------ | ---------------------------------------------------------- |
| Secrets leaked in logs/errors        | Medium     | High   | Redaction, secret manager, audit logs                      |
| Database outage loses all state      | Low        | High   | Replication, backups, failover                             |
| Worker crashes lose in-progress jobs | Medium     | Medium | Job retry logic, durable queue, checkpoint writes          |
| Zotero API changes break integration | Low        | High   | Version pinning, integration tests, monitoring             |
| LLM provider outage blocks workflows | Medium     | Medium | Fallback providers (already implemented), graceful degrade |

---

## Implementation Timeline (Proposed)

| Phase | Stories                             | Estimated Effort | Milestone |
| ----- | ----------------------------------- | ---------------- | --------- |
| 1     | AGT-21 (Auth), AGT-26 (Isolation)   | 3-4 weeks        | M7.1      |
| 2     | AGT-24 (Checkpoints), AGT-25 (Jobs) | 2-3 weeks        | M7.2      |
| 3     | ZAP-11 (Signed XPI), monitoring     | 1-2 weeks        | M7.3      |
| 4     | Load testing, security audit        | 1-2 weeks        | M7.4      |

Total estimated: **8-12 weeks** for SaaS readiness.

---

## Self-Hosting Without SaaS Features

For organizations that want to self-host without the full SaaS stack:

**Minimal Production Setup:**

1. Run backend with `docker compose up -d` (mounts `~/.sciagent` for persistence)
2. Set `AGT_BACKEND_API_KEY` and a restrictive `AGT_CORS_ALLOWED_ORIGINS`
3. Use a reverse proxy (Nginx, Caddy) for TLS termination
4. Restrict network access to internal users only
5. See [Security](security.md) for the full pre-production checklist
6. Manually distribute the signed XPI to users

**What You Lose:**

- No multi-user isolation (single shared API key)
- No durable state (restarts clear pending workflows)
- No background jobs (long searches block the API)
- No per-user cost tracking or quotas
- No auto-update for add-on

**What You Keep:**

- Full control over API keys and LLM provider
- No external dependencies on hosted services
- Privacy: all data stays on your infrastructure

---

## See Also

- [Configuration & Usage Manual](manual.md) — Local setup and configuration
- [REST API Reference](api.md) — Backend API contract
- [Zotero Add-on Roadmap](zotero.md) — Native Zotero 9 integration and future plans
- [Core Roadmap](core.md) — Detailed story backlog including AGT-21, AGT-24, AGT-25, AGT-26
