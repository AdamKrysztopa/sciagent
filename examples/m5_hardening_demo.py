"""Runnable M5 example: deterministic approval decisions and thread isolation check."""

from __future__ import annotations

import argparse
import asyncio
import os

from _shared_demo_helpers import (
    default_zotero_api_key,
    default_zotero_library_id,
    normalize_strict_settings_env,
    resolve_xai_key,
)

from agt.graph import finalize_approval, run_search_phase


def _ensure_required_env() -> None:
    normalize_strict_settings_env()
    os.environ.setdefault("AGT_XAI_API_KEY", resolve_xai_key())
    os.environ.setdefault("AGT_ZOTERO_API_KEY", default_zotero_api_key())
    os.environ.setdefault("AGT_ZOTERO_LIBRARY_ID", default_zotero_library_id())


async def _run(query: str, collection_name: str) -> int:
    try:
        checkpoint_a = await run_search_phase(
            query=query,
            collection_name=collection_name,
            thread_id="m5-thread-a",
        )
        checkpoint_b = await run_search_phase(
            query=query,
            collection_name=collection_name,
            thread_id="m5-thread-b",
        )
    except RuntimeError as exc:
        print("M5 Hardening Example")
        print(f"startup_error: {exc}")
        return 1

    rejected = await finalize_approval(checkpoint_a, approved=False)
    approved = await finalize_approval(checkpoint_b, approved=True, selected_indices=[0])

    print("M5 Hardening Example")
    print(
        f"thread_a: {rejected['thread_id']} decision={rejected['decision']} phase={rejected['phase']}"
    )
    print(
        f"thread_b: {approved['thread_id']} decision={approved['decision']} phase={approved['phase']}"
    )
    print(f"thread_isolated: {rejected['thread_id'] != approved['thread_id']}")
    print(f"reject_write_skipped: {rejected['write_result'] is None}")

    if approved["write_result"] is None:
        print("approve_write: skipped (no selected papers or write path unavailable)")
    else:
        result = approved["write_result"]
        print(
            "approve_write: "
            f"created={result['created']} unchanged={result['unchanged']} failed={result['failed']}"
        )

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M5 hardening demo")
    parser.add_argument("--query", default="retrieval augmented generation")
    parser.add_argument("--collection", default="Inbox")
    args = parser.parse_args()

    _ensure_required_env()
    raise SystemExit(asyncio.run(_run(args.query, args.collection)))


if __name__ == "__main__":
    main()
