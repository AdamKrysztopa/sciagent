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
    assert papers[0].authors == ["Ada Lovelace"]
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
    assert papers[0].authors == ["Grace Hopper", "Turing", "Alan"]


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
