# SciAgent Actionable Plan — GCP Deployment (Cloud Run + CI/CD)

> **⚠ Pivot 2026-05-17.** Single-user deploy (M0–M4) is **done** and live at
> `https://sciagent-ewpafdgfya-ew.a.run.app`. M5–M10 are **superseded** by the
> multi-user pivot — see [`actionable-plan-multiuser.md`](actionable-plan-multiuser.md)
> for the open-backend / BYO-credentials redesign. Do not execute M5–M10 of this
> plan; they assume single-user secrets baked into the service.
>
> **Prerequisite.** Every box in P10 is checked — see
> [actionable-plan-done-4.md](actionable-plan-done-4.md). This plan assumes:
>
> - The cheap LLM (DeepSeek or equivalent) is wired and smoke-tested locally.
> - The `Dockerfile` honors `$PORT`.
> - `.dockerignore` exists and the image is < 500 MB.
> - The end-to-end Zotero flow works against `localhost:8080`.
>
> **Audience.** You, learning GCP for the first time.
>
> **Canonical env var names.** The source design doc used `AGT_OPENAI_API_KEY`
> for the LLM key. After auditing the code, the correct variable is
> `AGT_LLM_API_KEY` — that is what `router.py:138` reads for the
> `openai-compatible` provider. Use `AGT_LLM_API_KEY` everywhere in this plan.
>
> Canonical execution tracker. Update done/not done state here first.
> Historical completed work stays in `actionable-plan-done*.md` — do not re-open closed items.

---

## TL;DR — What You Actually Do

- [ ] **G1.** Create GCP account, project `sciagent-prod`, billing account, $5 budget alert.
- [ ] **G2.** Install `gcloud` CLI, run `gcloud init` + `gcloud auth application-default login`.
- [ ] **G3.** Enable 7 GCP APIs.
- [ ] **G4.** Create one Artifact Registry Docker repo.
- [ ] **G5.** Create a least-privilege service account `sciagent-run`.
- [ ] **G6.** Put every secret into Secret Manager.
- [ ] **G7.** Build via Cloud Build, push to Artifact Registry, deploy to Cloud Run with `--min-instances=0`.
- [ ] **G8.** Smoke test `/health` and `/run` via authenticated `curl`.
- [ ] **G9.** Update the Zotero add-on "Backend URL" preference + add cloud error UX.
- [ ] **G10.** Wire GitHub Actions → Cloud Build → Cloud Run for auto-deploy on `main`.
- [ ] **G11.** Set up Cloud Storage for persistent sessions *(Phase 2, only when needed)*.

**Cost for solo daily use: $0–$2/month** (mostly $0). See §Cost Model.

---

## Tooling Setup

Set these up before M0. They save time throughout the deployment.

### VS Code Extensions

#### Required for GCP work

| Extension | ID | Why |
|---|---|---|
| **Cloud Code** | `googlecloudtools.cloudcode` | Official Google extension. Cloud Run deploy/log sidebar, YAML schema for `cloudbuild.yaml`, in-editor tail of Cloud Logging. |
| **Docker** | `ms-azuretools.vscode-docker` | Dockerfile lint, local build/run, layer inspection. Helps diagnose image size issues (C4). |
| **YAML** | `redhat.vscode-yaml` | Schema validation for `cloudbuild.yaml` and `.github/workflows/`. Catches typos before push. |
| **GitHub Actions** | `github.vscode-github-actions` | Autocomplete and validation for workflow files. |

#### Strongly recommended

| Extension | ID | Why |
|---|---|---|
| **REST Client** | `humao.rest-client` | Create `.http` files to hit `/health`, `/run`, and `/capabilities` with your API key without copy-pasting `curl` flags every time. Far better than a raw terminal for testing the cloud endpoint. |
| **Even Better TOML** | `tamasfe.even-better-toml` | `pyproject.toml` editing with schema validation. |

#### Cloud Code commands you will actually use

- **`Cloud Code: Sign In`** — once, before M0.
- **`Cloud Code: View Logs`** — tail Cloud Logging in-editor during M4/M5 testing.
- **`Cloud Code: Open Cloud Shell`** — free pre-authenticated Linux shell in the browser if local `gcloud` misbehaves.

Skip "Cloud Code: Deploy to Cloud Run" GUI — it hides the flags. Use the `gcloud`
commands in M4 explicitly so futurev-you can reproduce the exact configuration.

---

### MCP Servers for GCP Work

The MCP servers already wired in `CLAUDE.md` cover most of the GCP plan. The table
below maps each MCP to where it is useful during this plan.

