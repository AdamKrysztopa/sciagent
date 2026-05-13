"""LLM-powered collection gap analysis (SCI-0304)."""

from __future__ import annotations

from typing import Any, cast

import httpx
import structlog

from agt.config import Settings
from agt.models import GapSuggestion, NormalizedPaper
from agt.providers.protocol import LLMProvider
from agt.tools.query_rewriter import extract_json
from agt.tools.search_papers import search_papers
from agt.tools.zotero_upsert import normalize_doi, title_author_fingerprint
from agt.zotero.collection_inspector import LibraryIndex, classify_paper, fetch_library_index

_MAX_TITLES_IN_PROMPT = 30
_QUERIES_PER_GAP = 5
_RESULTS_PER_QUERY = 5
_MAX_GAP_PAPERS = 15

_logger = structlog.get_logger("agt.gap_finder")

_GAP_PROMPT = """\
You are a research librarian. Given these paper titles from a Zotero collection named "{collection_name}":

{titles}

Suggest 3-5 focused academic search queries to find important papers likely MISSING from this collection.
Think about: seminal foundational works, recent follow-ups (last 2 years), systematic reviews, \
papers from different methodological approaches, negative results.

Return ONLY a JSON object:
{{"reasoning": "one sentence on what the gaps seem to be", "queries": ["query1", "query2", ...]}}"""


def _build_title_list(items: list[dict[str, Any]], max_titles: int) -> list[str]:
    """Extract up to max_titles paper titles from raw Zotero items."""
    titles: list[str] = []
    for item in items:
        data_obj = item.get("data")
        if not isinstance(data_obj, dict):
            continue
        data = cast(dict[str, object], data_obj)
        title = str(data.get("title") or "").strip()
        if title:
            titles.append(title)
        if len(titles) >= max_titles:
            break
    return titles


def _is_already_in_library(paper: NormalizedPaper, lib_index: LibraryIndex) -> bool:
    return classify_paper(paper, lib_index) == "in_library"


def _deduplicate_papers(papers: list[NormalizedPaper]) -> list[NormalizedPaper]:
    """Remove duplicate papers from gap results by DOI or fingerprint."""
    seen_dois: set[str] = set()
    seen_fps: set[str] = set()
    unique: list[NormalizedPaper] = []
    for paper in papers:
        doi = normalize_doi(paper.doi)
        fp = title_author_fingerprint(paper.title, [a.name for a in paper.authors])
        if doi is not None and doi in seen_dois:
            continue
        if fp in seen_fps:
            continue
        if doi is not None:
            seen_dois.add(doi)
        seen_fps.add(fp)
        unique.append(paper)
    return unique


async def find_gaps(
    collection_name: str,
    settings: Settings,
    provider: LLMProvider,
    *,
    client: httpx.AsyncClient | None = None,
) -> GapSuggestion:
    """Find papers likely missing from a Zotero collection using LLM query generation.

    Steps:
    1. Fetch the library index for the given collection.
    2. Build a prompt with existing paper titles and ask the LLM for search queries.
    3. For each query, call search_papers and filter out already-present papers.
    4. Deduplicate and return up to _MAX_GAP_PAPERS suggestions.

    Returns an empty GapSuggestion on any LLM or search failure.
    """
    lib_index = await fetch_library_index(settings, collection_name=collection_name, client=client)

    titles = _build_title_list(lib_index.items, _MAX_TITLES_IN_PROMPT)
    if not titles:
        return GapSuggestion(
            reasoning="Collection is empty or not accessible; cannot suggest gaps.",
            papers=[],
        )

    titles_text = "\n".join(f"- {t}" for t in titles)
    prompt = _GAP_PROMPT.format(collection_name=collection_name, titles=titles_text)

    try:
        llm_response = await provider.ainvoke(prompt)
    except Exception:
        return GapSuggestion(reasoning="LLM invocation failed.", papers=[])

    parsed = extract_json(llm_response)
    if parsed is None:
        return GapSuggestion(reasoning="Could not parse LLM gap analysis response.", papers=[])

    reasoning = str(parsed.get("reasoning", "")).strip()
    queries_raw = parsed.get("queries", [])
    queries: list[str] = []
    if isinstance(queries_raw, list):
        for q_obj in cast(list[object], queries_raw):
            q = str(q_obj).strip()
            if q:
                queries.append(q)

    if not queries:
        return GapSuggestion(reasoning=reasoning or "No queries suggested.", papers=[])

    gap_papers: list[NormalizedPaper] = []
    for query in queries[:_QUERIES_PER_GAP]:
        try:
            results, _ = await search_papers(query, limit=_RESULTS_PER_QUERY, settings=settings)
        except Exception as exc:
            _logger.warning("gap_finder_search_failed", query=query, error=str(exc))
            continue
        for paper in results:
            if not _is_already_in_library(paper, lib_index):
                gap_papers.append(paper)

    gap_papers = _deduplicate_papers(gap_papers)

    return GapSuggestion(
        reasoning=reasoning or "Gap analysis complete.",
        papers=gap_papers[:_MAX_GAP_PAPERS],
    )
