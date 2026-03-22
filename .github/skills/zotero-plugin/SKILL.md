---
name: zotero-plugin
description: Build and validate Zotero plugin features based on zotero.md milestones and constraints.
---

# Zotero Plugin Skill

Use this skill when implementing or reviewing plugin-side features described in `zotero.md`.

## Inputs

- Plugin feature request.
- Expected backend contract details.

## Procedure

1. Map the request to ZAP epic/story IDs.
2. Define UI states (idle, loading, success, partial success, failure).
3. Specify endpoint calls, payload schemas, and retry behavior.
4. Include deduplication and idempotency checks in test scenarios.

## Output

- Feature design summary.
- Implementation steps by file/module.
- Test matrix (happy path and failures).
