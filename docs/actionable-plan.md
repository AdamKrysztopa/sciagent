# SciAgent Actionable Plan — P10 (GCP Prerequisites: Cheap LLM + Docker Cloud Readiness)

> **Last audit: 2026-05-17** — All P0–P9 stories complete (see
> [actionable-plan-done-3.md](actionable-plan-done-3.md) and earlier archives).
>
> This plan covers **P10: everything that must be true in the codebase and locally
> before the GCP deployment plan (`docs/actionable-plan-gcp.md`) makes sense.**
> No GCP commands here — this is the application story. The deployment plan is the
> infrastructure story. Both must pass before GCP works.
>
> Canonical execution tracker. Update done/not done state here first.
> Historical completed work stays in `actionable-plan-done*.md` — do not re-open closed items.

## Design Philosophy

**Cheap by default.** The codebase already supports every major LLM provider
through a unified `AGT_LLM_PROVIDER` / `AGT_LLM_BASE_URL` / `AGT_LLM_API_KEY`
config surface. The `openai-compatible` adapter covers DeepSeek, Groq (via their
OpenAI-compat endpoint), Together AI, LM Studio, and Ollama — no new code
required for any of them. What's missing is (a) the operator running the actual
key setup, (b) a startup log line confirming which provider is active (critical
for debugging cloud cold-starts), and (c) the Docker image being production-ready
for Cloud Run.

**One variable to change.** A researcher self-hosting on GCP should be able to
swap LLM providers by changing three env vars (`AGT_LLM_PROVIDER`,
`AGT_LLM_BASE_URL`, `AGT_LLM_API_KEY`) and restarting the container. Zero code
changes. P10 verifies this end-to-end with DeepSeek as the reference cheap
provider.

**Docker-ready before GCP.** Cloud Run is Docker. If the image doesn't work
locally against DeepSeek with the right env vars, it won't work in the cloud.
P10 is the local validation pass that makes M4 of the GCP plan a 10-minute
operation instead of an afternoon of debugging.

---

## What Is Already Done (Code Audit — 2026-05-17)

After auditing the codebase, the following items from the original prereq plan
are **already complete**. They are listed here so they are not re-implemented.

| Item | Location | Status |
|---|---|---|
| `AGT_LLM_BASE_URL` config field | `src/agt/config.py:148` | ✅ done |
| `AGT_LLM_API_KEY` config field | `src/agt/config.py:143` | ✅ done |
| `AGT_LLM_PROVIDER` auto-detection | `src/agt/config.py:478` | ✅ done |
| `openai_compatible` provider with `base_url` | `src/agt/providers/openai_compatible.py` | ✅ done |
| Router wires `llm_base_url` → `openai-compatible` | `src/agt/providers/router.py:132` | ✅ done |
| `.env.example` DeepSeek recipe | `.env.example:25-28` | ✅ done |
| Tests: base_url config + routing | `tests/test_config.py:203`, `tests/test_providers.py:365` | ✅ done |
| CORS via `AGT_CORS_ALLOWED_ORIGINS` | `src/agt/config.py:431`, `src/agt/api/app.py:299` | ✅ done |
| `AGT_BACKEND_API_KEY` auth middleware | `src/agt/config.py:78` | ✅ done |

**Do not re-implement any of the above.** If a future story contradicts this
table, verify by reading the current file before acting.

---

## Execution Tracker

### Current Status

- All P0–P9 milestones complete as of 2026-05-14.
- Current focus: **C7 — Commit + CI green**.
- Last completed: **C6 (2026-05-17)** — E2E Zotero → Docker test passed; idempotent write to Zotero collection confirmed.

### P10 Status

| ID  | Story                                          | Effort  | Owner                    | Status      |
| --- | ---------------------------------------------- | ------- | ------------------------ | ----------- |
| C1  | Cheap LLM account + key                        | ~15 min | you (operational)        | ✅ done (2026-05-17) |
| C2  | Startup LLM config log line                    | ~30 min | python-backend-engineer  | ✅ done (2026-05-17) |
| C3  | Dockerfile: honor `$PORT`                      | ~5 min  | python-backend-engineer  | ✅ done (2026-05-17) |
| C4  | Create `.dockerignore`                         | ~5 min  | python-backend-engineer  | ✅ done (2026-05-17) |
| C5  | Local Docker smoke test with cheap LLM         | ~15 min | you (operational)        | ✅ done (2026-05-17) |
| C6  | End-to-end Zotero → Docker test                | ~20 min | you (operational)        | ✅ done (2026-05-17) |
| C7  | Commit + CI green                              | ~10 min | python-backend-engineer  | not started |

