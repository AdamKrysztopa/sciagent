# Installation

> This page will become the full install guide in P9.13. For now it covers
> the two steps most likely to trip up first-time users: installing the
> add-on and dealing with OS security warnings.

## Quick Start

1. Download **`sciagent-zotero-addon.xpi`** from the
   [latest release](https://github.com/AdamKrysztopa/sciagent/releases/latest).
2. In Zotero: **Tools → Add-ons → Install Add-on From File…** → select the `.xpi` →
   restart Zotero.
3. Open the SciAgent panel (**Tools → SciAgent**).
4. Click **Download Server** in the first-run dialog. The ~70 MB binary is
   downloaded once to `~/.sciagent/bin/` and started automatically.
5. Enter at least one LLM API key in **Preferences → SciAgent → LLM Provider**.

That is the entire install. No `git clone`. No terminal. No Python.

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
    (see [local-first.md Part 7](local-first.md#part-7--macos-codesigning)).

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

## Verified Platforms

| Platform       | Runner         | Status                    |
| -------------- | -------------- | ------------------------- |
| macOS arm64    | macos-14       | ✅ CI-verified             |
| macOS x86\_64  | macos-13       | ⚠ Runner availability varies |
| Linux x86\_64  | ubuntu-22.04   | ✅ CI-verified             |
| Windows x64    | windows-2022   | ✅ CI-verified             |

---

## Next: Configure an LLM Provider

After the binary is running you need one LLM API key to start searching. See
[User Manual](user-manual.md) for the minimum config walkthrough.
