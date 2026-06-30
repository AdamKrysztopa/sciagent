# Installation

## Standalone Install (XPI)

The primary install path. No `git clone`. No terminal. No Python.

1. Download **`sciagent-zotero-addon.xpi`** from
   [Releases](https://github.com/AdamKrysztopa/sciagent/releases/latest).
2. In Zotero: **Tools → Add-ons → Install Add-on From File…** → select the `.xpi` →
   restart Zotero.
3. Open **Tools → SciAgent**. In the first-run dialog click **Download Server**.
   The ~70 MB binary is downloaded once to `~/.sciagent/bin/` and started automatically.
4. Paste an LLM API key in the first-run card → **Save & Continue**.

That's the entire install.

---

## Verified Platforms

| Platform | Runner | Status |
| -------------- | -------------- | ------------------------- |
| macOS arm64 | macos-14 | CI-verified |
| macOS x86\_64 | macos-13 | Runner availability varies |
| Linux x86\_64 | ubuntu-22.04 | CI-verified |
| Windows x64 | windows-2022 | CI-verified |

---

## Self-Update

The add-on checks `update.rdf` on startup. When a new version is available Zotero's
add-on manager shows a notification and lets you update with one click.

The server binary updates itself: if the binary version stored in `~/.sciagent/bin/`
does not match the version the add-on expects, the first-run dialog reappears and
downloads the correct binary automatically.

---

## OS Security Warnings

The server binary is not yet code-signed. Your OS will warn you on first run.

### macOS — Gatekeeper

!!! warning "macOS: Gatekeeper blocks unsigned binaries"
    Because the binary is not signed with an Apple Developer ID, Gatekeeper
    shows:

    > *"sciagent-server" can't be opened because Apple cannot check it for
    > malicious software.*

    **One-time approval (no Terminal needed):**

    1. Open **Finder** → navigate to `~/.sciagent/bin/`.
    2. **Right-click** (or Control-click) the binary
       (`sciagent-server-macos-arm64` or `sciagent-server-macos-x86_64`).
    3. Choose **Open** from the context menu.
    4. In the dialog click **Open** again to confirm.

    Gatekeeper remembers the choice — the binary starts automatically from
    that point on.

    **Alternative (Terminal):** remove the quarantine flag once:

    ```bash
    xattr -d com.apple.quarantine ~/.sciagent/bin/sciagent-server-macos-*
    ```

    Apple Developer ID signing is planned for a future release
    (see [local-first.md Part 7](../reference/local-first.md#part-7--macos-codesigning)).

### Windows — SmartScreen

!!! warning "Windows: SmartScreen warning on first run"
    Because the binary is not signed with an EV certificate, Windows
    SmartScreen shows a blue dialog: *"Windows protected your PC"*.

    **To allow it:**

    1. Click **More info** in the SmartScreen dialog.
    2. Click **Run anyway**.

    SmartScreen remembers the choice for that binary path.

    EV certificate signing is planned for a future release alongside macOS.

### Linux

No warning — Linux does not have an equivalent OS-level gate for downloaded
binaries. The binary is marked executable automatically by the add-on.

---

## Docker (Self-Hosters)

For teams or power users who want to run their own backend:

    docker run -p 8000:8000 \
      -e AGT_OPENAI_API_KEY=sk-... \
      ghcr.io/adamkrysztopa/sciagent:latest

Then point the add-on at `http://your-server:8000` in **ConfigPanel → Backend URL**.

See [deployment.md](../power-user/deployment.md) for full configuration options, environment
variables, and TLS setup.

---

## Source Build (Contributors)

<details>
<summary>Build from source (contributors only)</summary>

    git clone https://github.com/AdamKrysztopa/sciagent.git
    cd sciagent
    uv sync
    cp .env.example .env
    # edit .env — add your LLM key
    uv run uvicorn agt.api.app:app --host 127.0.0.1 --port 8000
    cd zotero-addon && npm ci && npm run build

Install the built XPI from `zotero-addon/build/sciagent-zotero-addon.xpi` via
**Tools → Add-ons → Install Add-on From File…**.

</details>

---

## Smoke Test Checklist {#smoke-checklist}

Run on each platform before tagging a release. Check off each item and record the date.

| Platform | Last verified | Verified by |
| -------- | ------------- | ----------- |
| macOS arm64 | — | — |
| macOS x86\_64 | — | — |
| Linux x86\_64 | — | — |
| Windows x64 | — | — |

### Steps

- [ ] Downloaded XPI from GitHub Releases page
- [ ] Installed XPI in Zotero 9 via Tools → Add-ons → Install Add-on From File
- [ ] Zotero restarted without errors
- [ ] Tools → SciAgent opens the sidebar panel
- [ ] First-run dialog appears; clicked Download Server; binary downloaded successfully
- [ ] Pasted a valid LLM API key; clicked Save & Continue
- [ ] Status pill shows "backend healthy" (green)
- [ ] Typed a test query ("machine learning transformers"); clicked Search
- [ ] Results appeared with titles, authors, and scores
- [ ] Approved 2+ results; clicked Approve Selected
- [ ] Items appeared in Zotero collection without duplicates
- [ ] macOS: Gatekeeper warning handled with right-click Open OR xattr command
- [ ] Windows: SmartScreen "Run anyway" clicked successfully
