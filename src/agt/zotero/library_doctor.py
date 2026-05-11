"""Read-only collection health scanner (SCI-0303)."""

from __future__ import annotations

from typing import Any, Literal, cast

import httpx

from agt.config import Settings
from agt.models import DoctorIssue, DoctorReport
from agt.tools.zotero_upsert import normalize_doi, title_author_fingerprint
from agt.zotero.collection_inspector import LibraryIndex, fetch_library_index

IssueType = Literal["missing_doi", "missing_abstract", "missing_pdf", "duplicate"]


def _item_key(item: dict[str, Any]) -> str:
    key = item.get("key")
    return str(key) if isinstance(key, str) else ""


def _item_data(item: dict[str, Any]) -> dict[str, object]:
    data_obj = item.get("data")
    if isinstance(data_obj, dict):
        return cast(dict[str, object], data_obj)
    return {}


def _item_title(data: dict[str, object]) -> str:
    return str(data.get("title") or "")


def _check_missing_doi(data: dict[str, object]) -> bool:
    return str(data.get("DOI") or "").strip() == ""


def _check_missing_abstract(data: dict[str, object]) -> bool:
    return str(data.get("abstractNote") or "").strip() == ""


def _check_missing_pdf(data: dict[str, object]) -> bool:
    """Lightweight check — does not fetch children; checks data-level URL fields."""
    has_url = bool(str(data.get("url") or "").strip())
    has_pdf_url = bool(str(data.get("pdf_url") or "").strip())
    return not has_url and not has_pdf_url


def _extract_authors(data: dict[str, object]) -> list[str]:
    creators_raw = data.get("creators", [])
    authors: list[str] = []
    if not isinstance(creators_raw, list):
        return authors
    for creator_obj in cast(list[object], creators_raw):
        if not isinstance(creator_obj, dict):
            continue
        creator = cast(dict[str, object], creator_obj)
        if creator.get("name"):
            authors.append(str(creator["name"]))
            continue
        first = str(creator.get("firstName") or "").strip()
        last = str(creator.get("lastName") or "").strip()
        combined = " ".join(p for p in [first, last] if p).strip()
        if combined:
            authors.append(combined)
    return authors


def _detect_duplicates(
    lib_index: LibraryIndex,
) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Return duplicate pairs (key_a, key_b) and a mapping key -> key_of_first_seen."""
    doi_to_key: dict[str, str] = {}
    fp_to_key: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []
    duplicate_of: dict[str, str] = {}  # key -> key of duplicate source

    for item in lib_index.items:
        key = _item_key(item)
        if not key:
            continue
        data = _item_data(item)
        title = _item_title(data)
        authors = _extract_authors(data)

        doi_value = data.get("DOI")
        doi = normalize_doi(doi_value if isinstance(doi_value, str) else None)
        if doi:
            if doi in doi_to_key:
                other = doi_to_key[doi]
                pair: tuple[str, str] = (other, key)
                if pair not in pairs:
                    pairs.append(pair)
                duplicate_of[key] = other
            else:
                doi_to_key[doi] = key

        if title.strip() and authors:
            fp = title_author_fingerprint(title, authors)
            if fp in fp_to_key:
                other_fp = fp_to_key[fp]
                pair_fp: tuple[str, str] = (other_fp, key)
                if pair_fp not in pairs:
                    pairs.append(pair_fp)
                if key not in duplicate_of:
                    duplicate_of[key] = other_fp
            else:
                fp_to_key[fp] = key

    return pairs, duplicate_of


async def scan_collection(
    collection_name: str,
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> DoctorReport:
    """Scan a Zotero collection for health issues.

    Checks each item for missing DOI, missing abstract, missing PDF URL,
    and duplicate detection (by DOI or title+author fingerprint).

    Note: PDF detection is limited to data-level URL fields; child attachment
    items are not fetched separately to keep this operation fast.
    """
    lib_index = await fetch_library_index(settings, collection_name=collection_name, client=client)

    dup_pairs, duplicate_of_map = _detect_duplicates(lib_index)

    issues: list[DoctorIssue] = []
    for item in lib_index.items:
        key = _item_key(item)
        if not key:
            continue
        data = _item_data(item)
        title = _item_title(data)

        issue_types: list[IssueType] = []
        if _check_missing_doi(data):
            issue_types.append("missing_doi")
        if _check_missing_abstract(data):
            issue_types.append("missing_abstract")
        if _check_missing_pdf(data):
            issue_types.append("missing_pdf")
        if key in duplicate_of_map:
            issue_types.append("duplicate")

        if issue_types:
            issues.append(
                DoctorIssue(
                    item_key=key,
                    title=title,
                    issue_types=issue_types,
                    duplicate_of=duplicate_of_map.get(key),
                )
            )

    return DoctorReport(
        collection_name=collection_name,
        total_items=len(lib_index.items),
        issues=issues,
        duplicate_pairs=dup_pairs,
    )
