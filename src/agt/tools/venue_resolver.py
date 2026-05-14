"""Venue/journal resolver using the OpenAlex /sources endpoint.

Searches OpenAlex /sources?search= for venues matching a text query.
Returns a list of :class:`~agt.models.ResolvedVenue` candidates.

Usage::

    from agt.tools.venue_resolver import resolve_venue

    venues = await resolve_venue("Nature", settings=settings)
"""

from __future__ import annotations

from typing import cast

import httpx

from agt.config import Settings, get_settings
from agt.models import ResolvedVenue

_OPENALEX_SOURCES = "https://api.openalex.org/sources"
_HTTP_OK = 200


async def resolve_venue(
    query: str,
    *,
    settings: Settings | None = None,
    limit: int = 5,
) -> list[ResolvedVenue]:
    """Search OpenAlex /sources?search= for venues matching the query.

    Parameters
    ----------
    query:
        Venue or journal name to search for (e.g. ``"Nature"``).
    settings:
        Settings instance. Defaults to :func:`get_settings`.
    limit:
        Max candidates to retrieve (default 5).
    """
    active = settings or get_settings()

    headers: dict[str, str] = {}
    if active.mailto:
        headers["User-Agent"] = f"SciAgent/0.1 mailto:{active.mailto}"

    params: dict[str, str | int] = {"search": query, "per-page": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_OPENALEX_SOURCES, params=params, headers=headers)
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

    venues: list[ResolvedVenue] = []
    for item_val in raw_results:
        if not isinstance(item_val, dict):
            continue
        item = cast("dict[str, object]", item_val)
        display_name_val: object = item.get("display_name", "")
        if not isinstance(display_name_val, str) or not display_name_val:
            continue
        display_name = display_name_val

        openalex_raw: object = item.get("id", "")
        openalex_id: str | None = None
        if isinstance(openalex_raw, str) and openalex_raw:
            openalex_id = openalex_raw.replace("https://openalex.org/", "")

        issn_raw: object = item.get("issn_l")
        issn: str | None = None
        if isinstance(issn_raw, str) and issn_raw:
            issn = issn_raw

        venues.append(
            ResolvedVenue(
                name=display_name,
                openalex_id=openalex_id,
                issn=issn,
            )
        )
    return venues
