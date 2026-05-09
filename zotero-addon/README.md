# SciAgent Zotero Add-on

This package contains the SciAgent M6 native Zotero 7 add-on scaffold and MVP UI.

## Contract

- Plugin ID: `agt@yourdomain.org`
- Native Zotero UI, backend-delegated writes
- Backend endpoints used: `GET /health`, `POST /run`, `GET /status/{run_id}`, `POST /resume`
- All writes remain server-side through `POST /resume`
- Filter edits are sent through the existing backend `FilterEditContract`

## Build And Validate

```bash
cd zotero-addon
npm ci
npm run lint
npm run build
```

Build outputs:

- `build/xpi/` — staged unpacked add-on contents
- `build/sciagent-zotero-addon.xpi` — local install package

## Install In Zotero 7

1. Start the SciAgent backend:

	```bash
	uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
	```

2. Install the add-on from `build/sciagent-zotero-addon.xpi` using Zotero's add-ons/plugins manager.
3. Open the SciAgent preferences pane and set backend URL, API key, and client ID.
4. Open the SciAgent item-pane section in Zotero.
5. Run a search, review the parsed filters loaded from `/status`, optionally edit them, then approve or reject.

## Included MVP Surface

- backend health check
- query and collection inputs
- parsed filter review/edit controls based on backend search plan data
- re-run with edited `FilterEditContract`
- result list with stable indices, summaries, and selection checkboxes
- approve and reject flow with write result rendering
- preference storage for backend URL, API key, client ID, and PDF toggle placeholder

## Current Limitations

- This environment validated the package build, typecheck, and tests, but not a live Zotero 7 runtime session.
- The generated XPI is unsigned and intended for local/manual installation.
- The PDF toggle is persisted now as a placeholder only.
- There is no direct native Zotero write path in the add-on; backend ownership of writes is preserved by design.