| MCP Server | When to use during GCP deployment |
|---|---|
| **`context7`** | Before writing or editing `cloudbuild.yaml`, Cloud Run YAML specs, or IAM bindings — fetch current GCP documentation (Cloud Run pricing, Secret Manager limits, Cloud Build config schema). Do not rely on training-data memory for GCP API details; they change frequently. |
| **`fetch`** | Retrieve current Cloud Run pricing, IAM role documentation, or the Cloud Build substitutions reference directly from `cloud.google.com` while working through milestones. |
| **`github`** | Checking CI status (Cloud Build trigger → GitHub Actions chain), PR state after M7, verifying the `release.yml` workflow still passes alongside the new `cloudbuild.yaml`. |
| **`sequential-thinking`** | Before M3 (secrets wiring is multi-step and order-dependent) and before M7 (IAM grants for Cloud Build touch three principals). Use sequential-thinking to reason through the permission graph before running any `gcloud iam` commands. |
| **`git`** | Structured log / blame when debugging which commit triggered a Cloud Build run that broke the deploy. |

#### GCP-specific MCP server (optional, community)

A community `gcloud` MCP server exists that wraps the `gcloud` CLI as an MCP
tool, allowing Claude Code to run `gcloud` commands directly within the session.
As of 2026-05, this is experimental and not in the project's default MCP config.

**If you want to add it:**

```json
// In .claude/settings.local.json → mcpServers
"gcloud": {
  "command": "npx",
  "args": ["-y", "@anthropic-samples/gcp-mcp"],
  "env": {}
}
```

Use with caution — it runs real `gcloud` commands against your production project.
Only add it after M2 (IAM is set up) and with the budget alert from M0.4 active.
The `--max-instances=2` flag in M4.2 is your rate guardrail; make sure it is set
before giving Claude Code direct `gcloud` access.

Without the GCP MCP server: use the **Bash tool** in Claude Code to run
`gcloud` commands. This is the safer default and how all milestones in this plan
are written.

---

## Executive Decisions

| Decision | Choice | Why |
|---|---|---|
| Compute | **Cloud Run, request-based billing, min-instances=0** | Scales to zero when idle. Free tier covers solo usage entirely. |
| Container registry | **Artifact Registry** (Docker format, regional) | GCP-native, replaces deprecated Container Registry. |
| Build system | **Cloud Build** triggered from GitHub | Free tier: 120 build-minutes/day. No local Docker daemon needed for CI. |
| Secrets | **Secret Manager**, mounted as env vars on Cloud Run | Encrypted, IAM-controlled, free up to 6 active versions. |
| LLM | **DeepSeek via `openai-compatible` adapter** | $0.07/month at solo volume. Env var swap, zero code change. |
| Persistence Phase 1 | **Container filesystem (ephemeral)** | Sessions/cache vanish on cold start. Acceptable for solo use. |
| Persistence Phase 2 | **Cloud Storage bucket mounted via volume** | ~$0.02/GB-month. No DB cost. Trigger: when cold-start data loss hurts. |
| Region | **`europe-west1`** (EU) or **`us-central1`** (NA) | Both are Cloud Run Tier 1 (cheapest per-vCPU-second). |
| Auth Phase 1 | **`X-AGT-API-Key` only**, public Cloud Run URL | Simple. Acceptable for personal use. |
| Auth Phase 2 | **Cloud Run IAM `--no-allow-unauthenticated`** | Deferred until you have other users. |
| CI/CD | **GitHub Actions → Cloud Build → Cloud Run** | Integrates with existing `.github/workflows/`. |
| Logging | **Cloud Logging** (default, free tier) | No external cost. |
| Google Scholar | **Disabled in production** | Cloud Run IPs get CAPTCHA-walled. Not worth it. See §Don't Bother. |

---

## Cost Model

### Solo usage (~50 requests/day, 3s @ 1 vCPU + 512 MiB)

| Item | Monthly |
|---|---|
| Cloud Run vCPU-seconds (4,500) | **$0.00** (180k free) |
| Cloud Run memory GiB-s (2,250) | **$0.00** (360k free) |
| Cloud Run requests (1,500) | **$0.00** (2M free) |
| Artifact Registry (~500 MB) | **~$0.05** |
| Cloud Build (~5 builds/mo) | **$0.00** (120 build-min/day free) |
| Secret Manager (≤6 secrets) | **$0.00** (6 versions free) |
| Logs (< 50 MB) | **$0.00** (50 GiB free) |
| DeepSeek LLM (~300k tokens) | **~$0.07** |
| **Total** | **~$0.12/month** |

