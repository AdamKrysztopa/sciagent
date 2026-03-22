---
name: env-bootstrap
description: Apply settings.md to bootstrap local development and quality tooling in a reproducible way.
---

# Environment Bootstrap Skill

Use this skill for project initialization, developer environment setup, and CI-ready quality checks derived from `settings.md`.

## Inputs

- Host OS and shell.
- Existing project files.

## Procedure

1. Align interpreter and package manager strategy.
2. Add or update tool config files (lint, format, type-check, tests).
3. Define canonical run commands for local dev and CI.
4. Validate command success and expected artifacts.

## Output

- Bootstrap command list.
- File diff summary.
- Post-setup verification checklist.
