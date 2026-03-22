from __future__ import annotations

from typing import Any

import pytest

from agt.tools.openalex import OpenAlexClient, OpenAlexResponseError

_EXPECTED_CITATION_COUNT = 42


@pytest.mark.anyio
async def test_openalex_search_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "results": [
                {
                    "title": "<b>Nutrition</b> in Sport",
                    "publication_year": 2024,
                    "doi": "https://doi.org/10.1/abc",
                    "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
                    "primary_location": {"landing_page_url": "https://example.org/paper"},
                    "open_access": {"is_oa": True},
                    "relevance_score": 0.7,
                    "cited_by_count": 42,
                }
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("sport nutrition", limit=5)
    assert len(papers) == 1
    assert papers[0].title == "Nutrition in Sport"
    assert papers[0].doi == "10.1/abc"
    assert papers[0].authors == ["Ada Lovelace"]
    assert papers[0].open_access is True
    assert papers[0].citation_count == _EXPECTED_CITATION_COUNT


@pytest.mark.anyio
async def test_openalex_search_builds_year_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)
    captured: dict[str, str] = {}

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        captured.update(params)
        return {"results": []}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("timeseries", limit=10, year_min=2020)
    assert papers == []
    assert captured["filter"] == "publication_year:>2019"


@pytest.mark.anyio
async def test_openalex_search_raises_on_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"wrong": []}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    with pytest.raises(OpenAlexResponseError):
        await client.search("x", limit=3)


@pytest.mark.anyio
async def test_openalex_search_skips_items_without_title(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "results": [
                {"title": "   "},
                {"title": "Valid title", "publication_year": 2023},
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=3)
    assert len(papers) == 1
    assert papers[0].title == "Valid title"


@pytest.mark.anyio
async def test_openalex_search_handles_missing_optional_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"results": [{"title": "Bare minimum"}]}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=3)
    assert len(papers) == 1
    assert papers[0].year is None
    assert papers[0].authors == []
    assert papers[0].open_access is False


@pytest.mark.anyio
async def test_openalex_search_paginates_with_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)
    calls: list[dict[str, str]] = []

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        calls.append(dict(params))
        if len(calls) == 1:
            return {
                "results": [{"title": "P1"}],
                "meta": {"next_cursor": "abc"},
            }
        return {
            "results": [{"title": "P2"}],
            "meta": {"next_cursor": ""},
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    papers = await client.search("x", limit=1, max_pages=2)
    assert [paper.title for paper in papers] == ["P1", "P2"]
    assert calls[0]["cursor"] == "*"
    assert calls[1]["cursor"] == "abc"
