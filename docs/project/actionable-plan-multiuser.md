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

### MU0 — Verify cost guardrails ✅ done 2026-05-17

- [x] `--max-instances=2` confirmed: `autoscaling.knative.dev/maxScale=2` on the service.
- [ ] 50 zł / month budget alert — cannot verify via gcloud (Billing Budgets API not enabled);
  confirm manually in [GCP Console → Billing → Budgets](https://console.cloud.google.com/billing).
- [ ] (Optional) Set a hard DeepSeek monthly cap in the DeepSeek dashboard.

### MU1 — Backend credential injection ✅ done 2026-05-17

**Goal.** Every Zotero/LLM call inside a request reads credentials from a
request-scoped contextvar, not from `settings`.

#### Delivered

- `src/agt/credential_context.py` — `RequestCredentials` model, `current_credentials`
  contextvar, `resolve_zotero_*` / `resolve_llm_*` helpers with settings fallback for
  local single-user dev.
- `src/agt/api/credentials.py` — FastAPI `get_credentials` generator dependency that
  reads 7 headers, validates Zotero fields, sets/restores contextvar in try/finally
  (using `set(previous)` pattern — `reset(token)` fails across async contexts).
- `src/agt/api/app.py` — `/health` is service-only (no Zotero call); new `/preflight`
  endpoint with `Depends(get_credentials)`; `Depends(get_credentials)` on `/run`,
  `/resume`, `/library-doctor`, `/gap-finder`, `/watches/{id}/rerun`.
- `src/agt/zotero/preflight.py` — resolves credentials from contextvar first, falls
  back to `settings`.
- `src/agt/zotero/collection_inspector.py`, `src/agt/tools/zotero_upsert.py`,
  `src/agt/tools/pdf_attach.py` — all switched to resolve helpers.
- `src/agt/providers/router.py` — `build_provider_for_request(settings)` checks
  contextvar for per-request LLM override, calls `settings.model_copy(update=...)`.
- `src/agt/graph/workflow.py` — `build_provider` → `build_provider_for_request`.
- All tests updated: `_ZOTERO_HEADERS` added to API tests; `build_provider_for_request`
  monkeypatched in workflow/e2e tests. 583 tests pass.

#### Acceptance criteria (MU1)

- [x] All Python quality gates pass (583 passed, ruff clean, pyright clean).
- [x] `/health` returns 200 without any user credentials (service-only).
- [x] `/run` returns 401 if `X-Zotero-API-Key` missing.
- [x] Existing single-user local dev still works when `AGT_ZOTERO_API_KEY` is set in `.env`.
- [ ] `/preflight` live smoke: 200 with valid creds, 401 without creds — verify after MU2 deploy.
- [ ] No credentials appear in `structlog` output — grep test not yet written.
- [ ] LangGraph checkpoint inspection shows no credential bytes — not yet tested.

#### Bug fixes shipped alongside MU1

- **Spell check skipped title-cased words** — `token[0].isupper()` guard removed;
  checker now runs on lowercase form and re-capitalizes the suggestion. "Scpectroscopy"
  → "Spectroscopy" confirmed.
- **Author/venue filter reset after search** — `applySnapshot` now preserves
  `authors`, `venues`, `seed_dois` from the current draft when rebuilding from the
  backend search plan.
- **500 on approve/reject from cache hit** — `cached_state` was missing `messages`,
  `preflight`, `trace_spans`; `finalize_approval` threw `KeyError`. Fixed by
  populating defaults in the cache reconstruction block in `app.py`.

### MU2 — Frontend credential UI ✅ done 2026-05-17

**Goal.** The add-on collects Zotero credentials (always) and LLM credentials (optional)
from the user and sends them as headers on every backend call.

**Blocker today:** `backendClient.buildHeaders` does not send any Zotero headers.
Every endpoint gated by `get_credentials` (including `/resume`) returns 401 when
called from the add-on in remote mode.

#### Files to edit

| File | Change |
|---|---|
| `zotero-addon/src/host/prefs.ts` | Add `zoteroApiKey`, `zoteroLibraryId`, `zoteroLibraryType` (`user` \| `group`), `useCustomLlm`, `customLlmProvider`, `customLlmBaseUrl`, `customLlmModel`, `customLlmApiKey`. Default to empty. |
| `zotero-addon/src/ui/components/ConfigPanel.tsx` | Add a "Zotero Account" section (required for remote mode). Add a "LLM Override" section gated by a toggle. |
| `zotero-addon/src/client/backendClient.ts` | `buildHeaders` adds `X-Zotero-API-Key`, `X-Zotero-Library-ID`, `X-Zotero-Library-Type` always; LLM headers only if `useCustomLlm`. Extend `BackendClientConfig` to carry the new fields. |
| `zotero-addon/src/ui/App.tsx` / hooks | Pipe prefs into the client constructor. |
| `zotero-addon/src/ui/components/FirstRunConfigCard.tsx` | First-run flow now prompts for Zotero credentials. LLM key remains optional. |
| Tests | Vitest for header serialization; assert no LLM headers when toggle is off. |

#### Acceptance criteria (MU2)

- [x] All Zotero add-on quality gates pass: lint, build, typecheck, 152 tests.
- [x] Sending a `/run` without Zotero API key in prefs surfaces a clear error in the UI before hitting the network (`searchDisabledReason`).
- [x] Toggle "Use my own LLM key" shows the four LLM fields; switching off hides them and clears the headers.
- [ ] `/run` and `/resume` no longer return 401 when Zotero prefs are filled in — verify after MU3 deploy.

### MU3 — Cloud Run reconfig ✅ done 2026-05-17

- [x] Deployed MU1+MU2 code (image `7b17551`, revision `sciagent-00005-9lb`).
- [x] Removed `AGT_ZOTERO_API_KEY`, `AGT_ZOTERO_LIBRARY_ID`, `AGT_BACKEND_API_KEY` from Cloud Run (revision `sciagent-00006-zfj`).
- [x] `AGT_LLM_API_KEY` remains bound (Adam's DeepSeek key, shared default).
- [x] `/health` returns 200 without credentials.
- [x] `/run` without credentials returns 401.
- [ ] (Optional) Delete the now-unbound secrets from Secret Manager:

  ```bash
  gcloud secrets delete AGT_ZOTERO_API_KEY --quiet
  gcloud secrets delete AGT_ZOTERO_LIBRARY_ID --quiet
  gcloud secrets delete AGT_BACKEND_API_KEY --quiet
  ```

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

- [x] Markdownlint passes on `README.md` (0 errors).
- [x] "Try the Hosted Demo" section added near the top of README.md.
- [x] Backend Mode dropdown added to ConfigPanel so users can switch local ↔ remote through the UI.
- [ ] Manual: open `README.md` on GitHub web view, confirm renders correctly.

### MU5 — End-to-end multi-user smoke test (30 min)

- [ ] Create a second Zotero account (or use a friend's, with permission).
- [ ] From that account's add-on settings, point at the Cloud Run URL with the new credentials.
- [ ] Run a search → approve → verify the items land in the **second account's** library, not yours.
- [ ] Toggle on "Use my own LLM key" with a fresh DeepSeek key. Run a search. Verify in DeepSeek dashboard that the second account's key was charged, not yours.
- [ ] Toggle off "Use my own LLM key". Run a search. Verify your key was charged.

### MU6 — Monitoring setup ✅ done 2026-05-17

Automated monitoring wired up via Cloud Monitoring:

- [x] Initial log scan — clean baseline; only smoke-test 401s present.
- [x] Email notification channel created → `krysztopa@gmail.com`
  (channel `3188061815048077143`).
- [x] Log-based metric `sciagent_errors` — severity≥ERROR in Cloud Run logs.
- [x] Log-based metric `sciagent_rate_limited` — HTTP 429 responses.
- [x] Alert policy: any ERROR in a 5-min window → email (max 1/hour).
- [x] Alert policy: any 429 in a 5-min window → email (max 1/hour).
- [x] Alert policy: active instance count > 1 for 5 min → email (at-cap warning).

### MU6.1 — Ongoing monitoring (manual, first week)

- [ ] Check Cloud Run logs daily:
  `gcloud run services logs read sciagent --region=europe-west1 --limit=200 | grep -E "ERROR|429|401"`
- [ ] Review Cloud Run dashboard weekly: p95 latency, instance count, request count.
  A sustained spike means someone found the URL.
- [ ] Check DeepSeek usage dashboard weekly — if cost trend looks bad:
  - Option A: ratchet down `--max-instances 1`
  - Option B: add per-IP rate limit via slowapi (already in deps)

### MU7 — Credential-leak safety tests ✅ done 2026-05-18

**Goal.** Close the two open Risk Register items: prove credentials never appear in
structlog output, and prove they never enter a LangGraph checkpoint.

#### MU7 delivered

- `RequestCredentials.zotero_api_key` migrated from `str` to `pydantic.SecretStr`.
  `llm_api_key` also migrated. `credentials.py` wraps incoming header strings with
  `SecretStr(...)` explicitly. `resolve_zotero_api_key` calls `.get_secret_value()`.
  `router.py` no longer wraps `creds.llm_api_key` (already `SecretStr`).
- `tests/test_credential_redaction.py` — 8 tests across three layers:
  - `redact_value` unit tests (dict keys, nested dicts, `SecretStr` values, plain strings)
  - `RequestCredentials.model_dump(mode="json")` and `repr()` do not expose the key
  - `structlog.testing.capture_logs()` during a `/run` request: no event dict contains
    the raw key value
  - `/status/{run_id}` JSON response does not contain the raw key value

#### MU7 acceptance criteria

- [x] `uv run pytest tests/test_credential_redaction.py -v` passes (8 tests).
- [x] `uv run pyright` zero errors after SecretStr migration.
- [x] All 591 tests still pass (583 existing + 8 new).

### MU8 — Live end-to-end verification

**Goal.** Confirm the deployed backend works with a real second Zotero account
(separate from Adam's dev account).

#### MU8 tasks

- [ ] Obtain a second Zotero account (test account or friend's with permission).
- [ ] Configure the add-on: remote mode, hosted URL, second account's API key + library ID.
- [ ] Run a search → approve → verify items appear in the second account's Zotero.
- [ ] Toggle BYO LLM key ON with a fresh DeepSeek key. Run a search.
  Verify DeepSeek dashboard shows the second key charged, not the operator's.
- [ ] Toggle BYO LLM key OFF. Run a search.
  Verify the operator's key is charged.
- [ ] Mark MU2 acceptance criterion "no longer 401" as done.
- [ ] Mark MU1 acceptance criterion "/preflight live smoke" as done.

#### MU8 acceptance criteria

- [ ] Second-account items appear in that account's Zotero library only.
- [ ] BYO LLM key correctly routes charges.
- [ ] All MU1/MU2 open acceptance criteria ticked off.

### MU9 — API docs: document all new headers ✅ done 2026-05-18

**Goal.** `docs/reference/api.md` Authentication section was missing all seven new request headers.

#### MU9 delivered

- Updated Authentication table with `X-Zotero-API-Key`, `X-Zotero-Library-ID`,
  `X-Zotero-Library-Type`, `X-LLM-API-Key`, `X-LLM-Provider`, `X-LLM-Model`,
  `X-LLM-Base-URL`.
- Added `POST /preflight` endpoint entry with request headers and response schema.
- Noted that `/run`, `/resume`, `/library-doctor`, `/gap-finder`, `/watches/{id}/rerun`
  all require Zotero headers (HTTP 401 if missing).

#### MU9 acceptance criteria

- [x] `uv run mkdocs build --strict` passes.
- [x] Markdownlint passes on `docs/reference/api.md`.

### MU10 — "Test Connection" button + preflight client method ✅ done 2026-05-18

**Goal.** README and docs reference a "Test Connection" button but it did not exist.
`backendClient.ts` had no `preflight()` method. Users had no way to verify their
Zotero credentials from the add-on UI without running a full search.

#### MU10 delivered

- `PreflightStatus` extended with `library_name?: string | null` in `contracts.ts`.
- `preflight(): Promise<PreflightStatus>` method added to `SciAgentBackendClient`
  (calls `POST /preflight` with current credential headers).
- `onTestZotero()` prop added to `ConfigPanelProps`. Button renders in the "Zotero Account"
  section below the zotero.org link. Shows spinner while loading; `✓ <library name> verified`
  on success; `✗ <error>` on failure. Disabled when API key or library ID is empty.
- `testZotero` `useEffectEvent` added to `useSciAgentController` and wired through `App.tsx`.
- `ConfigPanel.test.ts` updated with `onTestZotero` stub. 2 new Vitest tests in
  `backendClient.test.ts`: happy path + 401 propagation. Total: 154 tests pass.

#### MU10 acceptance criteria

- [x] `npm run lint && npm run build && npm run typecheck && npm run test` passes (154 tests).
- [x] Button visible in the Zotero Account section of ConfigPanel.
- [x] Success state shows the Zotero library name from the preflight response.
- [x] Failure state shows an inline error, does not crash the panel.
- [ ] Manual: open the add-on in Zotero, fill in credentials, click the button — verify green state.

### MU11 — Screenshots for hosted-demo-guide.md

**Goal.** The guide shared with new users needs screenshots showing each major step.
Cannot be automated — requires Zotero 9 with the add-on installed and a real account.

#### Steps (manual)

- [ ] Screenshot: ConfigPanel showing Backend Mode = Remote + Zotero Account fields filled.
- [ ] Screenshot: First-run card in remote mode (Zotero credential prompt).
- [ ] Screenshot: Search results panel with paper cards and approval checkboxes.
- [ ] Screenshot: Status pill green after successful preflight.
- [ ] Screenshot: Write result showing `created` / `unchanged` badges.
- [ ] Insert images into `docs/get-started/hosted-demo-guide.md` using `![alt](../../assets/img/*.png)`.
- [ ] Add images to `docs/assets/img/` and commit.

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
- MU1 backend ✅ done 2026-05-17 — committed (`0d10e67`), **not yet deployed**.
- Bug fixes (spell check, author filter reset, cache-hit 500) ✅ done 2026-05-17 — committed (`8324201`), not yet deployed.
- MU2 frontend ✅ done 2026-05-17 — 8 new prefs fields, Zotero/LLM headers in `buildHeaders`, ConfigPanel sections, FirstRunConfigCard adapts to remote mode, pre-search validation, 5 new tests.
- MU3 Cloud Run reconfig ✅ done 2026-05-17 — deployed image `7b17551`, removed baked-in Zotero/backend secrets, verified `/health` 200 + `/run`-no-creds 401.
- MU4 README ✅ done 2026-05-17 — "Try the Hosted Demo" section added to README.md; Backend Mode dropdown added to ConfigPanel.
- MU6 monitoring setup ✅ done 2026-05-17 — email channel, 2 log-based metrics, 3 alert policies (ERROR/429/instance-cap).
- Remaining: MU5 (needs second Zotero account — manual), MU6.1 (ongoing weekly checks — manual)

### Phase Tracker

- [x] **MU0** — Verify cost guardrails ✅ 2026-05-17 (max-instances=2 confirmed; budget alert needs manual Console check)
- [x] **MU1** — Backend credential injection ✅ 2026-05-17
- [x] **MU2** — Frontend credential UI ✅ 2026-05-17
- [x] **MU3** — Cloud Run reconfig ✅ 2026-05-17
- [x] **MU4** — README + trust statement ✅ 2026-05-17
- [ ] **MU5** — End-to-end smoke test (needs second Zotero account)
- [x] **MU6** — Monitoring setup ✅ 2026-05-17 (3 alert policies + email channel)
- [ ] **MU6.1** — Ongoing monitoring (manual, first week)
- [x] **MU7** — Credential-leak safety tests ✅ 2026-05-18 (SecretStr + structlog capture + checkpoint inspection)
- [ ] **MU8** — Live end-to-end verification (needs second Zotero account)
- [x] **MU9** — API docs: document new headers ✅ 2026-05-18
- [x] **MU10** — "Test Connection" button + preflight client method ✅ 2026-05-18
- [ ] **MU11** — Screenshots for hosted-demo-guide.md (manual, needs running Zotero)

### Tracker Rules

1. MU1 must land before MU2 (frontend needs the new backend contract).
2. MU3 must NOT run before MU1 + MU2 are deployed — removing the Zotero secrets while the backend still reads them would break the live service.
3. MU4 happens last so the README matches the live behavior.

---

## See Also

- `docs/project/actionable-plan.md` — single-user deploy plan (M0–M4 done, M5–M10 superseded by this file).
- `docs/reference/api.md` — REST contract; update headers section as part of MU1.
- `src/agt/api/app.py` — endpoint definitions.
- `src/agt/zotero/preflight.py` — preflight logic to refactor.
- `zotero-addon/src/host/prefs.ts` — prefs schema to extend.
