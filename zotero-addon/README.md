# SciAgent Zotero Add-on

This package contains the SciAgent M6 native Zotero add-on scaffold and MVP UI.

**Compatibility:** Zotero 7.0+ through Zotero 9.\* (bootstrapped Manifest V2 plugin with dynamic chrome registration)

## Contract

- Plugin ID: `agt@yourdomain.org`
- Native Zotero UI, backend-delegated writes
- Backend endpoints used: `GET /health`, `GET /capabilities`, `POST /run`, `GET /status/{run_id}`, `POST /resume`
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

## Troubleshooting & Developer Console

### Zotero Developer Tools

Zotero provides a JavaScript error console essential for diagnosing add-on installation failures, runtime errors, and bootstrap issues:

- **Open the Error Console:** Tools → Developer → Error Console (or press `Cmd+Shift+Z` / `Ctrl+Shift+Z`)
- **View bootstrap and runtime logs:** All plugin load errors, chrome registration failures, and JavaScript exceptions appear here
- **Filter by add-on:** Use the console search/filter to show only messages containing "SciAgent" or `agt@yourdomain.org`
- **Clear before testing:** Click "Clear" before installing/reloading the add-on to isolate new messages

**As of this commit, the add-on includes comprehensive `[SciAgent]` debug logging:**

- Bootstrap startup: chrome registration, runtime bundle loading, and controller initialization
- Window attachment: document ready state, FTL loading, stylesheet injection, menu item attachment
- Item pane registration: section registration ID and render callback execution
- Preference pane registration
- Window observer lifecycle
- Tools menu command handling
- All error paths with full exception details via `Zotero.logError()`

**To see detailed diagnostic output:**

1. Open Tools → Developer → Error Console
2. Enable "All" or "Messages & Warnings" in the severity filter
3. Install/reload the add-on or perform the action you're debugging
4. Look for lines starting with `[SciAgent]` — these show exactly which startup steps succeeded and which failed

### Common Installation Issues

1. **"Add-on is incompatible with this version of Zotero"**
   - **Verify Zotero version:** Help → About Zotero should show 7.0.0 or higher
   - **Check manifest:** `unzip -p build/sciagent-zotero-addon.xpi manifest.json | grep -A 5 applications` must show `applications.zotero` with `strict_max_version: "9.*"`
   - **Rebuild:** Run `npm run build` and reinstall
   - **Check error console:** Look for specific compatibility messages

2. **Add-on appears installed but doesn't load**
   - **Check error console for bootstrap errors:** Look for "registerChrome" or "amIAddonManagerStartup" failures
   - **Verify chrome.manifest:** Should exist in the XPI root with correct chrome:// registrations
   - **Restart Zotero:** Some bootstrap changes require a full restart

3. **Preferences or UI doesn't appear**
   - **Check error console for JavaScript errors** in preferences-pane.js or bootstrap-runtime.js
   - **Verify chrome paths:** Open the XPI as a zip and confirm `chrome/content/` structure matches manifest registrations

4. **Backend connection fails**
   - **Verify backend is running:** `curl http://localhost:8000/health` should return HTTP 200
   - **Check CORS:** Backend must allow `zotero://` origin if accessed from Zotero chrome:// context
   - **Review error console:** Network errors appear with full request/response details

### Debug Workflow

When diagnosing issues:

1. Clear the error console
2. Perform the action (install, reload, use feature)
3. Check the console immediately for new errors
4. Copy relevant error messages/stack traces
5. Check `bootstrap.js` line numbers if bootstrap fails
6. Verify `manifest.json` structure if compatibility errors appear

## Install In Zotero

1. Start the SciAgent backend:

   ```bash
   uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
   ```

2. Install the add-on from `build/sciagent-zotero-addon.xpi` using Zotero's add-ons/plugins manager.
3. After installation and restart, **SciAgent appears in the Tools menu**. Click **Tools → SciAgent** to:
   - Open preferences if no item is selected (configure backend URL, API key, and client ID)
   - See a reminder about the item pane location if an item is selected
