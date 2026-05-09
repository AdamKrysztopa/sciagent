"""M2.7 example: SearchPlan inspection and filter contract demonstration (AGT-28).

Shows the typed SearchPlan produced before retrieval begins, including:
- hard_filters (min_year, exclusion keywords, etc.)
- soft_preferences
- source_policy with push-down capabilities
- filters_pushed_down per source
- filters_enforced_post_merge

Usage:
    uv run python examples/m2_7_search_plan_demo.py
    uv run python examples/m2_7_search_plan_demo.py --query "RAG techniques 2026 game changers"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

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
from agt.models import SearchPlan
from agt.tools.search_papers import search_papers

# The canonical AGT-28 acceptance criteria example.
_DEFAULT_QUERY = (
    "time-series forecasting methods selection based on the data itself, not older than 2024"
)


def _print_plan(plan: SearchPlan) -> None:
    print("\n── Search Plan ─────────────────────────────────────────────────────")
    print(f"  original_query : {plan.original_query[:80]}")
    print(f"  topic_query    : {plan.topic_query[:80]}")
    print(f"  rewritten_queries: {plan.rewritten_queries}")

    print("\n  Hard Filters (cannot be relaxed by LLM):")
    hf = plan.hard_filters
    print(f"    min_year        : {hf.min_year}")
    print(f"    max_year        : {hf.max_year}")
    print(f"    min_citations   : {hf.min_citations}")
    print(f"    max_citations   : {hf.max_citations}")
    print(f"    open_access_only: {hf.open_access_only}")
    print(f"    include_keywords: {hf.include_keywords}")
    print(f"    exclude_keywords: {hf.exclude_keywords}")

    print("\n  Soft Preferences (influence ranking, not hard filtering):")
    sp = plan.soft_preferences
    print(f"    positive_community_perception: {sp.require_positive_community_perception}")
    print(f"    min_semantic_score           : {sp.min_semantic_score}")

    print("\n  Source Policy:")
    for sc in plan.source_policy:
        tier_tag = f"[{sc.tier}]"
        print(
            f"    {sc.name:<20} {tier_tag:<12} "
            f"year_pushdown={sc.supports_year_filter}  oa_pushdown={sc.supports_open_access_filter}"
        )

    print("\n  Filters Pushed Down (per source):")
    if plan.filters_pushed_down:
        for src, filters in sorted(plan.filters_pushed_down.items()):
            print(f"    {src:<20} {filters}")
    else:
        print("    (none)")

    print("\n  Filters Enforced Post-Merge:")
    print(f"    {plan.filters_enforced_post_merge}")
    print("─" * 72)


async def _run(query: str) -> int:
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
    provider = try_build_provider(settings)

    print("M2.7 — Search Plan Demo (AGT-28)")
    print(f"query: {query}")
    print(f"provider: {'LLM rewrite' if provider else 'regex keywords (no LLM key)'}")

    try:
        with thread_context("example-m27"):
            papers, metadata = await search_papers(
                query=query,
                limit=5,
                settings=settings,
                thread_id="example-m27",
                provider=provider,
            )
    except Exception as exc:
        print(f"error: {exc}")
        return 1

    if metadata.search_plan:
        _print_plan(metadata.search_plan)
    else:
        print("(no search plan available)")

    print(f"\n  Results ({len(papers)} returned):")
    for paper in papers:
        yr = paper.year if paper.year else "?"
        doi = paper.doi if paper.doi else "n/a"
        oa = "OA" if paper.open_access else "  "
        print(f"  [{paper.index}] {oa} [{yr}] {paper.title[:70]}")
        print(f"       score={paper.score:.2f}  citations={paper.citation_count}  doi={doi}")

    print(f"\n  Sources used : {', '.join(metadata.sources_used)}")
    print(f"  Sources failed: {', '.join(metadata.sources_failed) or 'none'}")
    print(f"  Mode: {metadata.mode}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="M2.7 SearchPlan inspection demo")
    parser.add_argument("--query", default=_DEFAULT_QUERY)
    args = parser.parse_args()

    raise SystemExit(asyncio.run(_run(query=args.query)))


if __name__ == "__main__":
    main()
