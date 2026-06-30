# SciAgent

SciAgent is a federated academic search assistant that queries OpenAlex, Semantic Scholar,
Crossref, PubMed, arXiv, Europe PMC, BASE, and OpenCitations in a single deterministic plan,
ranks and deduplicates results, and routes approved papers into your Zotero library through an
idempotent, approval-gated write path — so nothing lands in Zotero without your explicit sign-off.

## Start Here

- New to SciAgent? [Install and configure the backend and Zotero add-on.](get-started/install.md)
- Running your first search? [Follow the User Manual for a step-by-step walkthrough.](get-started/user-manual.md)
- Deploying for a team? [See Deployment and Hosting for server and Docker setup.](power-user/deployment.md)

## What Is in This Docs Site

- **Get Started** — installation, API key setup, and the user manual for daily use
- **Power User** — advanced configuration, the full configuration and usage reference, and
  deployment options for self-hosted or team environments
- **Reference** — REST API, provider inventory, settings contract, Zotero add-on architecture,
  security policy, benchmark results, local-first install guide, and the core roadmap
- **Project** — the active action plan and the multi-user backend plan
- **Plans & Specs** — implementation plans and design specs for in-flight workstreams
- **Archive** — completed plans (`done/`) and superseded or historical notes (`obsolete/`)

## Docs Maintenance

To lint and build the docs locally:

    npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" ".github/**/*.md" "zotero-addon/README.md"
    uv run mkdocs build --strict
