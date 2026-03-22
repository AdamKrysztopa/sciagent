"""Runnable M2.6 example: optional fallback retrieval with source provenance."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Literal

from agt.config import Settings
from agt.guardrails import configure_guardrails, thread_context
from agt.providers.protocol import LLMProvider
from agt.providers.router import build_provider
from agt.tools.search_papers import search_papers

_DUMMY_KEY = "xai-local"


def _resolve_xai_key() -> str:
    key = os.getenv("AGT_XAI_API_KEY") or os.getenv("XAI_API_KEY")
    if key:
        return key
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            name, _, value = stripped.partition("=")
            if name.strip() in ("AGT_XAI_API_KEY", "XAI_API_KEY"):
                return value.strip().strip("\"'")
    return _DUMMY_KEY


def _try_build_provider(settings: Settings) -> LLMProvider | None:
    try:
        key = settings.xai_api_key.get_secret_value()
        if key == _DUMMY_KEY:
            return None
        return build_provider(settings)
    except Exception:
        return None


async def _run(query: str, limit: int, fallback_mode: Literal["auto", "force", "off"]) -> int:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": _resolve_xai_key(),
        "AGT_ZOTERO_API_KEY": os.getenv(
            "AGT_ZOTERO_API_KEY", os.getenv("ZOTERO_API_KEY", "zot-local")
        ),
        "AGT_ZOTERO_LIBRARY_ID": os.getenv(
            "AGT_ZOTERO_LIBRARY_ID", os.getenv("ZOTERO_LIBRARY_ID", "local-library")
        ),
        "AGT_SEMANTIC_SCHOLAR_API_KEY": os.getenv(
            "AGT_SEMANTIC_SCHOLAR_API_KEY", os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        ),
        "AGT_CORE_API_KEY": os.getenv("AGT_CORE_API_KEY", os.getenv("CORE_API_KEY")),
        "AGT_DIMENSIONS_KEY": os.getenv("AGT_DIMENSIONS_KEY", os.getenv("DIMENSIONS_KEY")),
        "AGT_SERPAPI_KEY": os.getenv("AGT_SERPAPI_KEY", os.getenv("SERPAPI_KEY")),
        "AGT_ENABLE_FALLBACK_RETRIEVAL": fallback_mode != "off",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    configure_guardrails(settings)
    provider = _try_build_provider(settings)

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
