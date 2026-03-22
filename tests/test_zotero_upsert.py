from __future__ import annotations

from typing import Any

import httpx
import pytest

from agt.config import Settings
from agt.models import NormalizedPaper
from agt.tools.zotero_upsert import upsert_papers

EXPECTED_VALIDATION_FAILURES = 2


def _settings() -> Settings:
    return Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_ZOTERO_LIBRARY_TYPE": "user",
    })


def _paper(
    *,
    title: str = "Paper A",
    doi: str | None = "10.1000/example",
    authors: list[str] | None = None,
) -> NormalizedPaper:
    return NormalizedPaper(
        title=title,
        doi=doi,
        authors=authors if authors is not None else ["Ada Lovelace"],
        year=2024,
        source="semantic_scholar",
    )


def _match(path: str, expected: str) -> bool:
    return path == expected


@pytest.mark.anyio
async def test_collection_resolver_reuses_canonical_name_with_parent() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {"key": "PARENT1", "data": {"name": "Parent Folder", "parentCollection": None}},
                    {"key": "CHILD1", "data": {"name": "My Inbox", "parentCollection": "PARENT1"}},
                ],
            )
        if (
            _match(request.url.path, "/users/12345/collections/CHILD1/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="  my   inbox  ",
        papers=[],
        settings=_settings(),
        parent_collection_name="parent folder",
        client=client,
    )
    await client.aclose()

    assert result.collection.key == "CHILD1"
    assert result.collection.reused is True
    assert result.collection.parent_key == "PARENT1"
    assert all(call != "POST /users/12345/collections" for call in calls)


@pytest.mark.anyio
async def test_mapper_and_validation_fail_before_write_call() -> None:
    posted_items = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posted_items
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=[])
        if _match(request.url.path, "/users/12345/items") and request.method == "POST":
            posted_items += 1
            return httpx.Response(200, json={"successful": {"0": {"key": "I1"}}})
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="Inbox",
        papers=[
            _paper(title="", doi="10.1000/bad-title"),
            _paper(title="Missing Authors", doi="10.1000/no-authors", authors=[]),
        ],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert posted_items == 0
    assert result.failed == EXPECTED_VALIDATION_FAILURES
    assert result.created == 0
    assert result.outcomes[0].reason == "Missing title"
    assert result.outcomes[1].reason == "Missing authors"


@pytest.mark.anyio
async def test_idempotent_upsert_rerun_uses_doi_dedup() -> None:
    existing_items: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=existing_items)
        if _match(request.url.path, "/users/12345/items") and request.method == "POST":
            payload = request.read().decode("utf-8")
            if "10.1000/example" in payload:
                existing_items.append({
                    "key": "I1",
                    "data": {
                        "title": "Paper A",
                        "DOI": "10.1000/example",
                        "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
                    },
                })
                return httpx.Response(200, json={"successful": {"0": {"key": "I1"}}})
            return httpx.Response(400, json={"failed": {"0": {"message": "bad payload"}}})
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    first = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper()],
        settings=_settings(),
        client=client,
    )
    second = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper()],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert first.created == 1
    assert first.unchanged == 0
    assert second.created == 0
    assert second.unchanged == 1
    assert second.outcomes[0].duplicate_strategy == "doi"


@pytest.mark.anyio
async def test_idempotent_upsert_uses_title_author_hash_without_doi() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(
                200,
                json=[
                    {
                        "key": "I2",
                        "data": {
                            "title": "Paper Without DOI",
                            "DOI": "",
                            "creators": [{"firstName": "Grace", "lastName": "Hopper"}],
                        },
                    }
                ],
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper(title="Paper Without DOI", doi=None, authors=["Grace Hopper"])],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert result.created == 0
    assert result.unchanged == 1
    assert result.outcomes[0].duplicate_strategy == "title_author_hash"


@pytest.mark.anyio
async def test_create_response_partial_failure_is_reported() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=[])
        if _match(request.url.path, "/users/12345/items") and request.method == "POST":
            return httpx.Response(
                200, json={"successful": {}, "failed": {"0": {"message": "invalid date"}}}
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper()],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert result.created == 0
    assert result.failed == 1
    assert result.outcomes[0].reason == "invalid date"
    assert result.outcomes[0].retry_safe is False


@pytest.mark.anyio
async def test_retry_safe_failures_tracked_for_transient_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=[])
        if _match(request.url.path, "/users/12345/items") and request.method == "POST":
            return httpx.Response(503, text="service unavailable")
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper()],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert result.failed == 1
    assert result.retry_safe_failures == 1
    assert result.outcomes[0].retry_safe is True
