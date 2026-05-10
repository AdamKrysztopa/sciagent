"""CLI runner for the workflow skeleton."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from agt.graph.workflow import run_workflow
from agt.models import AgentState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run SciAgent workflow skeleton")
    parser.add_argument("query", help="Natural language paper query")
    parser.add_argument("--collection", default="Inbox", help="Target Zotero collection")
    parser.add_argument("--approve", action="store_true", help="Approve write step")
    parser.add_argument("--thread-id", default=None, help="Optional workflow thread id")
    return parser


def _exit_code_for_state(state: AgentState) -> int:
    return 1 if state["phase"] == "failed" else 0


async def main() -> int:
    args = build_parser().parse_args()
    try:
        state = await run_workflow(
            query=args.query,
            collection_name=args.collection,
            approved=args.approve,
            thread_id=args.thread_id,
        )
        print(json.dumps(state, indent=2, default=str))
        return _exit_code_for_state(state)
    except RuntimeError as exc:
        print(f"Startup validation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
