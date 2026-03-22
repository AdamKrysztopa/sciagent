"""Runnable M2.6 example: optional fallback retrieval with source provenance."""

from __future__ import annotations

import argparse
import asyncio
from typing import Literal

from _shared_demo_helpers import (
    default_zotero_api_key,
    default_zotero_library_id,
    resolve_env_key,
    resolve_xai_key,
    try_build_provider,
)

from agt.config import Settings
from agt.guardrails import configure_guardrails, thread_context
from agt.tools.search_papers import search_papers


async def _run(query: str, limit: int, fallback_mode: Literal["auto", "force", "off"]) -> int:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": resolve_xai_key(),
        "AGT_ZOTERO_API_KEY": default_zotero_api_key(),
        "AGT_ZOTERO_LIBRARY_ID": default_zotero_library_id(),
        "AGT_SEMANTIC_SCHOLAR_API_KEY": resolve_env_key(
            "AGT_SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"
        ),
        "AGT_CORE_API_KEY": resolve_env_key("AGT_CORE_API_KEY", "CORE_API_KEY"),
        "AGT_DIMENSIONS_KEY": resolve_env_key("AGT_DIMENSIONS_KEY", "DIMENSIONS_KEY"),
        "AGT_SERPAPI_KEY": resolve_env_key("AGT_SERPAPI_KEY", "SERPAPI_KEY"),
        "AGT_ENABLE_FALLBACK_RETRIEVAL": fallback_mode != "off",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    configure_guardrails(settings)
    provider = try_build_provider(settings)

    with thread_context("example-m2-6"):
        papers, metadata = await search_papers(
            query=query,
            limit=limit,
            settings=settings,
            thread_id="example-m2-6",
            provider=provider,
            fallback_mode=fallback_mode,
        )

    print("M2.6 Fallback Retrieval Example")
    print(f"query: {query}")
    print(f"fallback mode: {fallback_mode}")
    print(f"total results: {len(papers)}")
    print(f"sources used: {', '.join(metadata.sources_used) if metadata.sources_used else 'none'}")
    print("-" * 80)

    for paper in papers:
        print(
            f"[{paper.index}] {paper.title}\n"
            f"  source: {paper.source}\n"
            f"  year: {paper.year if paper.year is not None else 'n/a'}\n"
            f"  score: {paper.score:.3f}"
        )
        print("-" * 80)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M2.6 fallback retrieval demo")
    parser.add_argument("--query", default="retrieval augmented generation in 2026")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--fallback-mode", choices=["auto", "force", "off"], default="auto")
    args = parser.parse_args()

    raise SystemExit(asyncio.run(_run(args.query, args.limit, args.fallback_mode)))


if __name__ == "__main__":
    main()
