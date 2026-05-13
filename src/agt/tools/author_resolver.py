"""Author identity resolver across OpenAlex and Semantic Scholar.

Resolves a human name to a list of NormalizedAuthor records with
cross-provider identifiers. Deduplicates by ORCID when available.

Usage::

    from agt.tools.author_resolver import resolve_author

    authors = await resolve_author("Geoffrey Hinton", settings=settings)
"""

from __future__ import annotations

import asyncio
from typing import cast

import httpx

from agt.config import Settings, get_settings
from agt.models import NormalizedAuthor

_OPENALEX_AUTHORS = "https://api.openalex.org/authors"
_S2_AUTHOR_SEARCH = "https://api.semanticscholar.org/graph/v1/author/search"
_S2_FIELDS = "authorId,name,aliases"
_HTTP_OK = 200


async def _search_openalex(
    name: str,
    *,
    mailto: str | None,
    limit: int,
) -> list[NormalizedAuthor]:
    """Search OpenAlex /authors?search= endpoint."""
    headers: dict[str, str] = {}
    if mailto:
        headers["User-Agent"] = f"SciAgent/0.1 mailto:{mailto}"

    params: dict[str, str | int] = {"search": name, "per-page": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_OPENALEX_AUTHORS, params=params, headers=headers)
            if response.status_code != _HTTP_OK:
                return []
            raw_json: object = response.json()
    except Exception:  # pragma: no cover
        return []

    if not isinstance(raw_json, dict):
        return []
    data = cast("dict[str, object]", raw_json)
    raw_results_val: object = data.get("results", [])
    if not isinstance(raw_results_val, list):
        return []
    raw_results = cast("list[object]", raw_results_val)

    authors: list[NormalizedAuthor] = []
    for item_val in raw_results:
        if not isinstance(item_val, dict):
            continue
        item = cast("dict[str, object]", item_val)
        display_name_val: object = item.get("display_name", "")
        if not isinstance(display_name_val, str) or not display_name_val:
            continue
        display_name = display_name_val

        orcid_raw: object = item.get("orcid")
        orcid: str | None = None
        if isinstance(orcid_raw, str):
            orcid = orcid_raw.replace("https://orcid.org/", "")

        openalex_raw: object = item.get("id", "")
        openalex_id: str | None = None
        if isinstance(openalex_raw, str) and openalex_raw:
            openalex_id = openalex_raw.replace("https://openalex.org/", "")

        name_parts = display_name.rsplit(" ", 1)
        authors.append(
            NormalizedAuthor(
                name=display_name,
                family=name_parts[-1] if name_parts else None,
                given=name_parts[0] if len(name_parts) > 1 else None,
                orcid=orcid,
                openalex_id=openalex_id,
                source="openalex",
            )
        )
    return authors


async def _search_semantic_scholar(
    name: str,
    *,
    limit: int,
) -> list[NormalizedAuthor]:
    """Search Semantic Scholar /author/search endpoint."""
    params: dict[str, str | int] = {"query": name, "fields": _S2_FIELDS, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_S2_AUTHOR_SEARCH, params=params)
            if response.status_code != _HTTP_OK:
                return []
            raw_json: object = response.json()
    except Exception:  # pragma: no cover
        return []

    if not isinstance(raw_json, dict):
        return []
    data = cast("dict[str, object]", raw_json)
    raw_items_val: object = data.get("data", [])
    if not isinstance(raw_items_val, list):
        return []
    raw_items = cast("list[object]", raw_items_val)

    authors: list[NormalizedAuthor] = []
    for item_val in raw_items:
        if not isinstance(item_val, dict):
            continue
        item = cast("dict[str, object]", item_val)
        name_str_val: object = item.get("name", "")
        if not isinstance(name_str_val, str) or not name_str_val:
            continue
        name_str = name_str_val
        s2_id: object | None = item.get("authorId")
        authors.append(
            NormalizedAuthor(
                name=name_str,
                s2_author_id=str(s2_id) if s2_id is not None else None,
                source="semantic_scholar",
            )
        )
    return authors


def dedup_by_orcid(authors: list[NormalizedAuthor]) -> list[NormalizedAuthor]:
    """Merge authors with the same ORCID, preserving cross-provider IDs."""
    seen_orcid: dict[str, NormalizedAuthor] = {}
    no_orcid: list[NormalizedAuthor] = []

    for author in authors:
        if author.orcid is not None:
            if author.orcid in seen_orcid:
                existing = seen_orcid[author.orcid]
                updates: dict[str, object] = {}
                if existing.openalex_id is None and author.openalex_id is not None:
                    updates["openalex_id"] = author.openalex_id
                if existing.s2_author_id is None and author.s2_author_id is not None:
                    updates["s2_author_id"] = author.s2_author_id
                if updates:
                    seen_orcid[author.orcid] = existing.model_copy(update=updates)
            else:
                seen_orcid[author.orcid] = author
        else:
            no_orcid.append(author)

    return list(seen_orcid.values()) + no_orcid


async def resolve_author(
    name: str,
    *,
    settings: Settings | None = None,
    limit: int = 5,
) -> list[NormalizedAuthor]:
    """Resolve a human name to a list of NormalizedAuthor records.

    Queries OpenAlex and Semantic Scholar in parallel, then deduplicates
    results by ORCID. Returns an empty list on any network failure.

    Parameters
    ----------
    name:
        Author name to search for (e.g. ``"Geoffrey Hinton"``).
    settings:
        Settings instance. Defaults to :func:`get_settings`.
    limit:
        Max candidates to retrieve per source (default 5).
    """
    active = settings or get_settings()
    oa_task = _search_openalex(name, mailto=active.mailto, limit=limit)
    s2_task = _search_semantic_scholar(name, limit=limit)
    oa_results, s2_results = await asyncio.gather(oa_task, s2_task)
    return dedup_by_orcid(list(oa_results) + list(s2_results))
