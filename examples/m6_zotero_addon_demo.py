"""Runnable M6 example: real backend payloads for Zotero add-on style integration."""

from __future__ import annotations

import argparse
import asyncio
import json
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


async def _run(query: str, collection_name: str, approve: bool) -> int:
    try:
        checkpoint = await run_search_phase(
            query=query,
            collection_name=collection_name,
            thread_id="m6-addon-demo",
        )
    except RuntimeError as exc:
        print("M6 Zotero Add-on Example")
        print(f"startup_error: {exc}")
        return 1

    addon_payload = {
        "thread_id": checkpoint["thread_id"],
        "request_id": checkpoint["request_id"],
        "phase": checkpoint["phase"],
        "papers": checkpoint["papers"],
        "collection_name": checkpoint["collection_name"],
        "search_metadata": checkpoint["search_metadata"],
    }

    print("M6 Zotero Add-on Example")
    print("search_response_payload=")
    print(json.dumps(addon_payload, indent=2))

    final = await finalize_approval(
        checkpoint,
        approved=approve,
        collection_name=collection_name,
        selected_indices=[0],
    )

    print("approval_response_payload=")
    print(
        json.dumps(
            {
                "thread_id": final["thread_id"],
                "phase": final["phase"],
                "decision": final["decision"],
                "approved": final["approved"],
                "write_result": final["write_result"],
            },
            indent=2,
        )
    )

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M6 Zotero add-on integration demo")
    parser.add_argument("--query", default="retrieval augmented generation")
    parser.add_argument("--collection", default="Inbox")
    parser.add_argument("--approve", action="store_true", help="Execute real write path")
    args = parser.parse_args()

    _ensure_required_env()
    raise SystemExit(asyncio.run(_run(args.query, args.collection, args.approve)))


if __name__ == "__main__":
    main()
