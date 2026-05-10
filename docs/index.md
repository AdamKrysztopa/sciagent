# SciAgent Docs

SciAgent docs are organized around the primary researcher path: open the Zotero add-on from Zotero's main window, review the deterministic search plan, then approve selected papers into Zotero.

The Zotero add-on is the primary interface. Streamlit remains a prototype and support surface. The CLI and REST API remain developer and support interfaces.

## Start Here

- [Manual](manual.md) for the Zotero-first workflow, installation, and support interfaces
- [Settings](settings.md) for runtime, tooling, and quality-gate policy
- [Core Roadmap](core.md) for implementation order, acceptance criteria, and backlog structure
- [Zotero Add-on](zotero.md) for the primary product path, scope, and compatibility stance
- [API Reference](api.md) for backend integration, automation, and support debugging

## Docs Workflow

Use the repo Markdown toolchain to lint, preview, and build the docs site.

```bash
npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" "examples/**/*.md" ".github/**/*.md" "zotero-addon/README.md"
uv run mkdocs serve -a 127.0.0.1:8001
uv run mkdocs build --strict
```

The workspace also includes modern Markdown authoring support through `.vscode/`:

- autosave after a short delay
- format-on-save for Markdown
- advanced preview and Mermaid extensions
- MCP browser automation for validating the generated docs site
