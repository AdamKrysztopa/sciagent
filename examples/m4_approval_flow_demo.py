"""Runnable M4 example: real approval-gated workflow execution."""

from __future__ import annotations

import argparse
import asyncio

from _shared_demo_helpers import (
    default_zotero_api_key,
    default_zotero_library_id,
    resolve_env_key,
    resolve_xai_key,
)

from agt.config import Settings
from agt.graph import finalize_approval, run_search_phase


async def _run(
    query: str,
    collection_name: str,
    selected_indices: list[int] | None,
    approve: bool,
    thread_id: str | None,
) -> int:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": resolve_xai_key(),
        "AGT_ZOTERO_API_KEY": default_zotero_api_key(),
        "AGT_ZOTERO_LIBRARY_ID": default_zotero_library_id(),
        "AGT_SEMANTIC_SCHOLAR_API_KEY": resolve_env_key(
            "AGT_SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"
        ),
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    try:
        checkpoint = await run_search_phase(
            query=query,
            collection_name=collection_name,
            thread_id=thread_id,
            settings=settings,
        )
    except RuntimeError as exc:
        print("M4 Approval Workflow Example")
        print(f"startup_error: {exc}")
        return 1

    print("M4 Approval Workflow Example")
    print("phase: search checkpoint")
    print(f"request_id: {checkpoint['request_id']}")
    print(f"thread_id: {checkpoint['thread_id']}")
    print(f"papers_found: {len(checkpoint['papers'])}")
    print(f"decision: {checkpoint['decision']}")
    print("-" * 80)

    final = await finalize_approval(
        checkpoint,
        approved=approve,
        collection_name=collection_name,
        selected_indices=selected_indices,
        settings=settings,
    )

    print("phase: finalize approval")
    print(f"approved: {final['approved']}")
    print(f"decision: {final['decision']}")
    print(f"final_phase: {final['phase']}")
    print(f"selected_indices: {final['selected_indices']}")

    write_result = final["write_result"]
    if write_result is None:
        print("write: skipped")
    else:
        print(
            "write: "
            f"created={write_result['created']} unchanged={write_result['unchanged']} "
            f"failed={write_result['failed']}"
        )

    return 0


def _parse_indices(raw: str) -> list[int] | None:
    if not raw.strip():
        return None
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M4 approval-gated workflow example")
    parser.add_argument("--query", default="retrieval augmented generation")
    parser.add_argument("--collection", default="Inbox")
    parser.add_argument("--selected-indices", default="", help="Comma-separated indices, e.g. 0,2")
    parser.add_argument("--approve", action="store_true", help="Execute write step after approval")
    parser.add_argument("--thread-id", default=None)
    args = parser.parse_args()

    selected_indices = _parse_indices(args.selected_indices)
    raise SystemExit(
        asyncio.run(
            _run(
                query=args.query,
                collection_name=args.collection,
                selected_indices=selected_indices,
                approve=args.approve,
                thread_id=args.thread_id,
            )
        )
    )


if __name__ == "__main__":
    main()
