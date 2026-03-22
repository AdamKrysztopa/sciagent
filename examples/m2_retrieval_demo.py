"""Runnable M2 example: retrieval + ranking + summarization with guardrails."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import httpx

from agt.config import Settings
from agt.guardrails import configure_guardrails, thread_context
from agt.providers.protocol import LLMProvider
from agt.providers.router import build_provider
from agt.tools.search_papers import search_papers
from agt.tools.semantic_scholar import SemanticScholarResponseError
from agt.tools.summarize import summarize_papers

_DUMMY_KEY = "xai-local"


def _resolve_xai_key() -> str:
    """Resolve xAI API key from environment variables or .env file."""
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
            if name.strip() in ("XAI_API_KEY", "AGT_XAI_API_KEY"):
                return value.strip().strip("\"'")
    return _DUMMY_KEY


def _try_build_provider(settings: Settings) -> LLMProvider | None:
    """Build an LLM provider for query rewriting when a real API key is set."""
    try:
        key = settings.xai_api_key.get_secret_value()
        if key == _DUMMY_KEY:
            return None
        return build_provider(settings)
    except Exception:
        return None


async def _run(query: str, limit: int) -> int:
    xai_key = _resolve_xai_key()
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": xai_key,
        "AGT_ZOTERO_API_KEY": os.getenv(
            "AGT_ZOTERO_API_KEY", os.getenv("ZOTERO_API_KEY", "zot-local")
        ),
        "AGT_ZOTERO_LIBRARY_ID": os.getenv(
            "AGT_ZOTERO_LIBRARY_ID", os.getenv("ZOTERO_LIBRARY_ID", "local-library")
        ),
        "AGT_SEMANTIC_SCHOLAR_API_KEY": os.getenv(
            "AGT_SEMANTIC_SCHOLAR_API_KEY", os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        ),
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    configure_guardrails(settings)
    provider = _try_build_provider(settings)

    try:
        with thread_context("example-m2"):
            papers = await search_papers(
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
