#!/usr/bin/env bash
# protect-paths.sh — PreToolUse(Write|Edit) guard.
# Block edits to files that must never be hand-edited by the agent, protecting
# the CLAUDE.md invariants (test isolation, strict settings, no silent dep drift):
#   - env files (secrets)              -> edit yourself / confirm out of band
#   - vcrpy cassettes                  -> tests REPLAY these; re-record deliberately
#                                         with --vcr-record, never hand-edit a fixture
#   - uv.lock                          -> mutate via `uv add` / `uv lock`, not by hand
# Exit 2 = block + feed stderr back to Claude.

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
  *.env|*.env.*|*/.env|*/.env.*)
    echo "BLOCKED: '$path' is an env file (secrets). Edit it yourself or confirm explicitly out of band." >&2; exit 2;;
  */cassettes/*|*/cassettes/*.yaml|*.cassette.yaml)
    echo "BLOCKED: '$path' is a vcrpy cassette. Tests replay cassettes deterministically (--vcr-record=none). Re-record deliberately with a recording run; never hand-edit a cassette." >&2; exit 2;;
  */uv.lock|uv.lock)
    echo "BLOCKED: don't hand-edit '$path'. Change dependencies via 'uv add' / 'uv lock' so the lockfile stays consistent (and new runtime deps need explicit approval)." >&2; exit 2;;
esac

exit 0
