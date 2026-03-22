---
applyTo: "**/*.tsx,**/*.jsx"
description: "Use when generating or reviewing React UI code, including future Zotero add-on sidebar work, to keep components pure and hook-compliant."
---

# React and Hooks Guidance

Apply these rules when editing React UI code in this workspace.

1. Use function components and hooks, not class components.
2. Keep hooks at the top level. Do not call hooks conditionally, inside loops, inside nested functions, or after early returns.
3. Keep components and custom hooks pure. Compute derived data during render unless synchronizing with an external system.
4. Prefer small custom hooks for reusable logic. Custom hook names must start with `use`.
5. Prefer `useEffectEvent` when an Effect needs access to current props or state without re-subscribing on every render.
6. Keep Effect dependency lists complete and accurate. Do not silence hook linting unless the platform forces a documented exception.
7. Separate rendering, backend client calls, and host-platform adapters into different modules.
8. For Zotero add-on work, keep `Zotero.*` interactions in adapter or integration modules instead of leaf UI components.