**Total estimate: ~1.5 hours.**

---

## Milestones

### C1 — Cheap LLM Account & Key (15 minutes)

**Goal.** A working API key for a cheap OpenAI-compatible LLM provider stored in
your password manager and smoke-tested from the terminal.

**Recommended provider: DeepSeek V3** — `$0.14 / $0.28 per million tokens`
(in/out). At SciAgent's ~300k tokens/month solo volume, that is ~$0.07/month.
One $5 top-up covers roughly 18 months of solo use.

**Alternatives** (same `openai-compatible` adapter, zero code changes):
- **Groq** — free tier (`llama-3.3-70b`, `deepseek-r1-distill-*`). Rate-limited but
  usable for solo dev. Set `AGT_LLM_BASE_URL=https://api.groq.com/openai/v1`.
- **Ollama** — fully local, free, no key needed. Use `AGT_LLM_PROVIDER=ollama`.
  Slower cold start; no cloud cost at all.
- **OpenAI `gpt-4o-mini`** — $0.15/$0.60 per M tokens. Already works; no new setup.

**DeepSeek steps:**

- [ ] **C1.1** Sign up at <https://platform.deepseek.com> (Google OAuth works).
- [ ] **C1.2** Top up $5. This covers ~30 million tokens of `deepseek-chat` — over
  a year of solo SciAgent use.
- [ ] **C1.3** Create an API key. Save to password manager as `DEEPSEEK_API_KEY`.
- [ ] **C1.4** Verify with a direct curl (replace `<KEY>`):

  ```bash
  curl https://api.deepseek.com/chat/completions \
    -H "Authorization: Bearer <KEY>" \
    -H "Content-Type: application/json" \
    -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"Say hi"}],"max_tokens":10}'
  ```

  Expect 200 JSON. `401` = wrong key. `402` = balance zero (top up first).

- [ ] **C1.5** Verify the SciAgent env var wiring locally (no Docker):

  ```bash
  AGT_LLM_PROVIDER=openai-compatible \
  AGT_LLM_BASE_URL=https://api.deepseek.com/v1 \
  AGT_LLM_MODEL=deepseek-chat \
  AGT_LLM_API_KEY=<KEY> \
  uv run sciagent-server --port 57322 &

  curl -s http://127.0.0.1:57322/health | python3 -m json.tool
  kill %1
  ```

  Expect `/health` to return 200. If `llm_provider` is not in the health response,
  that is what C2 fixes.

**Cost: $5 one-time.**

---

### C2 — Startup LLM Config Log Line (30 minutes)

**Goal.** `create_app()` in `src/agt/api/app.py` emits one structured log line at
`INFO` level showing the effective LLM provider, model, and base URL. When
DeepSeek is on, the log is obvious. When debugging a cold-start failure on Cloud
Run, this is the first thing to check.

**Why this doesn't exist yet.** `get_settings()` loads and validates settings but
never logs the resolved LLM config. `create_app()` calls `get_settings()` at line
297 but only uses it for CORS and rate limits — nothing is logged.

**Implementation target:** `src/agt/api/app.py`, inside `create_app()`, right
after line 297 (`_settings = get_settings()`).

- [ ] **C2.1** Add a `structlog` import and log call:

  ```python
  import structlog as _structlog

  _log = _structlog.get_logger()

  def create_app() -> FastAPI:
      app = FastAPI(title="SciAgent API", version="0.1.0")
      _settings = get_settings()

      # Log the effective LLM config at startup — visible in Cloud Run logs.
      _log.info(
          "sciagent_startup",
          llm_provider=_settings.resolved_llm_provider,
          llm_model=_settings.runtime.model_name,
          llm_base_url=_settings.llm_base_url,  # not a secret; safe to log
      )
      # ... rest of create_app unchanged
  ```

  Place these additions at the top of the file and inside `create_app()` only.
  Do not move or restructure any existing code.

- [ ] **C2.2** Confirm the redaction processor does NOT redact `llm_base_url` (it
  shouldn't — the processor in `config.py:546` only redacts keys containing
  `"key"`, `"token"`, `"secret"`, `"authorization"`, or `"password"`).

