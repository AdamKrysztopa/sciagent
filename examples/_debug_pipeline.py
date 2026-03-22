"""Temporary debug script for tracing the search pipeline."""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("AGT_XAI_API_KEY", "xai-local")
os.environ.setdefault("AGT_ZOTERO_API_KEY", "zot-local")
os.environ.setdefault("AGT_ZOTERO_LIBRARY_ID", "local")
os.environ.setdefault("AGT_SUMMARIZATION_USE_LLM", "false")

from agt.config import Settings
from agt.guardrails import configure_guardrails
from agt.tools.crossref import CrossrefClient
from agt.tools.openalex import OpenAlexClient
from agt.tools.query_constraints import apply_query_constraints, parse_query_constraints
from agt.tools.ranking import rank_and_index_papers


async def main() -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-local",
        "AGT_ZOTERO_API_KEY": "zot-local",
        "AGT_ZOTERO_LIBRARY_ID": "local",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    configure_guardrails(settings)

    query = "the most cited 2020 and newer timeseries papers - list 5"
    _MIN_QUERY_LENGTH = 3
    constraints = parse_query_constraints(query, default_limit=5)
    retrieval_query = " ".join(constraints.keywords.include_keywords)
    if len(retrieval_query) < _MIN_QUERY_LENGTH:
        retrieval_query = query
    print(f"retrieval_query: {retrieval_query!r}")
    print(f"min_year={constraints.year.min_year}, min_cit={constraints.citations.min_citations}")
    print(f"keywords={constraints.keywords.include_keywords}")

    results = []
    oa = OpenAlexClient(timeout_seconds=15, retries=2)
    cr = CrossrefClient(timeout_seconds=15, retries=2)
    try:
        oa_results = await oa.search(
            query=retrieval_query,
            limit=15,
            year_min=constraints.year.min_year,
        )
        results.extend(oa_results)
        print(f"OpenAlex returned {len(oa_results)} papers")
        for p in oa_results[:5]:
            print(f"  OA: {p.title} | year={p.year} | cit={p.citation_count}")
    except Exception as e:
        print(f"OpenAlex failed: {e}")
    try:
        cr_results = await cr.search(query=retrieval_query, limit=15)
        results.extend(cr_results)
        print(f"Crossref returned {len(cr_results)} papers")
        for p in cr_results[:5]:
            print(f"  CR: {p.title} | year={p.year} | cit={p.citation_count}")
    except Exception as e:
        print(f"Crossref failed: {e}")

    ranked = rank_and_index_papers(results)
    print(f"After rank: {len(ranked)} papers")
    for p in ranked[:5]:
        print(f"  {p.title} | year={p.year} | cit={p.citation_count}")

    filtered = apply_query_constraints(ranked, constraints)
    print(f"After filter: {len(filtered)} papers")
    for p in filtered[:5]:
        print(f"  {p.title} | year={p.year} | cit={p.citation_count}")


if __name__ == "__main__":
    asyncio.run(main())