4. The main SciAgent interface appears in the **item details panel on the right** after you select a library item. Look for the **SciAgent section** in the right sidebar.
5. Run a search, review the parsed filters loaded from `/status`, optionally edit them, then approve or reject.

## Included MVP Surface

- backend health check
- query and collection inputs
- parsed filter review/edit controls based on backend search plan data
- re-run with edited `FilterEditContract`
- result list with stable indices, summaries, and selection checkboxes
- approve and reject flow with write result rendering
- preference storage for backend URL, API key, client ID, and PDF toggle placeholder

## Zotero Smoke Test Checklist

Before marking M6 complete, validate in a live Zotero runtime on macOS:

- [ ] Build the XPI: `npm run build` from `zotero-addon/` completes with no errors
- [ ] Verify Zotero version: **Help → About Zotero** shows 7.0.0 or higher
- [ ] Verify manifest compatibility: `unzip -p build/sciagent-zotero-addon.xpi manifest.json | grep -A 5 applications` shows `applications.zotero` with `id`, `update_url`, `strict_min_version: "6.999"`, and `strict_max_version: "9.*"`
- [ ] Open the Zotero Error Console: **Tools → Developer → Error Console** (or `Cmd+Shift+Z`) and clear it before installation
- [ ] Start the backend: `uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000`
- [ ] Open Zotero and navigate to Tools → Add-ons (or Preferences → Plugins)
- [ ] Install the add-on using the "Install Add-on From File..." button and select `build/sciagent-zotero-addon.xpi`
  - **Note:** Do NOT use double-click or open-with on macOS; use the add-ons/plugins manager
  - **If install fails with "incompatible with this version":** Check the Error Console for specific messages, rebuild XPI, verify Zotero version ≥7.0.0, check manifest has `manifest_version: 2` and `applications.zotero` (not `browser_specific_settings`), verify `strict_max_version` is `"9.*"`, and restart Zotero
- [ ] After installation, check the Error Console for any bootstrap or chrome registration errors
- [ ] After installation, the SciAgent add-on appears in the add-ons list with version 0.1.0
- [ ] After restart, **Tools → SciAgent** menu entry is visible
- [ ] Click **Tools → SciAgent** with no item selected: preferences open automatically
- [ ] Configure backend URL (`http://localhost:8000`), API key, and client ID in preferences
- [ ] Select a library item, then click **Tools → SciAgent**: a discoverability message explains the item pane location
- [ ] The **SciAgent section** appears in the right sidebar/item details panel after selecting an item
- [ ] Backend health indicator shows green/connected in the item pane section
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

## Release And Update Flow

SciAgent uses Zotero's automatic update mechanism for distribution:

1. **Update URL:** `manifest.json` points to `https://github.com/AdamKrysztopa/sciagent/releases/latest/download/update.rdf`, which Zotero checks periodically for new versions
2. **Release assets:** Each GitHub release must include both:
   - `sciagent-zotero-addon.xpi` — the add-on package
   - `update.rdf` — the update manifest pointing to the version-specific XPI URL
3. **Version sync:** Before release, ensure version numbers match in:
   - `package.json`
   - `manifest.json`
   - `update.rdf` (version tag and XPI download URL)
4. **Tag format:** Use `v{version}` tags (e.g., `v0.1.0`) matching the XPI download URL in `update.rdf`

**Manual release steps:**

1. Update versions in `package.json` and `manifest.json`
2. Build: `npm run build`
3. Update `update.rdf` with the new version and tag
4. Create a GitHub release with tag `v{version}`
5. Upload both `build/sciagent-zotero-addon.xpi` and `update.rdf` as release assets
6. Existing users will receive the update automatically; new users can install from the latest release

## Current Limitations

- This environment validated the package build, typecheck, and tests, but not a live Zotero 9 runtime session.
- The generated XPI is unsigned and intended for local/manual installation via the Zotero add-ons/plugins manager (not double-click/open-with on macOS).
- The PDF toggle is persisted now as a placeholder only.
- There is no direct native Zotero write path in the add-on; backend ownership of writes is preserved by design.
- **Zotero 9 is the supported M6 target; Zotero 7 compatibility is unclaimed and untested.**
