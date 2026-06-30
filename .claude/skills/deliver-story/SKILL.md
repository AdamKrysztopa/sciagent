---
name: deliver-story
description: Drive ONE SciAgent backlog story from docs/reference/core.md to verified, gate-green, committed code — goal-directed end-to-end. The controller (Opus) takes the next story off the execution order, branches, gathers the contract (story + CLAUDE.md invariants + Context7 for any SDK), then executes it subagent-driven — implementation ALWAYS on cheaper models (Sonnet default, Haiku for fully-pinned mechanical tasks), Opus NEVER writes code. When ruff + pyright + pytest and the story's acceptance criteria are all green (verified by the verification-gate agent), it commits and reports. Use when the user runs /deliver-story or asks to build/ship/deliver a story (e.g. "AGT-12", "the gap-finder story", "the next story") from docs/reference/core.md.
disable-model-invocation: true
---

# Deliver a SciAgent story

Take ONE story from [`docs/reference/core.md`](../../../docs/reference/core.md) (the highest-authority backlog)
and drive it goal-directed to verified, committed code:
**branch → gather contract → execute TDD subagent-driven → all gates green → commit → report.**
`docs/reference/core.md` already holds the acceptance criteria, so this is disciplined execution, not fresh
design. **The controller stays on Opus and never writes implementation code — cheap subagents do
all the coding.**

**Announce at start:** "Using deliver-story to ship `<story>`."

## Args

`<story>` — a story id (`AGT-12`), a name (`gap-finder`), or `next` (default).
`next` = the topmost story in `docs/reference/core.md`'s execution order whose dependencies are all done.
Run stories **in the documented execution order**; if a dependency isn't done, say so and stop
before branching.

## Live state (check before branching)

- Branch + tree: `git -C "$CLAUDE_PROJECT_DIR" status -sb | head -1`
- Confirm a **clean working tree** and that you are on `main` before branching. If a feature branch
  for this story already exists with work on it, resume rather than restart.

## Goal mode (the operating stance)

