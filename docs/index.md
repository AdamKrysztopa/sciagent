# SciAgent Docs

SciAgent ships a Markdown-first documentation stack for the backend, the Zotero add-on, and repo operations.

## Start Here

- [Manual](manual.md) for installation, configuration, CLI/UI/API usage, and development commands
- [Settings](settings.md) for runtime, tooling, and quality-gate policy
- [Core Roadmap](core.md) for implementation order, acceptance criteria, and backlog structure
- [Zotero Add-on](zotero.md) for the native add-on scope and delivery milestones

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
