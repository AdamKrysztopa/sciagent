"""Runnable M5 example: deterministic approval decisions and thread isolation check."""

from __future__ import annotations

import argparse
import asyncio
import os

import httpx
from _shared_demo_helpers import (
    default_zotero_api_key,
    default_zotero_library_id,
    normalize_strict_settings_env,
    resolve_xai_key,
)

from agt.graph import finalize_approval, resume_workflow, run_search_phase


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
    resumed = await resume_workflow(approved, approved=True)

    api_capabilities: dict[str, int | str] = {"run": 0, "resume": 0, "status": 0, "health": 0}
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=1.5) as client:
            for endpoint in ("/health", "/run", "/resume", "/status/health-check"):
                response = await client.get(endpoint)
                if endpoint == "/health":
                    api_capabilities["health"] = response.status_code
                if endpoint == "/run":
                    api_capabilities["run"] = response.status_code
                if endpoint == "/resume":
                    api_capabilities["resume"] = response.status_code
                if endpoint.startswith("/status"):
                    api_capabilities["status"] = response.status_code
    except Exception:
        api_capabilities = {
            "health": "unreachable",
            "run": "unreachable",
            "resume": "unreachable",
            "status": "unreachable",
        }

    print("M5 Hardening Example")
    print(
        f"thread_a: {rejected['thread_id']} decision={rejected['decision']} phase={rejected['phase']}"
    )
    print(
        f"thread_b: {approved['thread_id']} decision={approved['decision']} phase={approved['phase']}"
    )
    print(f"thread_isolated: {rejected['thread_id'] != approved['thread_id']}")
    print(f"reject_write_skipped: {rejected['write_result'] is None}")
    print(f"resume_reused_write_result: {resumed['write_result'] == approved['write_result']}")

    if approved["write_result"] is None:
        print("approve_write: skipped (no selected papers or write path unavailable)")
    else:
        result = approved["write_result"]
        print(
            "approve_write: "
            f"created={result['created']} unchanged={result['unchanged']} failed={result['failed']}"
        )

    print(
        "api_capabilities: "
        f"health={api_capabilities['health']} run={api_capabilities['run']} "
        f"resume={api_capabilities['resume']} status={api_capabilities['status']}"
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