### Hard guardrails to set on Day 1

- [ ] Budget alert at **$5/month** with email at 50/90/100 %.
- [ ] `--max-instances=2` while learning.
- [ ] `--min-instances=0` — the single biggest cost knob.
- [ ] `--memory=512Mi` — smallest realistic for FastAPI + SciAgent deps.
- [ ] `--timeout=300` — don't let LLM hangs run for an hour.
- [ ] `--concurrency=40`.

---

## Google Scholar — Don't Bother

Being on Cloud Run gives zero advantage for Google Scholar. Cloud Run egress comes
from datacenter IPs — Google's anti-bot systems flag those immediately. You get
CAPTCHA-walled in minutes. Commercial SERP APIs (SerpAPI) cost $50–$120/month
minimum — 25–60x your entire GCP bill. The existing keyless sources (OpenAlex,
Semantic Scholar, Crossref, PubMed, arXiv, Europe PMC) are competitive per
`docs/benchmark.md`. Leave `AGT_SERPAPI_KEY` unset in production.

---

## Architecture (End State)

```
              Zotero Desktop (your laptop)
                        │
                        │  HTTPS + X-AGT-API-Key + X-AGT-Client-ID
                        ▼
        ┌──────────────────────────────────────┐
        │  Cloud Run service: sciagent         │
        │  region: europe-west1                │
        │  min=0, max=2, cpu=1, memory=512Mi   │
        │  concurrency=40, timeout=300s        │
        │  identity: sciagent-run@...iam       │
        └──────────────┬───────────────────────┘
                       │
     ┌─────────────────┼──────────────────────┐
     │                 │                      │
     ▼                 ▼                      ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│ Artifact     │  │ Secret       │  │ Cloud Storage    │
│ Registry     │  │ Manager      │  │ (Phase 2)        │
│ docker image │  │ secrets      │  │ sciagent-data/   │
└──────────────┘  └──────────────┘  └──────────────────┘
                       │
                       │  outbound HTTPS
                       ▼
     ┌──────────────────────────────────────┐
     │ External APIs                        │
     │ - api.deepseek.com (LLM)             │
     │ - api.semanticscholar.org            │
     │ - api.openalex.org / crossref / etc. │
     └──────────────────────────────────────┘

              GitHub (main) ──push──▶ Cloud Build ──▶ Cloud Run revision
```

---

## Milestones

### M0 — GCP Account & Local Tooling (1 evening)

**Goal.** `gcloud run services list` runs without errors against your project.

- [x] **M0.1** Create a Google Cloud account at <https://console.cloud.google.com>.
  New accounts get **$300 free credit for 90 days**.
- [x] **M0.2** ~~Create project `sciagent-prod`.~~ Project created as **`sciagent-496617`**
  (project number: 358017232995). Set as default: `gcloud config set project sciagent-496617`.
  Use `sciagent-496617` everywhere this plan references `sciagent-prod`.
- [x] **M0.3** Link a billing account. Required even for free-tier services.
- [x] **M0.4** Set the billing budget alert — "Alert" budget, **50 zł/month**, alerts at 50/90/100%. Done 2026-05-17.
- [x] **M0.5** Install `gcloud` via `brew install --cask google-cloud-sdk`. Done 2026-05-17.
- [x] **M0.6** Authenticate:
  - [x] `gcloud init` — signed in as `krysztopa@gmail.com`, project sciagent-496617 set. Done 2026-05-17.
  - [x] `gcloud auth application-default login` — ADC saved. Done 2026-05-17.

- [x] **M0.7** Set default region: `gcloud config set run/region europe-west1`. Done 2026-05-17.

- [x] **M0.8** Verify: `gcloud projects describe sciagent-496617` → ACTIVE. Done 2026-05-17.

**Cost: $0.**

---

### M1 — Enable APIs and Foundation Resources (30 minutes)

- [x] **M1.1** Enable the 7 required APIs. Done 2026-05-17.
- [x] **M1.2** Create Artifact Registry repo `sciagent` in `europe-west1`. Done 2026-05-17.
- [x] **M1.3** Configure Docker auth to AR. Done 2026-05-17.
- [x] **M1.4** Verify: `gcloud artifacts repositories list` shows `sciagent`. Done 2026-05-17.

**Cost: $0** (empty repos are free).

---

### M2 — Service Account & IAM (20 minutes)

**Goal.** Cloud Run runs as a dedicated identity with only what it needs. Never
use the default Compute Engine service account.

