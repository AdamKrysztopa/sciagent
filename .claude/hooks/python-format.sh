#!/usr/bin/env bash
# python-format.sh — PostToolUse(Edit|Write) gate-keeper.
# Keep every Python edit aligned with the CLAUDE.md quality gates as it is made,
# instead of discovering ruff/format drift only at the end:
#   - `ruff format` the touched file
#   - `ruff check --fix` it (safe autofixes only)
# Non-Python files are ignored. Never blocks (exit 0 always); this is cleanup,
# not a gate. The real gate is the verification-gate agent / CI.

input=$(cat)
path=$(printf '%s' "$input" | python3 -c '
import sys, json
try:
    t = json.load(sys.stdin).get("tool_input", {}) or {}
    print(t.get("file_path") or t.get("path") or "")
except Exception:
    print("")
')

case "$path" in
  *.py)
    cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0
    uv run ruff format "$path" >/dev/null 2>&1
    uv run ruff check --fix "$path" >/dev/null 2>&1
    ;;
esac

exit 0
