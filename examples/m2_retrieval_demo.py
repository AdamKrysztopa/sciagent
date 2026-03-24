"""Runnable M2 example: retrieval + ranking + summarization with guardrails."""

from __future__ import annotations

import argparse
import asyncio

import httpx
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
from agt.tools.semantic_scholar import SemanticScholarResponseError
from agt.tools.summarize import summarize_papers


async def _run(query: str, limit: int) -> int:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": resolve_xai_key(),
        "AGT_ZOTERO_API_KEY": default_zotero_api_key(),
        "AGT_ZOTERO_LIBRARY_ID": default_zotero_library_id(),
        "AGT_SEMANTIC_SCHOLAR_API_KEY": resolve_env_key(
            "AGT_SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"
        ),
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    configure_guardrails(settings)
    provider = try_build_provider(settings)

    try:
        with thread_context("example-m2"):
            papers, metadata = await search_papers(
                query=query,
                limit=limit,
                settings=settings,
                thread_id="example-m2",
                provider=provider,
            )
    except httpx.HTTPStatusError as exc:
        print("M2 Retrieval Example")
        print("mode: live Semantic Scholar")
        print(f"query: {query}")
        print(f"error: HTTP {exc.response.status_code} from Semantic Scholar")
        print("hint: retry later or narrow query terms")
        return 1
    except SemanticScholarResponseError as exc:
        print("M2 Retrieval Example")
        print("mode: live Semantic Scholar")
        print(f"query: {query}")
        print(f"error: {exc}")
        print("hint: Semantic Scholar returned a non-standard response; retry later")
        return 1

    papers = await summarize_papers(
        papers,
        provider=None,
        use_llm=False,
        max_sentences=settings.summarization_max_sentences,
    )

    print("M2 Retrieval Example")
    mode = "live search + LLM rewrite" if provider else "live search (regex keywords)"
    print(f"mode: {mode}")
    print(f"query: {query}")
    print(f"results: {len(papers)}")
    print(f"sources used: {', '.join(metadata.sources_used) if metadata.sources_used else 'none'}")
    print(
        f"sources failed: {', '.join(metadata.sources_failed) if metadata.sources_failed else 'none'}"
    )
    print(f"retry count: {metadata.retry_count}")
    print("-" * 80)

    for paper in papers:
        summary = (paper.summary or "").strip()
        index = paper.index if paper.index is not None else -1
        doi = paper.doi if paper.doi is not None else "n/a"
        year = paper.year if paper.year is not None else "n/a"
        print(f"[{index}] {paper.title}\n  year: {year}\n  score: {paper.score:.3f}\n  doi: {doi}")
        if summary:
            print(f"  summary: {summary}")
        print("-" * 80)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M2 retrieval/ranking/summarization example")
    parser.add_argument("--query", default="retrieval augmented generation")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    raise SystemExit(asyncio.run(_run(query=args.query, limit=args.limit)))


if __name__ == "__main__":
    main()
