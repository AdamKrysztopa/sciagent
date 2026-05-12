# SciAgent — Local-First Distribution Plan

> **Goal:** a researcher installs one XPI, opens Zotero, and SciAgent works.
> No terminal. No Python. No Docker. No configuration except an LLM API key
> (or Ollama running locally — no key at all).
> Future: same add-on, optional toggle to a hosted paid tier.

This document covers the full local-first delivery plan: Python server entrypoint,
PyInstaller binary build, CI pipeline, and Zotero add-on integration. It is the
implementation spec for **SCI-0604** (embedded server) and the context for **P6**
overall.

See [actionable-plan.md](actionable-plan.md) for sequencing relative to P5 and P6.

---

## How It Works

```text
User opens Zotero
      │
      ▼
bootstrap.js runs (Zotero add-on lifecycle)
      │
      ├─ First run? → show download dialog
      │  → fetch sciagent-server binary from GitHub Releases (~70 MB)
      │  → save to ~/.sciagent/bin/
      │
      ├─ Already running? (check localhost:57321/health) → reuse
      │
      └─ Spawn: sciagent-server --port 57321 --data-dir ~/.sciagent
                        │
                        ▼
              FastAPI + uvicorn starts
              (existing src/agt/api/app.py — zero new backend code)
                        │
                        ▼
              Zotero sidebar connects → normal operation

User closes Zotero
      │
      ▼
bootstrap.js shutdown hook → kills the child process
```

The binary IS the existing Python backend, frozen by PyInstaller into a single
executable. No new backend logic is needed — just a CLI entrypoint and a build step.

---

## Part 1 — Python Backend Changes

### 1.1 Add CLI entrypoint to `pyproject.toml`

```toml
[project.scripts]
sciagent-server = "agt.server:main"
```

### 1.2 Create `src/agt/server.py`

This is the entrypoint PyInstaller freezes. It wraps uvicorn with the flags the
plugin passes.

```python
"""CLI entrypoint for the embedded local server (SCI-0604)."""
import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="SciAgent local backend")
    parser.add_argument("--port", type=int, default=57321)
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".sciagent")
    parser.add_argument("--log-level", default="warning")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("AGT_DATA_DIR", str(args.data_dir))

    import uvicorn
    uvicorn.run(
        "agt.api.app:app",
        host="127.0.0.1",
        port=args.port,
        log_level=args.log_level,
        access_log=False,
    )


if __name__ == "__main__":
    main()
```

The `--version` value is patched automatically by the CI build script from
`pyproject.toml` (see Part 3).

### 1.3 Add `AGT_DATA_DIR` to `src/agt/config.py`

```python
data_dir: Path = Field(
    default=Path.home() / ".sciagent",
    validation_alias=AliasChoices("AGT_DATA_DIR", "data_dir"),
)
```

Replace the hardcoded `~/.sciagent/` default in `resolved_session_dir`,
`resolved_cache_dir`, and `resolved_watch_dir` properties with `self.data_dir /
"sessions"` etc. This makes the embedded binary respect `--data-dir` properly.

### 1.4 Add `GET /version` to `src/agt/api/app.py`

The plugin uses this to decide if the bundled binary needs updating:

```python
import importlib.metadata

@app.get("/version")
async def get_version() -> dict[str, str]:
    return {"version": importlib.metadata.version("sciagent")}
```

---

## Part 2 — PyInstaller Build

### 2.1 Add PyInstaller to dev group

```toml
[dependency-groups]
dev = [
    # ... existing ...
    "pyinstaller>=6.0",
]
```

### 2.2 Create `build/sciagent-server.spec`

The working spec (verified 2026-05-12 on macOS arm64). Three things are required beyond the
bare minimum: `pathex=["../src"]` so PyInstaller finds the `agt` package; `collect_submodules("agt")`
because `uvicorn.run("agt.api.app:app", ...)` passes the module as a string; and
`collect_data_files("spellchecker")` because `spell_check.py` calls `pkgutil.get_data` at
import time.

