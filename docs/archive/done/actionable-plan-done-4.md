# SciAgent Actionable Plan — P10 (GCP Prerequisites: Cheap LLM + Docker Cloud Readiness) — DONE

> **Completed: 2026-05-17** — All C1–C7 stories complete. Archived 2026-05-17.
> See [actionable-plan.md](../../project/actionable-plan.md) for the current plan (GCP Deployment).
>
> **Last audit: 2026-05-17** — All P0–P9 stories complete (see
> [actionable-plan-done-3.md](actionable-plan-done-3.md) and earlier archives).
>
> This plan covers **P10: everything that must be true in the codebase and locally
> before the GCP deployment plan makes sense.**
> No GCP commands here — this is the application story. The deployment plan is the
> infrastructure story. Both must pass before GCP works.

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

---

## Execution Tracker

### Current Status

- All P0–P9 milestones complete as of 2026-05-14.
- **P10 complete.** All C1–C7 done as of 2026-05-17.
- Last completed: **C7 (2026-05-17)** — commit 509561c pushed, all pre-push hooks green (ruff, pyright, markdownlint, zotero-addon, docs).

### P10 Status

| ID  | Story                                          | Effort  | Owner                    | Status      |
| --- | ---------------------------------------------- | ------- | ------------------------ | ----------- |
| C1  | Cheap LLM account + key                        | ~15 min | you (operational)        | ✅ done (2026-05-17) |
| C2  | Startup LLM config log line                    | ~30 min | python-backend-engineer  | ✅ done (2026-05-17) |
| C3  | Dockerfile: honor `$PORT`                      | ~5 min  | python-backend-engineer  | ✅ done (2026-05-17) |
| C4  | Create `.dockerignore`                         | ~5 min  | python-backend-engineer  | ✅ done (2026-05-17) |
| C5  | Local Docker smoke test with cheap LLM         | ~15 min | you (operational)        | ✅ done (2026-05-17) |
| C6  | End-to-end Zotero → Docker test                | ~20 min | you (operational)        | ✅ done (2026-05-17) |
| C7  | Commit + CI green                              | ~10 min | python-backend-engineer  | ✅ done (2026-05-17) |

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

- [x] **C1.1** Sign up at <https://platform.deepseek.com> (Google OAuth works).
- [x] **C1.2** Top up $5. This covers ~30 million tokens of `deepseek-chat` — over
  a year of solo SciAgent use.
- [x] **C1.3** Create an API key. Save to password manager as `DEEPSEEK_API_KEY`.
- [x] **C1.4** Verify with a direct curl (replace `<KEY>`):

  ```bash
  curl https://api.deepseek.com/chat/completions \
    -H "Authorization: Bearer <KEY>" \
    -H "Content-Type: application/json" \
    -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"Say hi"}],"max_tokens":10}'
  ```

  Expect 200 JSON. `401` = wrong key. `402` = balance zero (top up first).

- [x] **C1.5** Verify the SciAgent env var wiring locally (no Docker):

  ```bash
  AGT_LLM_PROVIDER=openai-compatible \
  AGT_LLM_BASE_URL=https://api.deepseek.com/v1 \
  AGT_LLM_MODEL=deepseek-chat \
  AGT_LLM_API_KEY=<KEY> \
  uv run sciagent-server --port 57322 &

  curl -s http://127.0.0.1:57322/health | python3 -m json.tool
  kill %1
  ```

  Expect `/health` to return 200.

**Cost: $5 one-time.**

---

### C2 — Startup LLM Config Log Line (30 minutes)

**Goal.** `create_app()` in `src/agt/api/app.py` emits one structured log line at
`INFO` level showing the effective LLM provider, model, and base URL.

**Implemented:** `src/agt/api/app.py` — `structlog` import + `_log.info("sciagent_startup", ...)` inside `create_app()` right after `_settings = get_settings()`. Confirmed via Docker smoke test C5.

---

### C3 — Dockerfile: Honor `$PORT` (5 minutes)

**Goal.** The container listens on whatever port Cloud Run sets via `$PORT`.

**Implemented:** `Dockerfile` CMD now uses `/app/.venv/bin/uvicorn ... --port ${PORT:-8080}`.
Image also uses `uv sync --frozen --no-dev`, eliminating dev dependencies from the image.

---

### C4 — Create `.dockerignore` (5 minutes)

**Goal.** Reduce the Docker build context. Image shrank from 1.19 GB → 467 MB.

**Implemented:** `.dockerignore` at repo root excludes `tests/`, `zotero-addon/`, `docs/`, dev caches, `.env` files (with `!README.md` and `!.env.example` exceptions required by hatchling).

---

### C5 — Local Docker Smoke Test with Cheap LLM (15 minutes)

**Completed 2026-05-17.** Container started, `/health` returned 200 with
`provider=openai-compatible`. `/run` query returned `status: "awaiting_approval"`.
Docker logs confirmed DeepSeek called 10× with HTTP 200 OK. Startup log showed
correct `llm_provider`, `llm_model`, `llm_base_url`.

---

### C6 — End-to-End Zotero → Docker Test (20 minutes)

**Completed 2026-05-17.** Add-on set to `backendMode=remote`, URL
`http://localhost:8080`, API key `local-test-key`. Search → approve → write to
test collection succeeded. Second write confirmed idempotent (`unchanged` for all
items).

---

### C7 — Commit + CI (10 minutes)

**Completed 2026-05-17.** Commit `509561c` on `main`. All pre-push hooks green:
ruff, pyright, markdownlint, zotero-addon-quality, docs-quality.

---

## Definition of Done

All C1–C7 complete. ✅

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
  provider is set, it resolves to `openai-compatible`. Still, set it explicitly to
  be unambiguous.
- **`AGT_LLM_BASE_URL=https://api.deepseek.com` without `/v1`.** The correct base
  for the OpenAI-compat path is `https://api.deepseek.com/v1`. Without `/v1`,
  the SDK double-paths and gets 404.
- **`AGT_LLM_MODEL` not set.** The default for `openai-compatible` in
  `_PROVIDER_DEFAULT_MODELS` is `gpt-4o-mini` (`config.py:28`). DeepSeek will
  reject this model name. Always set `AGT_LLM_MODEL=deepseek-chat` explicitly.
- **`uv sync` without `--no-dev` in Dockerfile.** Pulls in streamlit, pyright,
  mkdocs — balloons the image to 1.19 GB. Always use `--no-dev`.
- **`uv run uvicorn` as CMD.** Triggers implicit re-sync at container startup.
  Use `/app/.venv/bin/uvicorn` directly.

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

No new dependencies added in P10. No Zotero add-on code changes.

---

## See Also

- `docs/project/actionable-plan.md` — current plan (GCP Deployment).
- `docs/archive/done/actionable-plan-done-3.md` — completed P9 plan.
- `.env.example` — canonical env var reference (documents DeepSeek recipe).
- `src/agt/providers/router.py` — provider routing logic.
- `src/agt/config.py` — settings contract.
