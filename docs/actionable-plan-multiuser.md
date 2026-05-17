# SciAgent Multi-User Plan — Open Backend with BYO Credentials

> **Supersedes M5–M10 of `actionable-plan.md`.** Single-user Cloud Run deploy
> (M0–M4) is the prerequisite; this plan converts it into a shared demo where
> users bring their own Zotero credentials and (optionally) their own LLM key.
>
> **Authored 2026-05-17 after live deploy at `https://sciagent-ewpafdgfya-ew.a.run.app`.**

---

## Executive Decisions (locked, 2026-05-17)

| Decision | Choice |
|---|---|
| LLM cost model | **Hybrid** — backend's DeepSeek key by default; users can BYO LLM key via headers to override. |
| Access control | **Open** — no `X-AGT-API-Key` gate. Anyone with the add-on URL can use the backend. |
| Cost cap | **$10 hard cap** via existing 50 zł budget alert (M0.4) + scale-to-zero + `--max-instances=2`. |
| Trust model | Stated explicitly in README. Backend never persists user credentials. Logs redact secrets. |
| Credential transport | HTTPS request headers only. Never in URL, body, or cache. |

---

## Architecture Diff

### Before (M4 state)

```
Zotero add-on ──HTTPS──> Cloud Run (sciagent)
                          │
                          │ uses BAKED-IN secrets:
                          │   AGT_ZOTERO_API_KEY     (Adam's)
                          │   AGT_ZOTERO_LIBRARY_ID  (Adam's)
                          │   AGT_LLM_API_KEY        (Adam's)
                          ▼
                       Adam's Zotero  +  DeepSeek (Adam pays)
```

### After (this plan)

```
Zotero add-on ──HTTPS + per-request headers──> Cloud Run (sciagent)
   │   X-Zotero-API-Key      (user's)              │
   │   X-Zotero-Library-ID   (user's)              │ no bound Zotero secrets
   │   X-Zotero-Library-Type (user's)              │ shared default LLM key
   │   X-LLM-API-Key         (user's, optional)    │
   │   X-LLM-Provider        (user's, optional)    │
   │   X-LLM-Model           (user's, optional)    │
   │   X-LLM-Base-URL        (user's, optional)    │
   ▼                                                ▼
User's Zotero (per request)         DeepSeek (Adam's key) OR user's LLM
```

---

## Credentials Threading: Contextvar, Not State

LangGraph state checkpoints survive across `/run` → `awaiting_approval` → `/resume`.
We do **NOT** want credentials persisted in those checkpoints.

**Pattern:** request-scoped `contextvars.ContextVar` set at endpoint entry, read by
tools at write time, never serialized.

- `/run` extracts headers → sets contextvar → invokes graph
- Graph pauses at human-in-loop → contextvar evaporates (graph is dehydrated, OK)
- `/resume` extracts headers **again** → sets contextvar → resumes graph
- Tools (`zotero_upsert`, `pdf_attach`, etc.) read from contextvar at execution time

Result: zero credential leakage through the session store. The add-on must send
the same credentials on `/run` and `/resume`.

---

## Phases

### MU0 — Verify cost guardrails (15 min)

- [ ] Confirm 50 zł / month budget alert from M0.4 is active.
- [ ] Confirm `--max-instances=2` on Cloud Run service: `gcloud run services describe sciagent --region=europe-west1 | grep -i maxScale`.
- [ ] (Optional) Set a hard DeepSeek monthly cap in the DeepSeek dashboard if available.

### MU1 — Backend credential injection (1–1.5 days)

**Goal.** Every Zotero/LLM call inside a request reads credentials from a
request-scoped contextvar, not from `settings`.

#### New file: `src/agt/api/credentials.py`

- Define `RequestCredentials` Pydantic model with optional/required fields per below.
- Define `current_credentials: ContextVar[RequestCredentials | None]` module-global.
- Define `get_credentials(...)` FastAPI dependency that:
  - Parses headers (`X-Zotero-API-Key`, `X-Zotero-Library-ID`, `X-Zotero-Library-Type`,
    `X-LLM-API-Key`, `X-LLM-Provider`, `X-LLM-Model`, `X-LLM-Base-URL`).
  - Validates required fields for Zotero-touching endpoints.
  - Sets the contextvar, yields, resets in `finally`.

#### Files to refactor

