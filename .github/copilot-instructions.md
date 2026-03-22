# SciAgent Copilot Instructions

This repository currently defines product and engineering direction in three docs:

- `core.md`: platform, retrieval, workflow, and delivery epic/story backlog.
- `settings.md`: runtime stack, bootstrap flow, quality tooling, and dev setup.
- `zotero.md`: Zotero add-on roadmap and native integration plan.

When making or proposing changes:

1. Treat `core.md` as the source of truth for execution order and acceptance criteria.
2. Treat `settings.md` as the source of truth for environment and tooling choices.
3. Treat `zotero.md` as the source of truth for plugin/UI integration scope.
4. Keep outputs implementation-ready and explicit about tradeoffs.
5. Prefer strict, typed Python and testable interfaces.
6. Preserve idempotency and approval gates for any Zotero write path.

Default output style:

- Start with a short plan.
- Provide concrete file-level changes.
- Include test or validation steps.
- Call out risks and assumptions.