- [x] **M2.1** Created service account `sciagent-run@sciagent-496617.iam.gserviceaccount.com`. Done 2026-05-17.
- [x] **M2.2** Granted 3 minimum roles: `secretmanager.secretAccessor`, `logging.logWriter`, `monitoring.metricWriter`. Done 2026-05-17.
- [x] **M2.3** Verified: all 3 roles confirmed at project level. Done 2026-05-17.

**Cost: $0.**

---

### M3 — Secrets in Secret Manager (45 minutes)

**Goal.** Nothing sensitive ever in the image, build-time env vars, or shell
history. Every key fetched at container startup via Secret Manager.

#### Required secrets

| Secret name | What it holds | Notes |
|---|---|---|
| `AGT_BACKEND_API_KEY` | The `X-AGT-API-Key` token the add-on sends | Generate: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `AGT_ZOTERO_API_KEY` | Zotero API key | From zotero.org/settings/keys — read + write scope |
| `AGT_ZOTERO_LIBRARY_ID` | Zotero user/group ID | Not strictly secret, but treat as private |
| `AGT_LLM_API_KEY` | Your cheap LLM key (DeepSeek, Groq, etc.) | Read by `src/agt/providers/router.py:138` |

#### Plain env vars (not secret — set via `--set-env-vars` in M4)

| Variable | Value |
|---|---|
| `AGT_LLM_PROVIDER` | `openai-compatible` |
| `AGT_LLM_BASE_URL` | `https://api.deepseek.com/v1` |
| `AGT_LLM_MODEL` | `deepseek-chat` |
| `AGT_CORS_ALLOWED_ORIGINS` | `zotero://*,http://localhost:*` |
| `AGT_LOG_LEVEL` | `INFO` |

These are not secrets — they contain no key material. Store them as plain env
vars on the Cloud Run service, not in Secret Manager.

#### Optional enrichment secrets (only if you use them)

| Secret name | Source |
|---|---|
| `AGT_SEMANTIC_SCHOLAR_API_KEY` | semanticscholar.org/product/api |
| `AGT_NCBI_API_KEY` | ncbi.nlm.nih.gov/account/settings |
| `AGT_CORE_API_KEY` | core.ac.uk/services/api |

#### Steps

- [x] **M3.1** Generate the backend API key:

  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

  Save to your password manager. You will paste it into the Zotero add-on
  settings in M5.

- [x] **M3.2** Created all 4 secrets from `.env` directly into Secret Manager. Done 2026-05-17.
  Note: `AGT_BACKEND_API_KEY` v1 was the placeholder (14 chars); v2 is the correct generated key (64 chars).

- [x] **M3.3** Verified: all 4 secrets readable, correct lengths. Done 2026-05-17.

- [ ] **M3.4** (Optional) Grant the service account per-secret access for
  belt-and-braces control:

  ```bash
  for s in AGT_BACKEND_API_KEY AGT_ZOTERO_API_KEY AGT_ZOTERO_LIBRARY_ID AGT_LLM_API_KEY; do
    gcloud secrets add-iam-policy-binding $s \
      --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
  done
  ```

  The project-level `secretAccessor` from M2.2 already covers this. Per-secret
  bindings are optional.

- [ ] **M3.5** Set a 90-day rotation reminder for:
  - DeepSeek key — via dashboard, then `echo -n "new" | gcloud secrets versions add AGT_LLM_API_KEY --data-file=-`.
  - Zotero key — via zotero.org settings.
  - Backend API key — regenerate locally, add new version, update Zotero add-on prefs.

**Cost: $0** (free tier: 6 active versions, 10k access ops/month).

---

### M4 — First Manual Deploy to Cloud Run ✅ Done 2026-05-17

**Goal.** `https://sciagent-ewpafdgfya-ew.a.run.app/health` returns 200 — ACHIEVED.

- [x] **M4.1** Build and push via Cloud Build (no local Docker needed):

  ```bash
  REGION=europe-west1
  PROJECT_ID=$(gcloud config get-value project)
  IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/sciagent/backend:v0.1.0"

  gcloud builds submit --tag $IMAGE .
  ```

  Takes 2–4 minutes. Free tier covers 120 build-minutes/day.