```python
# build/sciagent-server.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect the full agt package (uvicorn.run receives it as a string so
# PyInstaller cannot auto-detect it via import analysis).
agt_submodules = collect_submodules("agt")
agt_datas = collect_data_files("agt")
# spellchecker loads en.json.gz via pkgutil.get_data at import time; must be bundled.
spell_datas = collect_data_files("spellchecker")

hidden_imports = agt_submodules + [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    "pydantic_settings",
    "pydantic_settings.env_settings",
    "pydantic_settings.main",
    "structlog",
    "structlog.stdlib",
    "fastapi",
    "slowapi",
    "slowapi.extension",
]

a = Analysis(
    ["../src/agt/server.py"],
    pathex=["../src"],
    binaries=[],
    datas=agt_datas + spell_datas,
    hiddenimports=hidden_imports,
    hookspath=["./hooks"],
    runtime_hooks=[],
    excludes=["streamlit", "matplotlib", "PIL", "tkinter", "keybert", "pytest", "vcrpy"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="sciagent-server",
    debug=False,
    strip=False,
    upx=True,
    console=True,
)
```

> **PyInstaller 6.x note.** The `block_cipher` / `cipher=` parameters were removed in
> PyInstaller 6.0. Do not add them back — they will cause a build error.

### 2.3 Create `build/hooks/hook-pydantic_settings.py`

```python
from PyInstaller.utils.hooks import collect_submodules
hiddenimports = collect_submodules("pydantic_settings")
```

### 2.4 Local build command

```bash
uv run pyinstaller build/sciagent-server.spec \
  --distpath build/dist \
  --workpath build/work \
  --clean
# Output: build/dist/sciagent-server  (or .exe on Windows)
```

**Verified output (macOS arm64, 2026-05-12):**

```bash
./build/dist/sciagent-server --version
# → sciagent-server 0.1.0

./build/dist/sciagent-server --port 58000 &
sleep 2 && curl http://127.0.0.1:58000/health
# → {"ok": false, "provider": "openai", ...}  (HTTP 200; ok:false without credentials is expected)
kill %1
```

The spec in §2.2 is complete and working — no iteration should be needed.

### 2.5 Expected binary sizes (with UPX compression)

| Platform      | Approx size | Verified           |
| ------------- | ----------- | ------------------ |
| macOS arm64   | ~37 MB      | ✅ 2026-05-12       |
| Linux x86\_64 | ~45–60 MB   | estimated          |
| macOS x86\_64 | ~45–60 MB   | estimated          |
| Windows x64   | ~50–65 MB   | estimated          |

These are one-time downloads. Zotero itself is ~150 MB. Researchers accept this.

> **XPI size note.** Do NOT bundle binaries inside the XPI — it would exceed the
> 20 MB Zotero plugin limit. Use download-on-first-run instead (see Part 4.3).

---

## Part 3 — CI Pipeline

### 3.1 New workflow: `.github/workflows/build-binaries.yml`

Triggered on release tags (`v*`) and manually. Builds all platforms in parallel
on native GitHub runners.

