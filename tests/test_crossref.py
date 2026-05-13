from __future__ import annotations

from typing import Any

import pytest

from agt.tools.crossref import CrossrefClient, CrossrefResponseError

_EXPECTED_YEAR_2024 = 2024
_EXPECTED_YEAR_2023 = 2023
_EXPECTED_CITATION_COUNT = 12


@pytest.mark.anyio
async def test_crossref_search_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "message": {
                "items": [
                    {
                        "title": ["RAG in Practice"],
                        "published-print": {"date-parts": [[2024, 5, 1]]},
                        "DOI": "10.1/xyz",
                        "author": [{"given": "Ada", "family": "Lovelace"}],
                        "URL": "https://doi.org/10.1/xyz",
                        "is-referenced-by-count": 12,
                    }
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("rag", limit=5)
    assert len(papers) == 1
    assert papers[0].title == "RAG in Practice"
    assert papers[0].year == _EXPECTED_YEAR_2024
    assert papers[0].authors[0].name == "Ada Lovelace"
    assert papers[0].citation_count == _EXPECTED_CITATION_COUNT


@pytest.mark.anyio
async def test_crossref_prefers_print_then_online_year(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "message": {
                "items": [
                    {
                        "title": ["Only online"],
                        "published-online": {"date-parts": [[2023, 1, 1]]},
                    }
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=3)
    assert papers[0].year == _EXPECTED_YEAR_2023


@pytest.mark.anyio
async def test_crossref_handles_missing_title(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "message": {
                "items": [
                    {"title": []},
                    {"title": ["Valid title"]},
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=3)
    assert len(papers) == 1
    assert papers[0].title == "Valid title"


@pytest.mark.anyio
async def test_crossref_builds_author_names(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "message": {
                "items": [
                    {
                        "title": ["Author parsing"],
                        "author": [
                            {"given": "Grace", "family": "Hopper"},
                            {"family": "Turing"},
                            {"given": "Alan"},
                        ],
                    }
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=3)
    assert [a.name for a in papers[0].authors] == ["Grace Hopper", "Turing", "Alan"]


@pytest.mark.anyio
async def test_crossref_raises_on_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"wrong": {}}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    with pytest.raises(CrossrefResponseError):
        await client.search("x", limit=3)


@pytest.mark.anyio
async def test_crossref_search_paginates_with_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)
    offsets: list[str] = []

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        offsets.append(params["offset"])
        if params["offset"] == "0":
            return {"message": {"items": [{"title": ["P1"]}]}}
        return {"message": {"items": [{"title": ["P2"]}]}}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    papers = await client.search("x", limit=1, max_pages=2)
    assert [paper.title for paper in papers] == ["P1", "P2"]
    assert offsets == ["0", "1"]


@pytest.mark.anyio
async def test_crossref_extracts_venue_volume_issue_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "message": {
                "items": [
                    {
                        "title": ["Full Paper"],
                        "type": "journal-article",
                        "container-title": ["Journal of Science"],
                        "volume": "5",
                        "issue": "2",
                        "page": "101-115",
                        "DOI": "10.1/x",
                    }
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=1)
    assert papers[0].venue == "Journal of Science"
    assert papers[0].item_type == "journal_article"
    assert papers[0].volume == "5"
    assert papers[0].issue == "2"
    assert papers[0].pages == "101-115"


@pytest.mark.anyio
async def test_crossref_posted_content_maps_to_preprint(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"message": {"items": [{"title": ["Draft"], "type": "posted-content"}]}}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=1)
    assert papers[0].item_type == "preprint"


@pytest.mark.anyio
async def test_crossref_unknown_type_gives_none(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"message": {"items": [{"title": ["T"], "type": "report"}]}}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=1)
    assert papers[0].item_type is None