- [ ] **M4.2** Deploy:

  ```bash
  gcloud run deploy sciagent \
    --image=$IMAGE \
    --region=$REGION \
    --service-account=$SA \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=2 \
    --cpu=1 \
    --memory=512Mi \
    --concurrency=40 \
    --timeout=300 \
    --port=8080 \
    --set-secrets="AGT_BACKEND_API_KEY=AGT_BACKEND_API_KEY:latest" \
    --set-secrets="AGT_ZOTERO_API_KEY=AGT_ZOTERO_API_KEY:latest" \
    --set-secrets="AGT_ZOTERO_LIBRARY_ID=AGT_ZOTERO_LIBRARY_ID:latest" \
    --set-secrets="AGT_LLM_API_KEY=AGT_LLM_API_KEY:latest" \
    --set-env-vars="AGT_LLM_PROVIDER=openai-compatible" \
    --set-env-vars="AGT_LLM_BASE_URL=https://api.deepseek.com/v1" \
    --set-env-vars="AGT_LLM_MODEL=deepseek-chat" \
    --set-env-vars="AGT_CORS_ALLOWED_ORIGINS=zotero://*,http://localhost:*,chrome-extension://*" \
    --set-env-vars="AGT_LOG_LEVEL=INFO"
  ```

  Flag notes:

  - `--allow-unauthenticated` — Phase 1 only. App-level `X-AGT-API-Key` is the
    gate. M6 tightens this.
  - `--min-instances=0` — scales to zero. The single biggest cost knob.
  - `--set-secrets` — Secret Manager injects values at startup, not baked into image.
  - `AGT_LLM_*` env vars — not secrets; set directly.

- [ ] **M4.3** Grab the service URL:

  ```bash
  URL=$(gcloud run services describe sciagent --region=$REGION --format='value(status.url)')
  echo $URL
  ```

- [ ] **M4.4** Smoke test `/health`:

  ```bash
  API_KEY="<the-AGT_BACKEND_API_KEY-you-saved>"
  curl -H "X-AGT-API-Key: $API_KEY" \
       -H "X-AGT-Client-ID: dev-test" \
       "$URL/health"
  ```

  Expect 200 JSON. Check for the `sciagent_startup` log line — it should show
  `llm_provider=openai-compatible` and `llm_base_url=https://api.deepseek.com/v1`.

- [ ] **M4.5** Tail logs:

  ```bash
  gcloud run services logs tail sciagent --region=$REGION
  ```

- [ ] **M4.6** Run a real search:

  ```bash
  curl -X POST "$URL/run" \
    -H "X-AGT-API-Key: $API_KEY" \
    -H "X-AGT-Client-ID: dev-test" \
    -H "Content-Type: application/json" \
    -d '{"query":"retrieval augmented generation","collection_name":"SciAgent Cloud Test","limit":5}'
  ```

  Expect a `run_id` and 5 results. Watch logs — DeepSeek should be hit.

**Cost: a few cents** for the build + test calls.

---

### M5 — Zotero Add-on Updates for Cloud (1–2 hours)

**Goal.** The add-on talks to the Cloud Run URL exactly as it talked to
`localhost:8080`. Two sub-items require code changes to the add-on.

#### M5-A — Point at the new backend (10 minutes, no code)

- [ ] **M5-A.1** In Zotero → Tools → SciAgent → Settings → Connection:
  - Backend Mode: **Remote**.
  - Backend URL: paste `$URL` from M4.3.
  - Backend API Key: paste your `AGT_BACKEND_API_KEY`.
- [ ] **M5-A.2** Click "Test Connection" — expect green.
- [ ] **M5-A.3** Run end-to-end: search → approve → write to a test collection.
  If this works, the cloud deploy is real. **This is the gate.**

#### M5-B — Surface which backend is active in the UI (30 minutes, code)

**Why.** After you have both a local binary and a cloud backend, you will forget
which one the add-on is hitting. This has no test to catch it.

**Files to change:** `zotero-addon/src/host/runtime.ts` or wherever the health
badge is rendered (the component that calls `isServerRunning()`). Also potentially
`zotero-addon/src/ui/components/` — search for where the green/red health dot is
shown.

- [ ] **M5-B.1** After a successful `/health` call, display the backend URL's
  hostname in the sidebar status area. Short: `localhost:57321`, `sciagent-xxx.run.app`.
- [ ] **M5-B.2** Add a Vitest test that asserts the hostname extraction works for
  localhost, `*.run.app`, and a custom domain.

#### M5-C — Tighten CORS (15 minutes, no code)

For Phase 1 the CORS config in M4.2 is correct (`zotero://*`, `localhost:*`). If
you later add a docs site or admin UI:

- [ ] **M5-C.1** Update the Cloud Run env var:

  ```bash
  gcloud run services update sciagent --region=$REGION \
    --update-env-vars="AGT_CORS_ALLOWED_ORIGINS=zotero://*,http://localhost:*,https://yourdomain.com"
  ```

#### M5-D — Explicit cloud error UX in the add-on (30 minutes, code)

**Why.** In local mode the backend either works or isn't running. In cloud mode
it can be up but rejecting you (expired key, rate limit, cold-start timeout).
The current add-on has no specific handling for these statuses.

**File to change:** `zotero-addon/src/client/backendClient.ts`.

- [ ] **M5-D.1** Add explicit status handling in the fetch path:
  - **401** → `"API key rejected. Check Settings → Connection."` Do not retry.
  - **403** → `"Origin not allowed."` Do not retry.
  - **429** → `"Rate limit hit."` Show a countdown if `Retry-After` header is set.
  - **5xx + timeout** → `"Backend not responding. Falling back to cached results."`
    Trigger the existing offline cache path (`useOfflineCache.ts`).

- [ ] **M5-D.2** Add one Vitest test per status code — assert the right error
  message and retry behavior.

- [ ] **M5-D.3** Run the Zotero add-on quality gate:

  ```bash
  cd zotero-addon && npm ci && npm run lint && npm run build && npm run typecheck && npm run test
  ```

#### M5-E — Update `docs/deployment.md` (10 minutes)

- [ ] **M5-E.1** Add a "Cloud Run quickstart" subsection pointing at this plan
  and giving the one-liner for pointing the add-on at a hosted backend.

---

### M6 — Tighten Auth (Optional, Phase 2)

**When.** You share the API key with someone else, or you go public.

The Cloud Run URL is currently public — anyone can send requests (they still
need the right `X-AGT-API-Key`, but cold-start CPU is still consumed).

- [ ] **M6.1** Disable public access:

  ```bash
  gcloud run services update sciagent --region=$REGION --no-allow-unauthenticated
  ```

- [ ] **M6.2** Grant your user invoker rights (for `curl` testing):

  ```bash
  USER_EMAIL=$(gcloud config get-value account)
  gcloud run services add-iam-policy-binding sciagent \
    --member="user:$USER_EMAIL" \
    --role="roles/run.invoker" --region=$REGION
  ```

- [ ] **M6.3** Test with an ID token:

  ```bash
  TOKEN=$(gcloud auth print-identity-token)
  curl -H "Authorization: Bearer $TOKEN" \
       -H "X-AGT-API-Key: $API_KEY" \
       "$URL/health"
  ```

- [ ] **M6.4** The Zotero add-on needs to mint and send an ID token per request.
  This is ~50 lines of TypeScript + tests. **Defer until you actually have a
  second user.** It requires a service-account JSON key stored in the add-on prefs
  (non-trivial security surface).

---

### M7 — CI/CD: Auto-Deploy on Push to `main` (1 hour)

**Goal.** Every push to `main` triggers a Cloud Build → Cloud Run deploy. No
manual `gcloud builds submit` needed after this.

- [ ] **M7.1** Create `cloudbuild.yaml` at repo root:

  ```yaml
  steps:
    - name: gcr.io/cloud-builders/docker
      args:
        - build
        - -t
        - europe-west1-docker.pkg.dev/$PROJECT_ID/sciagent/backend:$SHORT_SHA
        - -t
        - europe-west1-docker.pkg.dev/$PROJECT_ID/sciagent/backend:latest
        - .

    - name: gcr.io/cloud-builders/docker
      args:
        - push
        - --all-tags
        - europe-west1-docker.pkg.dev/$PROJECT_ID/sciagent/backend

    - name: gcr.io/google.com/cloudsdktool/cloud-sdk
      entrypoint: gcloud
      args:
        - run
        - deploy
        - sciagent
        - --image=europe-west1-docker.pkg.dev/$PROJECT_ID/sciagent/backend:$SHORT_SHA
        - --region=europe-west1
        - --platform=managed
        - --quiet

  options:
    logging: CLOUD_LOGGING_ONLY
  ```

  Secrets and resource flags persist on the service between deploys — `cloudbuild.yaml`
  only swaps the image. Change CPU/memory/secrets via `gcloud run services update`,
  not in CI.

- [ ] **M7.2** Create the GitHub trigger:

  ```bash
  gcloud builds triggers create github \
    --name="sciagent-main-deploy" \
    --repo-name="sciagent" \
    --repo-owner="AdamKrysztopa" \
    --branch-pattern="^main$" \
    --build-config="cloudbuild.yaml"
  ```

  First run prompts you to install the Google Cloud Build GitHub app. Approve it.