```yaml
name: Build Server Binaries

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build:
    strategy:
      matrix:
        include:
          - os: ubuntu-22.04
            platform: linux-x86_64
            binary: sciagent-server
          - os: macos-14
            platform: macos-arm64
            binary: sciagent-server
          - os: macos-13
            platform: macos-x86_64
            binary: sciagent-server
          - os: windows-2022
            platform: windows-x64
            binary: sciagent-server.exe

    runs-on: ${{ matrix.os }}
    name: Build ${{ matrix.platform }}

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.13"

      - name: Install UPX (Linux)
        if: runner.os == 'Linux'
        run: sudo apt-get install -y upx

      - name: Install UPX (macOS)
        if: runner.os == 'macOS'
        run: brew install upx

      - name: Install UPX (Windows)
        if: runner.os == 'Windows'
        run: choco install upx -y

      - name: Sync dependencies
        run: uv sync --frozen

      - name: Patch version into server.py
        shell: bash
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          sed -i.bak "s/version=\"%(prog)s 0.1.0\"/version=\"%(prog)s $VERSION\"/" \
            src/agt/server.py

      - name: Build binary
        run: |
          uv run pyinstaller build/sciagent-server.spec \
            --distpath build/dist \
            --workpath build/work \
            --clean

      - name: Smoke test binary
        shell: bash
        run: |
          ./build/dist/${{ matrix.binary }} --version
          ./build/dist/${{ matrix.binary }} --port 58000 &
          sleep 3
          curl -f http://127.0.0.1:58000/health
          kill %1

      - name: Rename and checksum
        shell: bash
        run: |
          cp build/dist/${{ matrix.binary }} \
            sciagent-server-${{ matrix.platform }}${{ runner.os == 'Windows' && '.exe' || '' }}
          sha256sum sciagent-server-${{ matrix.platform }}* \
            > sciagent-server-${{ matrix.platform }}.sha256

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: binary-${{ matrix.platform }}
          path: sciagent-server-${{ matrix.platform }}*

  package-xpi:
    needs: build
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Download all binaries
        uses: actions/download-artifact@v4
        with:
          path: binaries/
          merge-multiple: true

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Build XPI
        working-directory: zotero-addon
        run: |
          npm ci && npm run lint && npm run typecheck && npm run test && npm run build

      - name: Generate update.rdf
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          XPI_URL="https://github.com/${{ github.repository }}/releases/download/${GITHUB_REF_NAME}/sciagent-zotero-addon.xpi"
          SHA256=$(sha256sum zotero-addon/sciagent-zotero-addon.xpi | cut -d' ' -f1)
          cat > update.rdf << EOF
          <?xml version="1.0" encoding="UTF-8"?>
          <RDF:RDF xmlns:RDF="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                   xmlns:em="http://www.mozilla.org/2004/em-rdf#">
            <RDF:Description about="urn:mozilla:extension:sciagent@sciagent.dev">
              <em:updates>
                <RDF:Seq>
                  <RDF:li>
                    <RDF:Description>
                      <em:version>$VERSION</em:version>
                      <em:targetApplication>
                        <RDF:Description>
                          <em:id>zotero@chnm.gmu.edu</em:id>
                          <em:minVersion>7.0</em:minVersion>
                          <em:maxVersion>*</em:maxVersion>
                          <em:updateLink>$XPI_URL</em:updateLink>
                          <em:updateHash>sha256:$SHA256</em:updateHash>
                        </RDF:Description>
                      </em:targetApplication>
                    </RDF:Description>
                  </RDF:li>
                </RDF:Seq>
              </em:updates>
            </RDF:Description>
          </RDF:RDF>
          EOF

      - name: Upload to GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            zotero-addon/sciagent-zotero-addon.xpi
            update.rdf
            binaries/**
```

---

## Part 4 — Zotero Add-on Changes

### 4.1 New file: `zotero-addon/src/host/serverManager.ts`

Handles the full lifecycle: detect platform, resolve binary path, spawn, health
check, kill on shutdown.

```typescript
import { getPref, setPref } from "../utils/prefs";

const SERVER_PORT = 57321;
const HEALTH_URL  = `http://127.0.0.1:${SERVER_PORT}/health`;
const DATA_DIR    = PathUtils.join(
  Services.dirsvc.get("Home", Ci.nsIFile).path,
  ".sciagent"
);
const BIN_DIR = PathUtils.join(DATA_DIR, "bin");

function getPlatform(): string {
  const os  = Services.appinfo.OS;
  const cpu = Services.appinfo.XPCOMABI;
  if (os === "WINNT")  return "windows-x64";
  if (os === "Darwin") return cpu.startsWith("aarch64") ? "macos-arm64" : "macos-x86_64";
  return "linux-x86_64";
}

function getBinaryName(): string {
  const plat = getPlatform();
  return plat.startsWith("windows")
    ? `sciagent-server-${plat}.exe`
    : `sciagent-server-${plat}`;
}

export async function getBinaryPath(): Promise<string> {
  return PathUtils.join(BIN_DIR, getBinaryName());
}

export async function binaryInstalled(): Promise<boolean> {
  try {
    await IOUtils.stat(await getBinaryPath());
    return true;
  } catch {
    return false;
  }
}

export async function downloadBinary(
  version: string,
  onProgress: (pct: number) => void
): Promise<void> {
  const name = getBinaryName();
  const url  = `https://github.com/AdamKrysztopa/sciagent/releases/download/v${version}/${name}`;
  await IOUtils.makeDirectory(BIN_DIR, { createAncestors: true });
  const tmpPath = PathUtils.join(BIN_DIR, name + ".tmp");

  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", url);
    xhr.responseType = "arraybuffer";
    xhr.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = async () => {
      if (xhr.status !== 200) { reject(new Error(`HTTP ${xhr.status}`)); return; }
      await IOUtils.write(tmpPath, new Uint8Array(xhr.response as ArrayBuffer));
      resolve();
    };
    xhr.onerror = () => reject(new Error("Network error during download"));
    xhr.send();
  });

  if (getPlatform() !== "windows-x64") {
    await Subprocess.call({ command: "/bin/chmod", arguments: ["+x", tmpPath] });
  }
  await IOUtils.move(tmpPath, await getBinaryPath());
}