| File | Change |
|---|---|
| `src/agt/api/app.py` | Attach `Depends(get_credentials)` to `/run`, `/resume`, `/library-doctor`, `/gap-finder`, `/extract-keywords`. Add new `/preflight` endpoint that calls `run_preflight(credentials)`. Change `/health` to service-only (drop Zotero preflight). |
| `src/agt/zotero/preflight.py` | `run_preflight(creds: RequestCredentials)` — stop reading from `settings`. |
| `src/agt/zotero/collection_inspector.py` | Read from `current_credentials.get()` instead of `settings`. |
| `src/agt/tools/zotero_upsert.py` | Same: 3 call sites switch to contextvar. |
| `src/agt/tools/pdf_attach.py` | Same. |
| `src/agt/providers/router.py` | `get_llm()` — if `creds.llm_api_key` is set, build provider from creds; otherwise use `settings`. |
| `src/agt/config.py` | Mark `zotero_*` settings as dev-only (kept for local single-user dev). Add `multi_user_mode: bool = True` (default True; flips to False if `AGT_ZOTERO_API_KEY` is set, for local backwards compat). |
| `tests/test_zotero_*.py`, `tests/test_api_*.py` | Update fixtures to pass credentials in headers (use a `make_credentials_headers()` helper). |

#### Acceptance criteria (MU1)

- [ ] All Python quality gates pass: `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q --vcr-record=none`.
- [ ] `/health` returns 200 without any user credentials (service-only).
- [ ] `/preflight` returns 200 with valid creds, 401 without creds, 403 with bad Zotero key.
- [ ] `/run` returns 401 if `X-Zotero-API-Key` missing.
- [ ] Existing single-user local dev still works when `AGT_ZOTERO_API_KEY` is set in `.env` (backwards-compat mode).
- [ ] No credentials appear in `structlog` output (grep test).
- [ ] LangGraph checkpoint inspection (`SELECT data FROM checkpoints LIMIT 1`) shows no credential bytes.

### MU2 — Frontend credential UI (0.5–1 day)

**Goal.** The add-on collects Zotero credentials (always) and LLM credentials (optional)
from the user and sends them as headers on every backend call.

#### Files to edit

| File | Change |
|---|---|
| `zotero-addon/src/host/prefs.ts` | Add `zoteroApiKey`, `zoteroLibraryId`, `zoteroLibraryType` (`user` \| `group`), `useCustomLlm`, `customLlmProvider`, `customLlmBaseUrl`, `customLlmModel`, `customLlmApiKey`. Default to empty. |
| `zotero-addon/src/ui/components/ConfigPanel.tsx` | Add a "Zotero Account" section (required for remote mode). Add a "LLM Override" section gated by a toggle. |
| `zotero-addon/src/client/backendClient.ts` | `buildHeaders` adds Zotero headers always; LLM headers only if `useCustomLlm`. Add `setUserCredentials(creds)` mutator. |
| `zotero-addon/src/ui/App.tsx` / hooks | Pipe prefs into the client constructor. |
| `zotero-addon/src/ui/components/FirstRunConfigCard.tsx` | First-run flow now prompts for Zotero credentials. LLM key remains optional. |
| Tests | Vitest for header serialization; assert no LLM headers when toggle is off. |

#### Acceptance criteria (MU2)

- [ ] All Zotero add-on quality gates pass: `npm ci && npm run lint && npm run build && npm run typecheck && npm run test`.
- [ ] Sending a `/run` without Zotero API key in prefs surfaces a clear error in the UI before hitting the network.
- [ ] Toggle "Use my own LLM key" shows the four LLM fields; switching off hides them and clears the headers.

### MU3 — Cloud Run reconfig (10 min)

- [ ] Remove user-specific secrets from the service:

  ```bash
  gcloud run services update sciagent --region=europe-west1 \
    --remove-secrets="AGT_ZOTERO_API_KEY,AGT_ZOTERO_LIBRARY_ID,AGT_BACKEND_API_KEY"
  ```