- [ ] **M7.3** Grant Cloud Build's service account the permissions it needs:

  ```bash
  PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
  CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$CB_SA" --role="roles/run.admin"

  gcloud iam service-accounts add-iam-policy-binding $SA \
    --member="serviceAccount:$CB_SA" --role="roles/iam.serviceAccountUser"
  ```

- [ ] **M7.4** Push a trivial commit to `main`. Watch Cloud Console → Cloud Build
  → History. Within ~3 minutes Cloud Run shows a new revision.

- [ ] **M7.5** Verify: `gcloud run revisions list --service=sciagent --region=$REGION`
  shows the new revision as ACTIVE.

---

### M8 — Persistence (Phase 2, trigger-based)

**When.** You restart the service and notice your sessions / result cache are gone.
Do not do this preemptively — the ephemeral filesystem is fine for Phase 1.

The codebase stores sessions in `~/.sciagent/sessions/` (JSON) and result cache
in `~/.sciagent/cache.sqlite`. On Cloud Run, both vanish on cold start.

- [ ] **M8.1** Create the Cloud Storage bucket:

  ```bash
  gcloud storage buckets create gs://sciagent-data-$PROJECT_ID --location=$REGION
  ```

- [ ] **M8.2** Mount it as a volume and point SciAgent at it:

  ```bash
  gcloud run services update sciagent --region=$REGION \
    --add-volume=name=data,type=cloud-storage,bucket=sciagent-data-$PROJECT_ID \
    --add-volume-mount=volume=data,mount-path=/data \
    --update-env-vars="AGT_DATA_DIR=/data"
  ```

  `AGT_DATA_DIR` is read by `server.py` and propagated to `SessionStore` and
  `ResultCache`. No code change required — the server already accepts `--data-dir`
  and sets `AGT_DATA_DIR` from it.

- [ ] **M8.3** Verify: run a search, restart the service, run the same search
  again. The result cache should be warm (cache hit logged) and session history
  should persist.

**Cost: ~$0.02/GB-month.**

---

### M9 — Observability & Cost Control (Always-On)

- [ ] **M9.1** Re-verify the budget alert from M0.4 is still active.
- [ ] **M9.2** Bookmark the Cloud Run dashboard: Console → Cloud Run → sciagent
  → Metrics. Key tiles: request count, p50/p95 latency, billable container
  instance time, memory utilization.
- [ ] **M9.3** Create one alert policy: "Billable instance time > 10,000
  vCPU-seconds in a day" → email. Catches runaway loops.
- [ ] **M9.4** Monthly: `gcloud run services describe sciagent --region=$REGION`.
  Right-size if p95 memory utilization is < 30%.
- [ ] **M9.5** Monthly: prune old Artifact Registry images. Keep last 5:

  ```bash
  gcloud artifacts docker images list \
    europe-west1-docker.pkg.dev/$PROJECT_ID/sciagent/backend \
    --sort-by=~CREATE_TIME --limit=999 --format='value(IMAGE)' | tail -n +6 | \
    xargs -I {} gcloud artifacts docker images delete {} --quiet
  ```

---

### M10 — Custom Domain (Optional, ~$12/year for the domain)

Only if you want `https://api.sciagent.yourname.dev` instead of `*.run.app`.

- [ ] **M10.1** Buy a domain (Cloudflare Registrar is cheap).
- [ ] **M10.2** Map it:

  ```bash
  gcloud beta run domain-mappings create \
    --service=sciagent \
    --domain=api.sciagent.yourname.dev \
    --region=$REGION
  ```

  Cloud Run issues a managed TLS cert automatically (free).

- [ ] **M10.3** Update the Zotero add-on Backend URL to the new domain.
- [ ] **M10.4** Update `AGT_CORS_ALLOWED_ORIGINS` if needed.

---

## Hard "Make It Cheaper" Checklist

Walk this top-to-bottom whenever your bill surprises you.