- [ ] **C2.3** Run the quality gates:

  ```bash
  uv run ruff check . && uv run ruff format --check . && uv run pyright
  uv run pytest -q --vcr-record=none
  ```

  No new failures expected. The existing 563+ tests must still pass.

- [ ] **C2.4** Manual verify: `uv run sciagent-server --port 57322` with DeepSeek
  env vars. Confirm the log line appears in stderr/stdout with the correct values.

**Pitfall:** Do not add `structlog` as a new dependency — it is already in
`pyproject.toml` (used throughout `src/agt/`). Import it directly.

---

### C3 — Dockerfile: Honor `$PORT` (5 minutes)

**Goal.** The container listens on whatever port Cloud Run sets via `$PORT`
(default 8080). The current `CMD` hardcodes `--port 8000`, which causes Cloud Run
health checks to fail silently on the first deploy.

**Current state** (`Dockerfile:9`):

```dockerfile
CMD ["uv", "run", "uvicorn", "agt.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **C3.1** Change to:

  ```dockerfile
  CMD ["sh", "-c", "uv run uvicorn agt.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
  ```

  The `${PORT:-8080}` idiom: uses Cloud Run's injected `$PORT` if set, falls
  back to 8080 for local Docker runs.

- [ ] **C3.2** Verify the base image is `python:3.14-slim` (it already is —
  confirm with `head -1 Dockerfile`).

- [ ] **C3.3** Verify `uv sync --frozen` is in the build (already is — `Dockerfile:6`).

- [ ] **C3.4** Build and confirm the image starts without errors:

  ```bash
  docker build -t sciagent:port-test .
  docker run --rm -p 8080:8080 -e PORT=8080 \
    -e AGT_LLM_PROVIDER=openai-compatible \
    -e AGT_LLM_BASE_URL=https://api.deepseek.com/v1 \
    -e AGT_LLM_MODEL=deepseek-chat \
    -e AGT_LLM_API_KEY=<KEY> \
    sciagent:port-test &
  sleep 3 && curl -s http://localhost:8080/health
  docker stop $(docker ps -q --filter ancestor=sciagent:port-test)
  ```

**Cost: $0.**

---

### C4 — Create `.dockerignore` (5 minutes)

**Goal.** Reduce the Docker build context from the full repo to only what the
backend needs. Target: image < 300 MB. Without `.dockerignore`, `tests/`,
`zotero-addon/` (with `node_modules/`), and `docs/` all get copied into the
build context, bloating the image and slowing Cloud Build.

- [ ] **C4.1** Create `.dockerignore` at repo root:

  ```
  .git
  .github
  .venv
  __pycache__
  *.pyc
  *.pyo
  .pytest_cache
  .ruff_cache
  .mypy_cache
  tests/
  zotero-addon/
  docs/
  examples/
  *.md
  .env
  .env.*
  !.env.example
  htmlcov/
  .coverage
  build/dist/
  build/work/
  ```

- [ ] **C4.2** Build and measure image size:

  ```bash
  docker build -t sciagent:size-check .
  docker images sciagent:size-check --format "{{.Size}}"
  ```

  Target: **< 500 MB**. The FastAPI + LangGraph + httpx + pyzotero stack lands at
  ~467 MB. If over 700 MB, `streamlit`/`pandas`/`pyright` got pulled in — confirm
  the Dockerfile uses `uv sync --frozen --no-dev` and those packages are not in
  `[project.dependencies]`.

**Cost: $0.**

---

### C5 — Local Docker Smoke Test with Cheap LLM (15 minutes)

**Goal.** The container runs with DeepSeek env vars, `/health` returns 200, and a
real `/run` query comes back with results — including evidence that DeepSeek was
actually called (via the C2 startup log line and the DeepSeek dashboard).

- [ ] **C5.1** Create `.env.docker` at repo root (**add to `.gitignore`**,
  never commit):

  ```bash
  AGT_BACKEND_API_KEY=local-test-key-replace-me
  AGT_LLM_PROVIDER=openai-compatible
  AGT_LLM_BASE_URL=https://api.deepseek.com/v1
  AGT_LLM_MODEL=deepseek-chat
  AGT_LLM_API_KEY=<your-deepseek-key>
  AGT_ZOTERO_API_KEY=<your-zotero-key>
  AGT_ZOTERO_LIBRARY_ID=<your-library-id>
  AGT_LOG_LEVEL=INFO
  ```

- [ ] **C5.2** Run:

  ```bash
  docker run --rm -p 8080:8080 --env-file .env.docker sciagent:size-check
  ```

  First line to look for in logs: `sciagent_startup` with
  `llm_provider=openai-compatible` and `llm_base_url=https://api.deepseek.com/v1`
  (the C2 log line). If that line is missing, C2 isn't complete.

- [ ] **C5.3** In a second terminal, hit `/health`:

  ```bash
  curl -H "X-AGT-API-Key: local-test-key-replace-me" \
       -H "X-AGT-Client-ID: smoke-test" \
       http://localhost:8080/health
  ```

  Expect 200 JSON.

- [ ] **C5.4** Run a real search:

  ```bash
  curl -X POST http://localhost:8080/run \
    -H "X-AGT-API-Key: local-test-key-replace-me" \
    -H "X-AGT-Client-ID: smoke-test" \
    -H "Content-Type: application/json" \
    -d '{"query":"retrieval augmented generation","collection_name":"SciAgent Docker Test","limit":5}'
  ```

  Expect a `run_id` and 5 results. Verify in logs that the query-rewrite step
  hit DeepSeek (look for a log line referencing the LLM call).

- [ ] **C5.5** Check the DeepSeek dashboard at <https://platform.deepseek.com>.
  Expect 1–3 API calls and ~$0.0001 of spend. If spend is zero, query rewriting
  silently fell through — check `AGT_LLM_API_KEY` is set correctly.

**Cost: ~$0.0001.**

---

### C6 — End-to-End Zotero → Docker Test (20 minutes)

**Goal.** The Zotero add-on talks to the local Docker container and completes a
full search → approve → write cycle. This proves the cloud path before any GCP
cost is incurred.

- [ ] **C6.1** Open Zotero. Confirm the SciAgent add-on is installed (XPI from
  `zotero-addon/build/sciagent-zotero-addon.xpi`).

- [ ] **C6.2** In Zotero → Tools → SciAgent → Settings → Connection:
  - Backend Mode: **Remote** (`backendMode: "remote"` bypasses the binary path).
  - Backend URL: `http://localhost:8080`.
  - Backend API Key: `local-test-key-replace-me`.

- [ ] **C6.3** Click "Test Connection" — expect green.

- [ ] **C6.4** Run a search from the main-window workspace. Approve 2–3 papers.
  Write to a test collection ("SciAgent E2E Test" — do not pollute a real
  collection).

- [ ] **C6.5** Verify the items appeared in Zotero. Check the per-item outcome
  (created / unchanged) shown in the add-on UI.

- [ ] **C6.6** Re-run the same search. The second write must report `unchanged`
  for every item (idempotent upsert working).

- [ ] **C6.7** Tear down: stop the Docker container, delete the test Zotero
  collection.

**Cost: $0 (local Docker, no GCP).**

---

### C7 — Commit + CI (10 minutes)

**Goal.** The three code changes (C2, C3, C4) land on `main` with CI green.

- [ ] **C7.1** Stage only the changed files:

  ```bash
  git add src/agt/api/app.py Dockerfile .dockerignore
  ```

- [ ] **C7.2** Run the full local gate before committing:

  ```bash
  uv run ruff check . && uv run ruff format --check . && uv run pyright
  uv run pytest -q --vcr-record=none
  ```

  All 563+ existing tests must pass. The `.dockerignore` and `Dockerfile` changes
  are not covered by the Python suite — that is expected.

- [ ] **C7.3** Commit:

  ```bash
  git commit -m "feat(p10): startup LLM log, Dockerfile \$PORT, .dockerignore"
  ```

- [ ] **C7.4** Push and verify CI passes all three jobs: `python-quality`,
  `zotero-addon-quality`, `docs-quality`, and `docker-build`. The `docker-build`
  job in `ci.yml` will now benefit from `.dockerignore`.

**Cost: $0 (CI is free).**

---

## Definition of Done

All C1–C7 boxes checked. To prove it, you must be able to:

1. Show a passing CI run for the commit that adds C2/C3/C4.
2. Run `docker run ... sciagent:size-check` with DeepSeek env vars and see the
   `sciagent_startup` log line with `llm_provider=openai-compatible`.
3. Hit `/health` and `/run` successfully against that container.
4. Run an end-to-end Zotero search-approve-write against the local Docker container.
5. Show the DeepSeek dashboard with non-zero usage.

When all five are true, **stop**. Switch to `docs/actionable-plan-gcp.md` and
start with M0.

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| DeepSeek API hiccup during smoke test | Low | Use Groq free tier as a same-day fallback — same adapter, different `AGT_LLM_BASE_URL`. |
| `deepseek-chat` model name changes | Low | Check <https://platform.deepseek.com/models>. The current name is `deepseek-chat` (not `deepseek-v3`). |
| Docker image > 300 MB despite `.dockerignore` | Low | Confirm `uv sync --frozen` doesn't pull in `[keywords]`/`[rerank]` extras. Check `pyproject.toml` optional groups. |
| C2 log line triggers the redaction processor | Very low | `llm_base_url` doesn't contain `"key"`, `"token"`, or `"secret"`. Verified against `config.py:546`. |
| `.env.docker` committed accidentally | Medium | Add it to `.gitignore` immediately in C5.1 before populating it. |

---

## Common Pitfalls

- **`AGT_LLM_PROVIDER` not set, only `AGT_LLM_BASE_URL`.** The auto-detection in
  `config.py:483` handles this: when `llm_base_url is not None` and no explicit
  provider is set, it resolves to `openai-compatible`. Still, set it explicitly in
  `.env.docker` to be unambiguous.
- **`AGT_LLM_BASE_URL=https://api.deepseek.com` without `/v1`.** The correct base
  for the OpenAI-compat path is `https://api.deepseek.com/v1`. Without `/v1`,
  the SDK double-paths and gets 404.
- **`AGT_LLM_MODEL` not set.** The default for `openai-compatible` in
  `_PROVIDER_DEFAULT_MODELS` is `gpt-4o-mini` (`config.py:28`). DeepSeek will
  reject this model name. Always set `AGT_LLM_MODEL=deepseek-chat` explicitly.
- **Forgetting `-n` on `echo` when creating env files.** Trailing newlines in API
  keys cause 401s with no useful error. Always: `echo -n "key" | ...`.

---

## Quality Gates

```bash
# Python (always)
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none

# Docker (C3/C4)
docker build -t sciagent:ci-check .
docker images sciagent:ci-check --format "{{.Size}}"
```

No new dependencies are added in P10. No Zotero add-on code changes.
No docs changes beyond this plan file.

---

## Tracker

### P10 Current Status

- Current focus: **C5 — Local Docker smoke test**
- Current next implementation target: **C5.1**
- Last completed: **C3+C4** (2026-05-17) — Dockerfile CMD uses `/app/.venv/bin/uvicorn` + `${PORT:-8080}`; `uv sync --frozen --no-dev` excludes dev group; `streamlit`/`vcrpy`/`responses` moved out of core deps; `.dockerignore` created; image 467 MB (down from 1.19 GB); smoke test confirms health + startup log.

### Phase Tracker

- [ ] **C1** — Cheap LLM account + key *(operational)*
- [ ] **C2** — Startup LLM config log line *(code)*
- [ ] **C3** — Dockerfile: honor `$PORT` *(code)*
- [ ] **C4** — Create `.dockerignore` *(code)*
- [ ] **C5** — Local Docker smoke test *(operational)*
- [ ] **C6** — End-to-end Zotero → Docker test *(operational)*
- [ ] **C7** — Commit + CI *(code + operational)*

### Tracker Rules

1. Update status here first.
2. Treat the first unchecked box as the next implementation target.
3. Do not start M0 of `actionable-plan-gcp.md` until all C1–C7 are checked.
4. If a pitfall from the list above bites you, add it to Common Pitfalls with the
   fix so future-you doesn't repeat it.

---

## See Also

- `docs/actionable-plan-gcp.md` — the GCP deployment plan (start after P10 is done).
- `docs/actionable-plan-done-3.md` — completed P9 plan.
- `.env.example` — canonical env var reference (already documents DeepSeek recipe).
- `src/agt/providers/router.py` — provider routing logic (read before touching providers).
- `src/agt/config.py` — settings contract (read before adding any new env var).