- [ ] Keep `AGT_LLM_API_KEY` bound (this is Adam's DeepSeek key, used as the default LLM).
- [ ] (Optional) Delete the Zotero/Backend secrets entirely in Secret Manager:

  ```bash
  gcloud secrets delete AGT_ZOTERO_API_KEY --quiet
  gcloud secrets delete AGT_ZOTERO_LIBRARY_ID --quiet
  gcloud secrets delete AGT_BACKEND_API_KEY --quiet
  ```

- [ ] Verify `/health` from a fresh `curl` (no `X-AGT-API-Key`) returns 200.
- [ ] Verify `/run` with no creds returns 401.

### MU4 — README + trust statement (30 min)

Add to root `README.md` a new section near the top:

```markdown
## Try the Hosted Demo

Public backend: `https://sciagent-ewpafdgfya-ew.a.run.app`

### Setup
1. Install the SciAgent Zotero add-on (XPI link).
2. Get a Zotero API key with read+write scope: <https://www.zotero.org/settings/keys/new>.
3. Find your Zotero user ID: <https://www.zotero.org/settings/keys> → top of page.
4. In the add-on → Settings → Connection:
   - Backend Mode: Remote
   - Backend URL: `https://sciagent-ewpafdgfya-ew.a.run.app`
   - Zotero API Key: from step 2
   - Zotero Library ID: from step 3
5. Click "Test Connection" — expect green.

### What the backend sees
- Your search queries
- Your Zotero credentials (transient — used to write to your library, never stored)
- The items it writes to your library (it does NOT read your existing library beyond duplicate detection)

### What the backend does NOT do
- Persist your Zotero credentials beyond a single request
- Log your credentials (structlog redaction enforced)
- Share your data with anyone besides the LLM provider (DeepSeek by default; configurable)

### LLM costs
- By default, LLM calls use the operator's DeepSeek key. The demo has a $10/month hard cap;
  when it's gone, the backend stops responding until next month.
- To bypass the limit, enable "Use my own LLM key" in add-on settings.

### This is a demo, not a hosted product.
- No SLA. The service may go offline at any time.
- No warranty. Use at your own risk.
- Source code: <https://github.com/AdamKrysztopa/sciagent>.
```

#### Acceptance criteria (MU4)

- [ ] Markdownlint passes on `README.md`.
- [ ] Manual: open `README.md` on GitHub web view, confirm renders correctly.

### MU5 — End-to-end multi-user smoke test (30 min)

- [ ] Create a second Zotero account (or use a friend's, with permission).
- [ ] From that account's add-on settings, point at the Cloud Run URL with the new credentials.
- [ ] Run a search → approve → verify the items land in the **second account's** library, not yours.
- [ ] Toggle on "Use my own LLM key" with a fresh DeepSeek key. Run a search. Verify in DeepSeek dashboard that the second account's key was charged, not yours.
- [ ] Toggle off "Use my own LLM key". Run a search. Verify your key was charged.

### MU6 — Monitoring (always-on)

- [ ] Check Cloud Run logs daily for the first week: `gcloud run services logs tail sciagent --region=europe-west1 | grep -E "ERROR|429|401"`.
- [ ] Cloud Run dashboard: watch p95 latency, instance count, request count. Spike = someone found the URL.
- [ ] If LLM cost trend looks bad, ratchet down `--max-instances` or add per-IP rate limit (slowapi already in deps).

---

## Risk Register

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| LLM cost blowup from an abusive user | Medium | High | Budget alert at 50 zł (50% of $10 cap); manual revoke by adding `AGT_BACKEND_API_KEY` back to require an invite token. |
| Bot scanning Cloud Run URLs hits /run | Low | Medium | `/run` requires valid Zotero creds; bots without those get 401 cheap. |
| Credential leak via logs | Low | Critical | Add a unit test that asserts `Zotero-API-Key` substring never appears in `structlog` output for any test request. |
| Credential leak via LangGraph checkpoint | Low | Critical | Contextvar pattern (above) ensures creds never enter state. Add a checkpoint-inspection test. |
| User confused about "where do my papers go" | High | Low | README diagram + first-run dialog explicitly state "items will be written to YOUR Zotero library at ID X". |
| User uses wrong library ID | Medium | Medium | Preflight call validates the ID resolves before any write. Surface "Library `<name>` (user/group `<id>`)" in the add-on after a successful preflight. |

---

## Out of Scope (Phase 3+ if needed)

- Multi-tenant rate limiting (per-Zotero-key, not per-IP) — not needed until abuse appears.
- Per-user usage dashboards — needs a database. The demo is fire-and-forget.
- OAuth-based Zotero auth (instead of raw API keys) — friendlier but requires server-side OAuth flow. Demo uses raw keys for now.
- Terraform / IaC — useful once we have > 1 environment.
- Custom domain — see M10 in `actionable-plan.md`.

---

## Tracker

### Current Status

- Single-user deploy ✅ done 2026-05-17 (M0–M4 of `actionable-plan.md`).
- Current focus: **MU1 — Backend credential injection**

### Phase Tracker

- [ ] **MU0** — Verify cost guardrails
- [ ] **MU1** — Backend credential injection
- [ ] **MU2** — Frontend credential UI
- [ ] **MU3** — Cloud Run reconfig
- [ ] **MU4** — README + trust statement
- [ ] **MU5** — End-to-end smoke test
- [ ] **MU6** — Monitoring (continuous)

### Tracker Rules

1. MU1 must land before MU2 (frontend needs the new backend contract).
2. MU3 must NOT run before MU1 + MU2 are deployed — removing the Zotero secrets while the backend still reads them would break the live service.
3. MU4 happens last so the README matches the live behavior.

---

## See Also

- `docs/actionable-plan.md` — single-user deploy plan (M0–M4 done, M5–M10 superseded by this file).
- `docs/api.md` — REST contract; update headers section as part of MU1.
- `src/agt/api/app.py` — endpoint definitions.
- `src/agt/zotero/preflight.py` — preflight logic to refactor.
- `zotero-addon/src/host/prefs.ts` — prefs schema to extend.
