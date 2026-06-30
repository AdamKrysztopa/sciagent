---
name: model-route
description: Background policy for which Claude model tier to use when delegating SciAgent work to subagents — plan/architect on Opus, implement on Sonnet, fully-pinned mechanical tasks and gate-running on Haiku. Applies whenever Claude spawns subagents for SciAgent work, even outside the full deliver-story pipeline, so cost/quality tiering happens automatically without the user restating it.
user-invocable: false
---

# Model routing policy (SciAgent)

When delegating SciAgent work to subagents (the Agent tool, or a Workflow), pick the model tier by
the **kind of work**, not by convenience. The expensive tier reasons and judges; cheap tiers execute.
This applies to ad-hoc delegation too — not only the `deliver-story` pipeline.

| Work | Tier | Agents / examples |
|---|---|---|
| Decompose, route, plan, judge reviews, all git | **opus** | controller / `sciagent-orchestrator`, `core-planner` |
| Architecture & contract design (no code) | **opus** | story/interface design |
| Write Python (`src/agt/**`, `tests/**`) | **sonnet** | `python-backend-engineer` |
| Write TS/React (Zotero add-on, mechai web) | **sonnet** | `zotero-frontend` |
| Tooling / CI / Docker / docs edits | **sonnet** | `settings-bootstrap` |
| Contract drift review (api/models) | **sonnet** | `api-contract-guardian` |
| Run the quality gates and report | **haiku** | `verification-gate` |
| Fully-pinned mechanical work | **haiku** | a Pydantic model whose fields are listed; a pure helper fully specified by its test; fixtures; config scaffolding |

## The Haiku test
Drop a task to **haiku** only when the task pins the work completely and no judgment is left:
*"Could a careful junior do this from the task description alone, inventing nothing?"* If yes → Haiku.
If it needs provider-SDK nuance, graph/workflow reasoning, invariant judgment (idempotency, approval
gate, ProviderProtocol, typed state, no raw Any), or UX taste → keep it on **sonnet**.

## Escalation
If a Haiku implementer fails the `verification-gate` twice, re-dispatch the fix on **sonnet**. Don't
thrash the cheap tier on something it can't do. Reviewers and gates are never below their listed tier.

## Controller never codes
The Opus controller (main loop or `sciagent-orchestrator`) reads, plans, dispatches, reviews diffs,
and owns git — it does **not** write implementation or test code. State the chosen tier per task so
the cost split stays visible.
