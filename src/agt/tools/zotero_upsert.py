"""Zotero upsert tool adapter."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal, cast

import httpx

from agt.config import Settings, get_settings
from agt.guardrails import current_thread_id, get_guardrails
from agt.models import CollectionResult, ItemWriteOutcome, NormalizedPaper, WriteResult

ZOTERO_API_BASE = "https://api.zotero.org"
HTTP_CREATED = 201
HTTP_OK = 200
MIN_VALID_PUBLICATION_YEAR = 1000


class ZoteroWriteError(RuntimeError):
    """Raised when Zotero write flow cannot proceed."""


@dataclass(slots=True)
class _CreateItemRequest:
    endpoint: str
    headers: dict[str, str]


def _library_prefix(settings: Settings) -> str:
    if settings.zotero_library_type == "group":
        return f"/groups/{settings.zotero_library_id}"
    return f"/users/{settings.zotero_library_id}"


def _normalize_collection_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


def _normalize_doi(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    cleaned = cleaned.removeprefix("doi:")
    return cleaned or None


def _normalize_author(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _title_author_fingerprint(title: str, authors: list[str]) -> str:
    normalized_title = " ".join(title.strip().split()).casefold()
    normalized_authors = "|".join(_normalize_author(author) for author in authors if author.strip())
    raw = f"{normalized_title}::{normalized_authors}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _split_creator_name(full_name: str) -> tuple[str, str]:
    cleaned = " ".join(full_name.strip().split())
    if "," in cleaned:
        family, given = [part.strip() for part in cleaned.split(",", 1)]
        return given, family

    parts = cleaned.split(" ")
    if len(parts) <= 1:
        return "", cleaned
    return " ".join(parts[:-1]), parts[-1]


def _map_item_type(paper: NormalizedPaper) -> Literal["journalArticle", "preprint"]:
    if paper.source in {"arxiv", "europe_pmc_preprint"}:
        return "preprint"
    return "journalArticle"


def _map_paper_to_item(paper: NormalizedPaper, collection_key: str) -> dict[str, Any]:
    item_type = _map_item_type(paper)
    creators: list[dict[str, Any]] = []
    for author in paper.authors:
        first_name, last_name = _split_creator_name(author)
        creators.append({
            "creatorType": "author",
            "firstName": first_name,
            "lastName": last_name,
        })

    item: dict[str, Any] = {
        "itemType": item_type,
        "title": paper.title.strip(),
        "creators": creators,
        "date": str(paper.year) if paper.year is not None else "",
        "url": paper.url or "",
        "DOI": paper.doi or "",
        "abstractNote": paper.abstract or "",
        "collections": [collection_key],
        "extra": f"SciAgent source: {paper.source}",
    }
    if item_type == "preprint":
        item["archive"] = paper.source
        item["archiveID"] = paper.arxiv_id or ""
    return item


def _validate_item_payload(item: dict[str, Any], paper: NormalizedPaper) -> str | None:
    if not item.get("title"):
        return "Missing title"
    creators_obj = item.get("creators", [])
    if not isinstance(creators_obj, list) or not creators_obj:
        return "Missing authors"
    creators = cast(list[object], creators_obj)
    for creator_obj in creators:
        if not isinstance(creator_obj, dict):
            return "Invalid author name"
        creator = cast(dict[str, object], creator_obj)
        if not creator.get("lastName"):
            return "Invalid author name"
    if paper.year is not None and paper.year < MIN_VALID_PUBLICATION_YEAR:
        return "Invalid publication year"
    return None


def _collection_parent_key(
    collections_payload: list[dict[str, object]],
    parent_collection_name: str,
) -> str | None:
    target = _normalize_collection_name(parent_collection_name)
    for collection in collections_payload:
        data_obj = collection.get("data")
        if not isinstance(data_obj, dict):
            continue
        data = cast(dict[str, object], data_obj)
        if _normalize_collection_name(str(data.get("name", ""))) == target:
            key = collection.get("key")
            return key if isinstance(key, str) else None
    return None


def _extract_created_key(payload: dict[str, object], index: int) -> str | None:
    successful_obj = payload.get("successful")
    if not isinstance(successful_obj, dict):
        return None
    successful = cast(dict[str, object], successful_obj)
    entry_obj = successful.get(str(index))
    if not isinstance(entry_obj, dict):
        return None
    entry = cast(dict[str, object], entry_obj)
    key = entry.get("key")
    if isinstance(key, str):
        return key
    return None


def _extract_failed_message(payload: dict[str, object], index: int) -> str:
    failed_obj = payload.get("failed")
    if not isinstance(failed_obj, dict):
        return "Zotero rejected item payload"
    failed = cast(dict[str, object], failed_obj)
    entry_obj = failed.get(str(index))
    if not isinstance(entry_obj, dict):
        return "Zotero rejected item payload"
    entry = cast(dict[str, object], entry_obj)
    message = entry.get("message")
    if isinstance(message, str) and message.strip():
        return message
    return "Zotero rejected item payload"


def _find_reusable_collection(
    collections_payload: list[dict[str, object]],
    *,
    normalized_name: str,
    parent_key: str | None,
    requested_name: str,
) -> CollectionResult | None:
    for collection in collections_payload:
        data_obj = collection.get("data")
        if not isinstance(data_obj, dict):
            continue
        data = cast(dict[str, object], data_obj)
        if _normalize_collection_name(str(data.get("name", ""))) != normalized_name:
            continue

        existing_parent = data.get("parentCollection")
        if parent_key is not None and existing_parent != parent_key:
            continue
        if parent_key is None and existing_parent is not None:
            continue

        key = collection.get("key")
        if isinstance(key, str):
            return CollectionResult(
                key=key,
                name=str(data.get("name") or requested_name.strip()),
                parent_key=parent_key,
                reused=True,
            )
    return None


async def _resolve_collection(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    collection_name: str,
    parent_collection_name: str | None,
) -> CollectionResult:
    headers = {"Zotero-API-Key": settings.zotero_api_key.get_secret_value()}
    prefix = _library_prefix(settings)
    list_resp = await client.get(f"{prefix}/collections", headers=headers, params={"limit": 200})
    list_resp.raise_for_status()
    collections_raw = list_resp.json()
    if not isinstance(collections_raw, list):
        raise ZoteroWriteError("Malformed collections response from Zotero")
    collections_list = cast(list[object], collections_raw)
    collections_payload = [
        cast(dict[str, object], collection)
        for collection in collections_list
        if isinstance(collection, dict)
    ]

    normalized_name = _normalize_collection_name(collection_name)
    parent_key: str | None = None
    if parent_collection_name is not None and parent_collection_name.strip():
        parent_key = _collection_parent_key(collections_payload, parent_collection_name)
        if parent_key is None:
            raise ZoteroWriteError("Parent collection not found")

    existing = _find_reusable_collection(
        collections_payload,
        normalized_name=normalized_name,
        parent_key=parent_key,
        requested_name=collection_name,
    )
    if existing is not None:
        return existing

    create_payload: dict[str, object] = {"name": collection_name.strip()}
    if parent_key is not None:
        create_payload["parentCollection"] = parent_key
    create_resp = await client.post(f"{prefix}/collections", headers=headers, json=[create_payload])
    if create_resp.status_code not in {HTTP_OK, HTTP_CREATED}:
        raise ZoteroWriteError(f"Failed to create collection: {create_resp.text}")
    created_payload_obj = create_resp.json()
    if not isinstance(created_payload_obj, dict):
        raise ZoteroWriteError("Collection creation response malformed")
    created_payload = cast(dict[str, object], created_payload_obj)
    created_key = _extract_created_key(created_payload, 0)
    if created_key is None:
        raise ZoteroWriteError("Collection creation response missing key")
    return CollectionResult(
        key=created_key,
        name=collection_name.strip(),
        parent_key=parent_key,
        reused=False,
    )


async def _fetch_existing_signatures(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    collection_key: str,
) -> tuple[set[str], set[str]]:
    headers = {"Zotero-API-Key": settings.zotero_api_key.get_secret_value()}
    prefix = _library_prefix(settings)
    response = await client.get(
        f"{prefix}/collections/{collection_key}/items/top",
        headers=headers,
        params={"limit": 200},
    )
    response.raise_for_status()
    payload_raw = response.json()
    if not isinstance(payload_raw, list):
        raise ZoteroWriteError("Malformed existing items response from Zotero")
    payload_list = cast(list[object], payload_raw)
    payload = [cast(dict[str, object], item) for item in payload_list if isinstance(item, dict)]

    doi_set: set[str] = set()
    fingerprint_set: set[str] = set()
    for item in payload:
        data_obj = item.get("data")
        if not isinstance(data_obj, dict):
            continue
        data = cast(dict[str, object], data_obj)

        doi_value = data.get("DOI")
        doi = _normalize_doi(doi_value if isinstance(doi_value, str) else None)
        if doi:
            doi_set.add(doi)

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
        if title.strip() and authors:
            fingerprint_set.add(_title_author_fingerprint(title, authors))

    return doi_set, fingerprint_set


@dataclass(slots=True)
class UpsertResult:
    """Backward-compatible alias for tests that mock upsert results."""

    created: int = 0
    unchanged: int = 0
    failed: int = 0


def _failure_is_retry_safe(status_code: int | None) -> bool:
    return status_code in {429, 500, 502, 503, 504}


def _empty_collection_name_result(papers: list[NormalizedPaper]) -> WriteResult:
    outcomes = [
        ItemWriteOutcome(
            index=index,
            title=paper.title,
            status="failed",
            reason="Collection name cannot be empty",
            retry_safe=False,
        )
        for index, paper in enumerate(papers)
    ]
    return WriteResult(
        created=0,
        unchanged=0,
        failed=len(papers),
        collection=CollectionResult(key="", name="", parent_key=None, reused=False),
        outcomes=outcomes,
        retry_safe_failures=0,
    )


def _unchanged_outcome(index: int, paper: NormalizedPaper, strategy: str) -> ItemWriteOutcome:
    if strategy == "doi":
        return ItemWriteOutcome(
            index=index,
            title=paper.title,
            status="unchanged",
            reason="Duplicate DOI detected",
            duplicate_strategy="doi",
            retry_safe=True,
        )
    return ItemWriteOutcome(
        index=index,
        title=paper.title,
        status="unchanged",
        reason="Duplicate title+author hash detected",
        duplicate_strategy="title_author_hash",
        retry_safe=True,
    )


async def _create_item(
    *,
    client: httpx.AsyncClient,
    request: _CreateItemRequest,
    payload: dict[str, Any],
    paper: NormalizedPaper,
    index: int,
) -> tuple[ItemWriteOutcome, bool]:
    create_resp = await client.post(request.endpoint, headers=request.headers, json=[payload])
    if create_resp.status_code not in {HTTP_OK, HTTP_CREATED}:
        failure_reason = f"Zotero create failed: {create_resp.text}"
        safe = _failure_is_retry_safe(create_resp.status_code)
        return (
            ItemWriteOutcome(
                index=index,
                title=paper.title,
                status="failed",
                reason=failure_reason,
                retry_safe=safe,
            ),
            safe,
        )

    create_payload_obj = create_resp.json()
    if not isinstance(create_payload_obj, dict):
        return (
            ItemWriteOutcome(
                index=index,
                title=paper.title,
                status="failed",
                reason="Malformed create response from Zotero",
                retry_safe=False,
            ),
            False,
        )
    create_payload = cast(dict[str, object], create_payload_obj)
    item_key = _extract_created_key(create_payload, 0)
    if item_key is None:
        return (
            ItemWriteOutcome(
                index=index,
                title=paper.title,
                status="failed",
                reason=_extract_failed_message(create_payload, 0),
                retry_safe=False,
            ),
            False,
        )

    return (
        ItemWriteOutcome(
            index=index,
            title=paper.title,
            status="created",
            item_key=item_key,
            retry_safe=True,
        ),
        False,
    )


async def _upsert_with_client(
    *,
    collection_name: str,
    papers: list[NormalizedPaper],
    settings: Settings,
    parent_collection_name: str | None,
    client: httpx.AsyncClient,
) -> WriteResult:
    collection = await _resolve_collection(
        client=client,
        settings=settings,
        collection_name=collection_name,
        parent_collection_name=parent_collection_name,
    )

    existing_dois, existing_fingerprints = await _fetch_existing_signatures(
        client=client,
        settings=settings,
        collection_key=collection.key,
    )

    create_request = _CreateItemRequest(
        endpoint=f"{_library_prefix(settings)}/items",
        headers={"Zotero-API-Key": settings.zotero_api_key.get_secret_value()},
    )

    created = 0
    unchanged = 0
    failed = 0
    retry_safe_failures = 0
    outcomes: list[ItemWriteOutcome] = []

    for index, paper in enumerate(papers):
        payload = _map_paper_to_item(paper, collection.key)
        validation_error = _validate_item_payload(payload, paper)
        if validation_error is not None:
            failed += 1
            outcomes.append(
                ItemWriteOutcome(
                    index=index,
                    title=paper.title,
                    status="failed",
                    reason=validation_error,
                    retry_safe=False,
                )
            )
            continue

        doi = _normalize_doi(paper.doi)
        fingerprint = _title_author_fingerprint(paper.title, paper.authors)
        if doi is not None and doi in existing_dois:
            unchanged += 1
            outcomes.append(_unchanged_outcome(index, paper, "doi"))
            continue
        if fingerprint in existing_fingerprints:
            unchanged += 1
            outcomes.append(_unchanged_outcome(index, paper, "title_author_hash"))
            continue

        try:
            outcome, safe_failure = await _create_item(
                client=client,
                request=create_request,
                payload=payload,
                paper=paper,
                index=index,
            )
        except httpx.HTTPError as exc:
            response = exc.response if isinstance(exc, httpx.HTTPStatusError) else None
            safe_failure = _failure_is_retry_safe(response.status_code) if response else False
            outcome = ItemWriteOutcome(
                index=index,
                title=paper.title,
                status="failed",
                reason=f"HTTP error while writing item: {exc}",
                retry_safe=safe_failure,
            )

        outcomes.append(outcome)
        if outcome.status == "created":
            created += 1
            if doi is not None:
                existing_dois.add(doi)
            existing_fingerprints.add(fingerprint)
            continue

        if outcome.status == "failed":
            failed += 1
            if safe_failure:
                retry_safe_failures += 1

    return WriteResult(
        created=created,
        unchanged=unchanged,
        failed=failed,
        collection=collection,
        outcomes=outcomes,
        retry_safe_failures=retry_safe_failures,
    )


async def upsert_papers(
    collection_name: str,
    papers: list[NormalizedPaper],
    *,
    settings: Settings | None = None,
    parent_collection_name: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> WriteResult:
    """Upsert papers into Zotero with deterministic deduplication and typed outcomes."""

    resolved_settings = settings or get_settings()
    get_guardrails().acquire("zotero", current_thread_id())
    if not collection_name.strip():
        return _empty_collection_name_result(papers)

    owns_client = client is None
    api_client = client or httpx.AsyncClient(
        base_url=ZOTERO_API_BASE,
        timeout=resolved_settings.timeout_seconds,
    )

    try:
        return await _upsert_with_client(
            collection_name=collection_name,
            papers=papers,
            settings=resolved_settings,
            parent_collection_name=parent_collection_name,
            client=api_client,
        )
    finally:
        if owns_client:
            await api_client.aclose()
