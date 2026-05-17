"""Read-only Zotero library inspection used by SCI-0301, SCI-0303, SCI-0304."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

import httpx

from agt.config import Settings
from agt.credential_context import (
    resolve_zotero_api_key,
    resolve_zotero_library_id,
    resolve_zotero_library_type,
)
from agt.models import NormalizedPaper
from agt.tools.zotero_upsert import (
    ZOTERO_API_BASE,
    normalize_doi,
    title_author_fingerprint,
)

_PAGE_LIMIT = 500
_MAX_PAGES = 3


def _empty_str_frozenset() -> frozenset[str]:
    return frozenset()


def _empty_item_list() -> list[dict[str, Any]]:
    return []


@dataclass(slots=True)
class LibraryIndex:
    """In-memory snapshot of a Zotero library or collection used for classification."""

    doi_set: frozenset[str] = field(default_factory=_empty_str_frozenset)
    fingerprint_set: frozenset[str] = field(default_factory=_empty_str_frozenset)
    items: list[dict[str, Any]] = field(default_factory=_empty_item_list)


def _extract_doi_and_fingerprint(
    item: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Extract normalized DOI and title+author fingerprint from a raw Zotero item."""
    data_obj = item.get("data")
    if not isinstance(data_obj, dict):
        return None, None
    data = cast(dict[str, object], data_obj)

    doi_value = data.get("DOI")
    doi = normalize_doi(doi_value if isinstance(doi_value, str) else None)

    title = str(data.get("title") or "")
    creators_data = data.get("creators", [])
    authors: list[str] = []
    if isinstance(creators_data, list):
        creator_entries = cast(list[object], creators_data)
        for creator_obj in creator_entries:
            if not isinstance(creator_obj, dict):
                continue
            creator = cast(dict[str, object], creator_obj)
            if creator.get("name"):
                authors.append(str(creator["name"]))
                continue
            first_name = str(creator.get("firstName") or "").strip()
            last_name = str(creator.get("lastName") or "").strip()
            combined = " ".join(part for part in [first_name, last_name] if part).strip()
            if combined:
                authors.append(combined)

    fingerprint: str | None = None
    if title.strip() and authors:
        fingerprint = title_author_fingerprint(title, authors)

    return doi, fingerprint


async def _fetch_paginated(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    *,
    limit: int,
    max_pages: int,
) -> list[dict[str, Any]]:
    """Fetch up to max_pages pages from a Zotero list endpoint."""
    all_items: list[dict[str, Any]] = []
    start = 0
    for _ in range(max_pages):
        response = await client.get(url, headers=headers, params={"limit": limit, "start": start})
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, list):
            break
        raw_list = cast(list[object], raw)
        items_page: list[dict[str, Any]] = [
            cast(dict[str, Any], item) for item in raw_list if isinstance(item, dict)
        ]
        all_items.extend(items_page)
        if len(items_page) < limit:
            break
        start += limit
    return all_items


async def _resolve_collection_key(
    client: httpx.AsyncClient,
    prefix: str,
    headers: dict[str, str],
    collection_name: str,
) -> str | None:
    """Find the Zotero collection key by name via search."""
    response = await client.get(
        f"{prefix}/collections",
        headers=headers,
        params={"q": collection_name, "limit": 100},
    )
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        return None

    name_lower = collection_name.strip().casefold()
    for item_obj in cast(list[object], raw):
        if not isinstance(item_obj, dict):
            continue
        item = cast(dict[str, object], item_obj)
        data_obj = item.get("data")
        if not isinstance(data_obj, dict):
            continue
        data = cast(dict[str, object], data_obj)
        found_name = str(data.get("name", "")).strip().casefold()
        if found_name == name_lower:
            key = item.get("key")
            if isinstance(key, str):
                return key
    return None


async def fetch_library_index(
    settings: Settings,
    *,
    collection_name: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> LibraryIndex:
    """Fetch DOI and fingerprint sets from Zotero, optionally scoped to a collection.

    Returns an empty LibraryIndex if Zotero credentials are not configured.
    """
    try:
        api_key = resolve_zotero_api_key(settings)
        lib_id = resolve_zotero_library_id(settings)
    except ValueError:
        return LibraryIndex()

    lib_type = resolve_zotero_library_type(settings)
    prefix = f"/groups/{lib_id}" if lib_type == "group" else f"/users/{lib_id}"
    headers = {"Zotero-API-Key": api_key}

    owns_client = client is None
    api_client = client or httpx.AsyncClient(
        base_url=ZOTERO_API_BASE,
        timeout=settings.timeout_seconds,
    )

    try:
        if collection_name is not None:
            col_key = await _resolve_collection_key(api_client, prefix, headers, collection_name)
            if col_key is None:
                return LibraryIndex()
            url = f"{prefix}/collections/{col_key}/items/top"
            raw_items = await _fetch_paginated(
                api_client, url, headers, limit=_PAGE_LIMIT, max_pages=1
            )
        else:
            url = f"{prefix}/items/top"
            raw_items = await _fetch_paginated(
                api_client, url, headers, limit=_PAGE_LIMIT, max_pages=_MAX_PAGES
            )
    finally:
        if owns_client:
            await api_client.aclose()

    doi_set: set[str] = set()
    fingerprint_set: set[str] = set()
    for item in raw_items:
        doi, fingerprint = _extract_doi_and_fingerprint(item)
        if doi:
            doi_set.add(doi)
        if fingerprint:
            fingerprint_set.add(fingerprint)

    return LibraryIndex(
        doi_set=frozenset(doi_set),
        fingerprint_set=frozenset(fingerprint_set),
        items=raw_items,
    )


def classify_paper(
    paper: NormalizedPaper,
    index: LibraryIndex,
) -> Literal["new", "in_library", "possible_duplicate"]:
    """Classify a paper against a LibraryIndex.

    Returns:
        "in_library"          — DOI matches an existing item exactly.
        "possible_duplicate"  — Title+author fingerprint matches but DOI does not.
        "new"                 — No match found.
    """
    doi = normalize_doi(paper.doi)
    if doi is not None and doi in index.doi_set:
        return "in_library"

    fingerprint = title_author_fingerprint(paper.title, [a.name for a in paper.authors])
    if fingerprint in index.fingerprint_set:
        return "possible_duplicate"

    return "new"
