"""CLI runner for the workflow skeleton."""

from __future__ import annotations

import argparse
import asyncio
import json

from agt.graph.workflow import run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run SciAgent workflow skeleton")
    parser.add_argument("query", help="Natural language paper query")
    parser.add_argument("--collection", default="Inbox", help="Target Zotero collection")
    parser.add_argument("--approve", action="store_true", help="Approve write step")
    return parser


async def _main() -> None:
    args = build_parser().parse_args()
    state = await run_workflow(
        query=args.query, collection_name=args.collection, approved=args.approve
    )
    print(json.dumps(state, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
