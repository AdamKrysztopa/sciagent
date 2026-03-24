# SciAgent Copilot Instructions

This repository currently defines product and engineering direction in three docs:

- `docs/core.md`: platform, retrieval, workflow, and delivery epic/story backlog.
- `docs/settings.md`: runtime stack, bootstrap flow, quality tooling, and dev setup.
- `docs/zotero.md`: Zotero add-on roadmap and native integration plan.

When making or proposing changes:

1. Treat `docs/core.md` as the source of truth for execution order and acceptance criteria.
2. Treat `docs/settings.md` as the source of truth for environment and tooling choices.
3. Treat `docs/zotero.md` as the source of truth for plugin/UI integration scope.
4. Keep outputs implementation-ready and explicit about tradeoffs.
5. Prefer strict, typed Python and testable interfaces.
6. Preserve idempotency and approval gates for any Zotero write path.
7. Build and validate real implementations by default; do not ship mockup-only or stub-only feature code unless the user explicitly asks for a mock/demo.

Global execution policy (highest priority for this repository):

1. Do not use subagents for implementation, planning, or codebase exploration unless the user explicitly requests a specific subagent by name.
2. Execute work directly in the main coding session using local file and terminal tools.
3. For milestone examples, prefer real runtime behavior and integration paths over mocked flows.

Agent routing and research rules:

1. Use `core-planner` for backlog mapping, acceptance checks, and story sequencing against `docs/core.md`.
2. Use `settings-bootstrap` for environment, quality tooling, CI, and reproducibility work tied to `docs/settings.md`.
3. Use `zotero-addon` for Zotero plugin architecture, backend contract mapping, and native integration work tied to `docs/zotero.md`.
4. Use `zotero-frontend` for TypeScript, React, WebExtension, sidebar UI, manifest, bootstrap, and hook-heavy add-on implementation work.
5. For unfamiliar third-party libraries or fast-moving APIs, fetch current documentation through Context7 (`mcp_io`) before coding. Prefer official docs over memory for React, Zotero add-on tooling, LangGraph, and VS Code customization behavior.
6. Keep agent descriptions keyword-rich so the right specialist is discoverable from the user prompt.

Frontend and add-on implementation rules:

1. Treat Zotero add-on work as TypeScript-first and React-first, not Python-first.
2. Keep plugin UI, backend client, and Zotero host integration in separate modules.
3. Generated React code must follow the current Rules of Hooks: no conditional hooks, no hooks in loops or callbacks, custom hooks must start with `use`, and components/hooks must stay pure.
4. Prefer `useEffectEvent` when event-like logic must read current values without making an Effect re-run unnecessarily.
5. Keep effect dependencies explicit and lint-clean; do not suppress hook lint rules unless there is a documented platform constraint.
6. Keep Zotero globals and host APIs at the boundary layer instead of reading them directly in presentational components.

Default output style:

- Start with a short plan.
- Provide concrete file-level changes.
- Include test or validation steps.
- Call out risks and assumptions.