let _proc: SubprocessResult | null = null;

export async function isServerRunning(): Promise<boolean> {
  try {
    const r = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(500) });
    return r.ok;
  } catch {
    return false;
  }
}

export async function startServer(): Promise<void> {
  if (await isServerRunning()) return;
  const binPath = await getBinaryPath();
  _proc = await Subprocess.call({
    command:   binPath,
    arguments: ["--port", String(SERVER_PORT), "--data-dir", DATA_DIR],
    environment: collectProviderEnv(),
    stderr: "pipe",
  });
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    if (await isServerRunning()) return;
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error("SciAgent server did not start within 15 seconds");
}

export async function stopServer(): Promise<void> {
  if (_proc) {
    try { _proc.kill(); } catch { /* already dead */ }
    _proc = null;
  }
}

/**
 * Collect LLM provider env vars from Zotero prefs.
 * Supports all built-in providers + custom OpenAI-compatible endpoints.
 * P6 (SCI-0601/0602) adds AGT_LLM_BASE_URL and AGT_LLM_MODEL support.
 */
function collectProviderEnv(): Record<string, string> {
  const env: Record<string, string> = {};
  const keyMap: Record<string, string> = {
    openai_api_key:    "OPENAI_API_KEY",
    anthropic_api_key: "ANTHROPIC_API_KEY",
    xai_api_key:       "XAI_API_KEY",
    groq_api_key:      "GROQ_API_KEY",
  };
  for (const [pref, envVar] of Object.entries(keyMap)) {
    const val = getPref(pref) as string | undefined;
    if (val) env[envVar] = val;
  }
  const provider = getPref("llmProvider") as string | undefined;
  if (provider) env["AGT_LLM_PROVIDER"] = provider;

  // Custom OpenAI-compatible endpoint (SCI-0601)
  const baseUrl = getPref("llmBaseUrl") as string | undefined;
  const model   = getPref("llmModel") as string | undefined;
  if (baseUrl) env["AGT_LLM_BASE_URL"] = baseUrl;
  if (model)   env["AGT_LLM_MODEL"]    = model;

  return env;
}
```

### 4.2 Update `bootstrap.js`

```javascript
let serverManager = null;

async function startup({ id, version, rootURI, reason }) {
  // ... existing startup code ...
  const { default: sm } = await ChromeUtils.importESModule(
    rootURI + "chrome/content/host/serverManager.js"
  );
  serverManager = sm;

  const mode = Zotero.Prefs.get("extensions.agt.backendMode") ?? "local";
  if (mode === "local") {
    try {
      const installed = await serverManager.binaryInstalled();
      if (!installed) await showFirstRunDialog(version);
      await serverManager.startServer();
    } catch (e) {
      Zotero.logError(e);
      showErrorNotification(
        "SciAgent could not start. Check your LLM provider key in SciAgent preferences."
      );
    }
  }
}

async function shutdown({ id, version, rootURI, reason }) {
  // ... existing shutdown code ...
  if (serverManager) {
    await serverManager.stopServer();
    serverManager = null;
  }
}
```

### 4.3 First-run dialog: `zotero-addon/src/ui/FirstRunDialog.tsx`

```tsx
import { useState } from "react";
import { downloadBinary } from "../host/serverManager";

interface Props {
  version: string;
  onComplete: () => void;
  onError: (msg: string) => void;
}