Run the story to its **acceptance criteria autonomously** — branch, all TDD tasks, all gates,
commit — **without pausing for per-step approval**. Surface to the user only for:
- a genuine **blocker** (a gate two subagent attempts can't fix; missing key/secret/infra),
- an **open design decision** the story genuinely leaves ambiguous, or
- the **final report**.
Commit per task as you go; the work is always recoverable. Don't narrate every step — act.

## Model policy (the point of this skill)

The expensive controller plans, dispatches, and judges; cheap subagents write the code.

- **Controller (you): Opus.** Read, plan, dispatch, review diffs, do git. **Never write
  implementation or test code yourself.**
- **Implementer subagents — default `model: sonnet`** via the matching specialist
  (`python-backend-engineer` for `src/agt/**` + `tests/**`, `zotero-frontend` for the add-on,
  `settings-bootstrap` for tooling/CI). All real coding.
- **Mechanical tasks — drop to `model: haiku`.** Use Haiku only when the story pins the work
  completely and no judgment is left. Test: *"Could a careful junior do this from the task alone,
  inventing nothing?"* If yes → Haiku. Typical here: a Pydantic model whose fields are listed, a
  pure deterministic helper fully specified by its test, fixtures, config scaffolding.
- **Keep on `sonnet`** anything needing provider-API nuance (the federated search adapters, LLM
  provider router, LangGraph workflow state), or typed-invariant judgment (the Zotero upsert path).
- **Reviewer / gate — `verification-gate` agent on `model: haiku`** for running gates;
  `python-backend-engineer` (sonnet) for code-quality review of higher-risk diffs. The
  `api-contract-guardian` (sonnet) reviews any change to `src/agt/api/**` or `src/agt/models.py`.
- **Escalation:** if a Haiku implementer fails the gate twice, re-dispatch the fix on `sonnet`.
  Don't thrash the cheap tier on something it can't do.

State the chosen tier per task in the task list, so the cost split is visible.

## Workflow

Create a TaskCreate item per phase below, then work them in order.

### 1. Branch (no subagent)
- [ ] Confirm clean tree + on `main`. Create the story branch: `git checkout -b story/AGT-NN-short-name`.

### 2. Gather the story contract (no subagent)
From `docs/reference/core.md` and the supporting docs, read and restate:
- [ ] the **story**: its goal, scope, and **acceptance criteria** (the acceptance check is the demo).
- [ ] the **CLAUDE.md Critical Invariants** the story touches — restate the ones in play:
      idempotent Zotero upsert; every write through the **approval gate**; `zotero/preflight.py`
      passes before any write; all provider adapters satisfy **ProviderProtocol**; **typed** LangGraph
      state (no dict blobs); **zero pyright errors**; **no raw Any** (`response.json()` parsed as
      `object`, narrowed); strict `pydantic-settings` (`extra='forbid'`); tests use `_env_file=None`;
      **no new runtime deps without explicit user approval**.
- [ ] **Verify any provider/library SDK surface against Context7 (mandatory when the story touches a
      provider adapter or a library where the current API matters).** Resolve the library id and pull
      current docs for the exact call (OpenAlex / Semantic Scholar / Crossref / PubMed / Zotero Web
      API; FastAPI, LangGraph, httpx, tenacity, Pydantic v2). The story's snippets can drift from the
      installed version; **Context7 wins**. Capture the verified call shape — paste it into the
      relevant implementer dispatch in step 4.

Restate the **binding rules** before any coding: TDD red→green→refactor; **no live network in tests**
(vcrpy cassettes, `--vcr-record=none`); `_env_file=None` in every settings fixture; deterministic;
idempotent writes; approval-gated writes; zero pyright.

### 3. Plan the tasks (no subagent)
Turn the story's acceptance criteria into an ordered TaskCreate list: each code task is
*failing test → run-it-red → minimal code → green → commit*. Assign each task its **model tier**.
Carry the Context7-verified call shapes into each SDK-touching task. The final task = the story's
**acceptance criteria run green**. Show the full list before executing.

### 4. Execute — subagent-driven
- [ ] Execute tasks **in dependency order** on the story branch. Disjoint-file tasks may be dispatched
      **in parallel**; tasks sharing a file run sequentially. Tell parallel dispatches the
      file-ownership boundary and "if `git commit` hits an `index.lock`, wait and retry".
- [ ] Dispatch each **implementer at its tier** via the matching specialist agent, told to use the
      **`tdd` skill** and obey the step-2 invariants. Give it only its task + the exact types/protocol
      it consumes/produces — not the whole repo. **Dispatch checklist:** the commit-trailer format,
      the pre-existing lint/error baseline (don't chase failures it didn't cause), file-ownership
      boundary, **never push**, and the Context7-verified call shape for SDK tasks.
- [ ] **Review proportional to risk.** Floor = the implementer's own green tests + the
      `verification-gate` agent. For higher-risk diffs (new provider adapter, workflow state, the
      Zotero write path) add a `python-backend-engineer` code-quality review; for any
      `src/agt/api/**` or `models.py` change add the **`api-contract-guardian`**. Controller (Opus)
      judges; bounce the task back if it fails.
- [ ] **Commit per task** on the story branch.

### 5. All gates green (verification-gate agent)
- [ ] Dispatch the **`verification-gate`** agent (Haiku) to run: `uv run ruff check .` ·
      `uv run ruff format --check .` · `uv run pyright` · `uv run pytest -q --vcr-record=none`
      (plus the zotero-addon / docs gates if those areas changed). **Green means green** — fix any red
      (or prove it pre-existed against `main` and flag it); never step over a red test.
- [ ] The story's **acceptance criteria** actually run green (the demo from `docs/reference/core.md`).

### 6. Commit / integrate (no subagent)
- [ ] The story branch carries one clean commit per task. By default leave the branch for the user to
      review/merge; **never push** unless asked. If the user wants it integrated, follow
      `superpowers:finishing-a-development-branch`.

### 7. Report
Summarize: gates met (with evidence — test names, file paths, the acceptance command + its output),
the commits on the story branch, and the **next** story in execution order plus any dependency it
still waits on. State the **model cost split** (which tasks ran Sonnet vs Haiku).

## Definition of done
- [ ] story's **acceptance criteria** run green — shown with evidence
- [ ] `ruff check` · `ruff format --check` · `pyright` (zero errors) · `pytest --vcr-record=none` green
      (+ zotero-addon / docs gates if those areas changed); no red tests left behind
- [ ] every touched CLAUDE.md invariant honored (idempotent + approval-gated + preflight writes,
      ProviderProtocol, typed graph state, no raw Any, strict settings, `_env_file=None`, no
      unapproved deps)
- [ ] every provider/library SDK call the story adds was verified against Context7
- [ ] one clean commit per task on the story branch, **nothing pushed**
- [ ] all coding done on Sonnet/Haiku, never Opus
