# SciAgent Zotero Add-on

This package contains the SciAgent M6 native Zotero 9 add-on scaffold and MVP UI.

## Contract

- Plugin ID: `agt@yourdomain.org`
- Native Zotero UI, backend-delegated writes
- Backend endpoints used: `GET /health`, `POST /run`, `GET /status/{run_id}`, `POST /resume`
- All writes remain server-side through `POST /resume`
- Filter edits are sent through the existing backend `FilterEditContract`
- **Required backend contract version: `2026-05`** — The add-on displays a warning if the backend `/health` response returns a missing or mismatched `api_contract_version`.

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

## Install In Zotero 9

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

## Zotero 9 Smoke Test Checklist

Before marking M6 complete, validate in a live Zotero 9 runtime on macOS:

- [ ] Build the XPI: `npm run build` from `zotero-addon/` completes with no errors
- [ ] Verify Zotero version: **Help → About Zotero** shows 9.0.0 or higher
- [ ] Verify manifest compatibility: `unzip -p build/sciagent-zotero-addon.xpi manifest.json | grep strict_` shows `strict_max_version: "9.*"`
- [ ] Start the backend: `uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000`
- [ ] Open Zotero 9 and navigate to Tools → Add-ons (or Preferences → Plugins)
- [ ] Install the add-on using the "Install Add-on From File..." button and select `build/sciagent-zotero-addon.xpi`
  - **Note:** Do NOT use double-click or open-with on macOS; use the add-ons/plugins manager
  - **If install fails with "incompatible with this version":** Rebuild XPI, verify Zotero version ≥9.0.0, check manifest `strict_max_version` is `"9.*"`, and restart Zotero
- [ ] After installation, the SciAgent add-on appears in the add-ons list with version 0.1.0
- [ ] Open SciAgent preferences (Tools → Add-ons → SciAgent → Preferences or gear icon)
- [ ] Configure backend URL (`http://localhost:8000`), API key, and client ID
- [ ] Open the SciAgent item-pane section in Zotero
- [ ] Backend health indicator shows green/connected
- [ ] Health status displays the backend contract version `2026-05` without warnings
- [ ] Enter a test query (e.g., "retrieval augmented generation") and collection name
- [ ] Parsed filters from `/status` render correctly with year, date range, sources, and preferences
- [ ] Optionally edit filters using the review/edit controls
- [ ] Result list displays with stable indices, summaries, and selection checkboxes
- [ ] Select or deselect papers using checkboxes
- [ ] Click Approve and verify write results render with created/unchanged/failed status
- [ ] Verify items appear in the target Zotero collection with correct metadata
- [ ] Test Reject flow: results are discarded without writing to Zotero
- [ ] Reload Zotero and verify preferences persist across sessions
- [ ] Uninstall the add-on cleanly via the add-ons/plugins manager

## Current Limitations

- This environment validated the package build, typecheck, and tests, but not a live Zotero 9 runtime session.
- The generated XPI is unsigned and intended for local/manual installation via the Zotero add-ons/plugins manager (not double-click/open-with on macOS).
- The PDF toggle is persisted now as a placeholder only.
- There is no direct native Zotero write path in the add-on; backend ownership of writes is preserved by design.
- **Zotero 9 is the supported M6 target; Zotero 7 compatibility is unclaimed and untested.**