- [ ] `--min-instances=0` set? Verify: `gcloud run services describe sciagent --region=$REGION | grep minScale`.
- [ ] `--max-instances` ≤ 5 for solo use?
- [ ] Memory ≤ 512 MiB?
- [ ] Concurrency ≥ 40?
- [ ] Region is Tier 1 (`europe-west1` or `us-central1`)?
- [ ] Image size < 500 MB? (check in M9.5)
- [ ] Logs not retained beyond 30 days?
- [ ] No `--cpu-throttling=false`? Default is throttled — correct.
- [ ] No idle Cloud SQL instance? ($8+/month minimum, no scale-to-zero)
- [ ] No leftover Artifact Registry images? (M9.5)
- [ ] LLM model is `deepseek-chat`, not `deepseek-reasoner`? (reasoner burns tokens)

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Cold-start latency frustrates interactive use | Medium | `--min-instances=0` means first request after idle takes 3–8s. Acceptable for solo use. Set `--min-instances=1` ($1–2/month) if it bothers you. |
| DeepSeek API outage during a cloud demo | Low | Switch to `AGT_LLM_PROVIDER=openai` + `AGT_LLM_API_KEY=<openai-key>` via `gcloud run services update --update-env-vars`. One command, no redeploy. |
| Secret rotation breaks the running service | Low | Add a new secret version, deploy a new Cloud Run revision, then delete the old version. Zero downtime. |
| `cloudbuild.yaml` deploy races with a PR build | Low | Cloud Build triggers are branch-scoped. M7.2 only triggers on `main`, not PRs. |
| `.dockerignore` misses a heavy file | Low | Check `docker images` size after M4.1. If > 500 MB, inspect with `docker history sciagent:latest`. |
| M5-D code changes break existing add-on tests | Medium | Run the full Vitest suite before merging. The new error-status tests are additions, not replacements. |

---

## What This Plan Does Not Cover

- **Multi-user auth / OAuth** — needs Cloud SQL + code work. Deferred.
- **Async job queue** — Cloud Tasks or Pub/Sub. Only needed if requests exceed
  Cloud Run's 15-min timeout (current `--timeout=300` is fine).
- **Terraform / Pulumi IaC** — worth doing before you have > 1 environment.
- **MkDocs hosting** — GitHub Pages, free, unrelated to backend.
- **macOS / Windows code signing** — planned for v1.1 (see `docs/local-first.md`).

---

## Tracker

### Current Status

- Prerequisite: P10 (`actionable-plan-done-4.md`) ✅ complete (2026-05-17).
- Current focus: **M0 — GCP Account & Local Tooling**
- Current next implementation target: **MU1** in [`actionable-plan-multiuser.md`](actionable-plan-multiuser.md) — backend credential injection
- Last completed: M5 done 2026-05-17 (M5-B and M5-D shipped, will be revised in MU2)
- **Pivoted to multi-user 2026-05-17.** M6–M10 of this plan are no longer applicable.
- **Note:** Project ID is `sciagent-496617` — replace `sciagent-prod` everywhere in this plan.

### Phase Tracker

- [x] **P10 prereqs done** — gate: do not proceed past this line until checked
- [ ] **M0** — GCP Account & Local Tooling
- [ ] **M1** — Enable APIs and Foundation Resources
- [ ] **M2** — Service Account & IAM
- [ ] **M3** — Secrets in Secret Manager
- [ ] **M4** — First Manual Deploy
- [ ] **M5** — Zotero Add-on Updates for Cloud
  - [ ] M5-A — Point at new backend *(operational)*
  - [ ] M5-B — Surface backend hostname in UI *(code)*
  - [ ] M5-C — Tighten CORS *(operational)*
  - [ ] M5-D — Cloud error UX in `backendClient.ts` *(code)*
  - [ ] M5-E — Update `docs/deployment.md` *(docs)*
- [ ] **M6** — Tighten Auth *(optional, Phase 2)*
- [ ] **M7** — CI/CD via Cloud Build
- [ ] **M8** — Persistence *(trigger-based, Phase 2)*
- [ ] **M9** — Observability
- [ ] **M10** — Custom Domain *(optional)*

### Tracker Rules

1. Update status here first.
2. The P10 prereq gate is checked — proceed directly to M0.
3. Treat the first unchecked milestone as the current focus.
4. Secrets and resource flags persist between Cloud Run deploys. If you change
   CPU/memory/secrets, do it via `gcloud run services update`, not `cloudbuild.yaml`.
5. When a decision in the Executive Decisions table changes, write a one-line
   rationale in the milestone where it changed.

---

## See Also

- `docs/actionable-plan-done-4.md` — completed P10 prereqs plan.
- `docs/deployment.md` — user-facing deployment overview (update in M5-E).
- `docs/api.md` — REST contract the Zotero add-on calls.
- `src/agt/providers/router.py` — provider routing (read before changing LLM config).
- `src/agt/config.py` — settings contract (read before adding env vars).
- [Cloud Run pricing](https://cloud.google.com/run/pricing) — re-check before any architecture change.