export function FirstRunDialog({ version, onComplete, onError }: Props) {
  const [progress, setProgress] = useState<number | null>(null);
  const [status, setStatus]     = useState<"ready"|"downloading"|"done"|"error">("ready");

  async function handleInstall() {
    setStatus("downloading");
    try {
      await downloadBinary(version, (pct) => setProgress(pct));
      setStatus("done");
      onComplete();
    } catch (e: unknown) {
      setStatus("error");
      onError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 420 }}>
      <h2>Welcome to SciAgent</h2>
      <p style={{ color: "#555" }}>
        SciAgent needs to download its search engine (~70 MB, one time only).
        Everything runs on your computer — your data stays local.
      </p>
      {status === "ready" && (
        <button onClick={() => void handleInstall()}>Download &amp; Install</button>
      )}
      {status === "downloading" && (
        <div>
          <progress value={progress ?? 0} max={100} style={{ width: "100%" }} />
          <p>{progress !== null ? `${progress}%` : "Starting…"}</p>
        </div>
      )}
      {status === "done"  && <p>Ready. You can close this window.</p>}
      {status === "error" && <p>Download failed. Check your internet connection.</p>}
    </div>
  );
}
```

### 4.4 Provider selector in settings panel (P6 / SCI-0603)

The existing settings panel gains a provider dropdown and conditional fields. This
is tracked as SCI-0603 in P6. See the P6 section in [actionable-plan.md](actionable-plan.md).

---

## Part 5 — CORS for the Embedded Server

Add to `src/agt/api/app.py` (also covers SCI-0501):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["app://zotero.org", "chrome://zotero", "http://127.0.0.1"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

---

## Part 6 — Port Safety

Port 57321 is the preferred port. Add a fallback scan in `serverManager.ts`:

```typescript
async function findFreePort(): Promise<number> {
  for (const port of [57321, 57322, 57323, 57324, 57325]) {
    if (await isPortFree(port)) return port;
  }
  throw new Error("No free port found for SciAgent server");
}

async function isPortFree(port: number): Promise<boolean> {
  try {
    await fetch(`http://127.0.0.1:${port}`, { signal: AbortSignal.timeout(100) });
    return false;
  } catch {
    return true;
  }
}
```

Store the resolved port in `Zotero.Prefs` and read it from `backendClient.ts`.

---

## Part 7 — macOS Codesigning

Without codesigning, macOS Gatekeeper blocks the binary. For MVP beta, ship
unsigned with this install note:

> "macOS users: right-click the Zotero app → Open → confirm once. Signing is
> coming in v1.1."

For v1.1, add Apple Developer Program secrets to GitHub CI:

```yaml
- name: Sign binary
  run: |
    codesign --deep --force --options runtime \
      --sign "Developer ID Application: Your Name (${{ secrets.APPLE_TEAM_ID }})" \
      build/dist/sciagent-server
```

Windows SmartScreen shows a similar warning; plan EV certificate codesigning
alongside macOS for v1.1.

---

## Part 8 — Sequencing

Each week is independently shippable.

**Week 1 — Backend entrypoint (SCI-0604 precursor)**

- [ ] Create `src/agt/server.py`
- [ ] Add `[project.scripts]` entry to `pyproject.toml`
- [ ] Add `AGT_DATA_DIR` to `config.py`
- [ ] Add `GET /version` to `app.py`
- [ ] Run `uv run python -m agt.server --port 57321` and confirm `/health` responds

**Week 2 — PyInstaller**

- [ ] Add PyInstaller to dev deps
- [ ] Create `build/sciagent-server.spec` and `build/hooks/`
- [ ] Build locally, fix hidden imports
- [ ] Binary smoke test: `./build/dist/sciagent-server --version` and `curl /health`

**Week 3 — CI pipeline**

- [ ] Add `.github/workflows/build-binaries.yml`
- [ ] Trigger on branch, fix CI-specific failures
- [ ] Confirm four platform binaries pass smoke test in CI

**Week 4 — Plugin integration**

- [ ] Create `serverManager.ts`
- [ ] Update `bootstrap.js`
- [ ] Create `FirstRunDialog.tsx`
- [ ] Manual end-to-end: install XPI → first-run dialog → download → server starts → search works → Zotero close → server stops

**Week 5 — Polish and release**

- [ ] Add port fallback logic
- [ ] Update README: remove "run uvicorn manually" step
- [ ] Tag `v1.0.0` → CI builds all artifacts → publish GitHub Release

---

## Part 9 — Future: Hosted Tier

When ready, the local-first architecture makes hosted almost free to add:

**What changes in the add-on:** just the settings panel that already exists (§4.4).
Users toggle "SciAgent Cloud", enter a cloud URL and subscription key, restart
Zotero. The local server does not start.

**What you deploy:** the same Docker image already in the repo (once SCI-0503 fixes
the Dockerfile). Add auth middleware and per-user quotas. The `/capabilities`
response signals which tier features are active — the add-on shows them
conditionally.

**No separate build or codebase.** The local binary and the cloud backend run
identical application code. That is the key architectural win of this approach.
