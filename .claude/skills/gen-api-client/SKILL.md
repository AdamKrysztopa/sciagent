---
name: gen-api-client
description: Regenerate the typed TypeScript SciAgent API client(s) from the backend's live OpenAPI schema, so the Zotero add-on and the mechai.pl web app stay in lockstep with the FastAPI backend instead of drifting against hand-written types. Use when src/agt/api/** or src/agt/models.py changed, when api-contract-guardian reports drift, or when bootstrapping a new client (the mechai.pl web app). Run /gen-api-client.
disable-model-invocation: true
---

# Generate the typed API client from OpenAPI

The FastAPI backend is the single source of truth for the request/response shapes. Both
TypeScript clients — the Zotero add-on and the standalone mechai.pl web app — should consume
a **generated** client derived from the backend's `/openapi.json`, not hand-maintained
interfaces that silently drift. This skill regenerates them.

**Announce at start:** "Using gen-api-client to regenerate the typed client(s)."

## 1. Dump the OpenAPI schema (no running server needed)

Build the FastAPI app in-process and emit its schema. Confirm the factory name in
`src/agt/api/app.py` first (it builds the app + routes); adjust the import if it differs:

```bash
uv run python -c "from agt.api.app import build_app; import json; print(json.dumps(build_app().openapi(), indent=2))" > /tmp/sciagent-openapi.json
```

If the app factory needs settings, pass test-style settings (`_env_file=None`) the same way the
test suite builds the app. If it genuinely can't build headless, fall back to starting the server
(`uv run sciagent-server --port 57321`) and `curl -s http://localhost:57321/openapi.json`.

## 2. Generate the typed client

Use `openapi-typescript` (types) — invoke via `npx`, **do not add it as a dependency** (CLAUDE.md:
no new deps without approval; this is a dev-time codegen tool, run on demand):

```bash
# Types for the Zotero add-on
npx --yes openapi-typescript /tmp/sciagent-openapi.json -o zotero-addon/src/api/schema.gen.ts
```

For the mechai.pl web app, generate into that repo's client module (e.g.
`my_web_page/lib/sciagent/schema.gen.ts`). Keep the thin hand-written fetch wrapper (auth headers
`X-AGT-API-Key` / `X-AGT-Client-ID`, the run→resume→status flow, loading/partial/error states)
separate from the generated `schema.gen.ts` so regeneration never clobbers hand-written logic.

## 3. Wire and verify
- [ ] Point the hand-written client's types at the regenerated `schema.gen.ts`.
- [ ] `cd zotero-addon && npm run typecheck` must pass (the generated types flush out drift as
      compile errors — that is the point).
- [ ] For mechai.pl: `npm run build` (Next.js typecheck) must pass.
- [ ] Run the **`api-contract-guardian`** agent to confirm zero remaining drift.

## Notes
- `schema.gen.ts` files are **generated** — treat them as build artifacts: regenerate, don't
  hand-edit. Consider gitignoring them or marking them generated.
- This is the structural fix behind contract drift: change a Pydantic model → regenerate → both
  clients fail to typecheck exactly where they relied on the old shape.
