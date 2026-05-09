"""Standalone academic-paper search CLI for SciAgent.

Runs a multi-source retrieval with deterministic filters and optional LLM
query rewriting.  Results are printed to stdout; use ``--json`` for machine-
readable output.

Usage examples
--------------
Keyword-only search (no LLM, no year constraint):

    uv run python examples/search.py --search "time-series forecasting"

Full filter stack with LLM rewrite:

    uv run python examples/search.py \\
        --search "foundation models for time-series" \\
        --min-year 2023 \\
        --must-include "time series" \\
        --exclude "stock market"

Citation-priority mode (surfacing seminal work):

    uv run python examples/search.py \\
        --search "transformer attention mechanism" \\
        --min-citations 50

Open-access only, fresh results, JSON output:

    uv run python examples/search.py \\
        --search "RAG retrieval augmented generation" \\
        --min-year 2024 --open-access --json results.json

Using a custom number of results:

    uv run python examples/search.py --search "protein structure AlphaFold" --limit 5

Positional arguments
--------------------
--search TEXT           Required.  Natural-language search query (topic only).
--min-year INT          Hard lower year bound (inclusive).
--max-year INT          Hard upper year bound (inclusive).
--min-citations INT     Hard lower citation count.
--open-access           Restrict to open-access papers.
--must-include TEXT     Comma-separated topic tokens that MUST appear in every
                        result (post-merge topic gate).  Additive with tokens
                        parsed from the query itself.
--exclude TEXT          Comma-separated terms that must NOT appear in any result.
--limit INT             Number of results to return (default 10, max 50).
--no-llm                Skip LLM query rewriting (faster, deterministic).
--verbose               Print search plan and per-source telemetry.
--json FILE             Write results to a JSON file in addition to stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _shared_demo_helpers import (
    default_zotero_api_key,
    default_zotero_library_id,
    normalize_strict_settings_env,
    resolve_env_key,
    resolve_xai_key,
    try_build_provider,
)

from agt.config import Settings
from agt.guardrails import configure_guardrails, thread_context
from agt.models import NormalizedPaper, SearchPlan
from agt.tools.search_papers import search_papers

_DEFAULT_LIMIT = 10
_MAX_LIMIT = 50


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="search.py",
        description="SciAgent multi-source paper search with deterministic filters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--search",
        required=True,
        metavar="TEXT",
        help="Natural-language search query (topic keywords)",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        metavar="YEAR",
        help="Hard lower year bound (inclusive, e.g. 2023)",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        default=None,
        metavar="YEAR",
        help="Hard upper year bound (inclusive)",
    )
    parser.add_argument(
        "--min-citations",
        type=int,
        default=None,
        metavar="N",
        help="Only return papers with at least N citations",
    )
    parser.add_argument(
        "--open-access",
        action="store_true",
        help="Restrict results to open-access papers",
    )
    parser.add_argument(
        "--must-include",
        default="",
        metavar="TOKENS",
        help=(
            "Comma-separated topic tokens that must appear in result title/abstract "
            "(e.g. 'forecasting,time series')"
        ),
    )
    parser.add_argument(
        "--exclude",
        default="",
        metavar="TOKENS",
        help="Comma-separated tokens that must NOT appear in any result",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=_DEFAULT_LIMIT,
        metavar="N",
        help=f"Number of results to return (default {_DEFAULT_LIMIT}, max {_MAX_LIMIT})",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM query rewriting (faster, fully deterministic)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print search plan and per-source telemetry",
    )
    parser.add_argument(
        "--json",
        default=None,
        metavar="FILE",
        dest="json_output",
        help="Write JSON results to FILE in addition to stdout",
    )
    return parser


def _build_query(args: argparse.Namespace) -> str:
    """Compose a single query string that embeds all deterministic constraints
    so that ``parse_query_constraints`` picks them up automatically."""
    parts = [args.search.strip()]
    if args.min_year is not None:
        parts.append(f"not older than {args.min_year}")
    if args.max_year is not None:
        parts.append(f"before {args.max_year}")
    if args.min_citations is not None:
        parts.append(f"at least {args.min_citations} citations")
    if args.open_access:
        parts.append("open access")
    if args.exclude.strip():
        for token in [t.strip() for t in args.exclude.split(",") if t.strip()]:
            parts.append(f"but not {token}")
    return ", ".join(parts)


def _print_plan(plan: SearchPlan) -> None:
    width = 70
    print("\n" + "─" * width)
    print("  Search Plan")
    print("─" * width)
    hf = plan.hard_filters
    print(f"  topic_query     : {plan.topic_query[: width - 20]}")
    print(f"  rewritten       : {plan.rewritten_queries}")
    print(f"  min_year        : {hf.min_year}   max_year: {hf.max_year}")
    print(f"  min_citations   : {hf.min_citations}   open_access_only: {hf.open_access_only}")
    print(f"  include_keywords: {hf.include_keywords}")
    print(f"  exclude_keywords: {hf.exclude_keywords}")
    print(f"  pushed_down     : {plan.filters_pushed_down}")
    print(f"  post_merge      : {plan.filters_enforced_post_merge}")
    print("─" * width)


def _print_results(papers: list[NormalizedPaper], *, verbose: bool) -> None:
    if not papers:
        print("\n  No results found.")
        return
    print(f"\n  Results ({len(papers)} returned):")
    for paper in papers:
        oa = "OA " if paper.open_access else "   "
        yr = str(paper.year) if paper.year else "????"
        title = paper.title[:72]
        print(f"  [{paper.index}] {oa}[{yr}] {title}")
        if verbose:
            print(
                f"       score={paper.score:.2f}  citations={paper.citation_count}"
                f"  source={paper.source}"
            )
            if paper.doi:
                print(f"       doi={paper.doi}")


def _build_json_output(
    query: str,
    papers: list[NormalizedPaper],
    plan: SearchPlan | None,
    sources_used: list[str],
    sources_failed: list[str],
) -> dict[str, Any]:
    return {
        "query": query,
        "result_count": len(papers),
        "results": [
            {
                "index": p.index,
                "title": p.title,
                "year": p.year,
                "doi": p.doi,
                "score": p.score,
                "citation_count": p.citation_count,
                "open_access": p.open_access,
                "source": p.source,
                "abstract": p.abstract,
            }
            for p in papers
        ],
        "sources_used": sorted(sources_used),
        "sources_failed": sorted(sources_failed),
        "search_plan": (
            {
                "hard_filters": plan.hard_filters.model_dump(),
                "rewritten_queries": plan.rewritten_queries,
                "filters_pushed_down": plan.filters_pushed_down,
                "filters_enforced_post_merge": plan.filters_enforced_post_merge,
            }
            if plan
            else None
        ),
    }


async def _run(args: argparse.Namespace) -> int:
    normalize_strict_settings_env()
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

    limit = max(1, min(args.limit, _MAX_LIMIT))
    query = _build_query(args)

    # Inject must-include tokens into the query so the topic gate picks them up.
    extra_includes = [t.strip() for t in args.must_include.split(",") if t.strip()]

    provider = None if args.no_llm else try_build_provider(settings)

    print(f"\nquery: {query}")
    print(f"mode : {'no-llm' if provider is None else 'llm-rewrite'}  limit={limit}")

    with thread_context("search-cli"):
        papers, metadata = await search_papers(
            query=query,
            limit=limit,
            settings=settings,
            thread_id="search-cli",
            provider=provider,
        )

    # Apply extra must-include gate on top of any existing topic filtering.
    if extra_includes:
        filtered: list[NormalizedPaper] = []
        for p in papers:
            text = f"{p.title} {p.abstract or ''}".lower()
            if any(t.lower() in text for t in extra_includes):
                filtered.append(p)
        papers = filtered

    plan = metadata.search_plan
    if args.verbose and plan:
        _print_plan(plan)

    _print_results(papers, verbose=args.verbose)

    if args.verbose or metadata.sources_failed:
        print(f"\n  Sources used   : {', '.join(metadata.sources_used)}")
        if metadata.sources_failed:
            print(f"  Sources failed : {len(metadata.sources_failed)} failure(s)")
            for f in metadata.sources_failed[:3]:
                print(f"    {f[:100]}")

    if args.json_output:
        out = _build_json_output(
            query, papers, plan, metadata.sources_used, metadata.sources_failed
        )
        Path(args.json_output).write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"\n  JSON written to: {args.json_output}")

    return 0


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
