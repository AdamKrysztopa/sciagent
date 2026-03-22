from __future__ import annotations

from typing import Any

import pytest

from agt.tools.europe_pmc import EuropePMCClient, EuropePMCResponseError

_EXPECTED_YEAR_2024 = 2024


@pytest.mark.anyio
async def test_europe_pmc_search_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuropePMCClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "resultList": {
                "result": [
                    {
                        "title": "Sports Nutrition Review",
                        "pubYear": "2024",
                        "doi": "10.1/abc",
                        "abstractText": "Useful review.",
                        "authorString": "Ada Lovelace, Grace Hopper",
                        "source": "MED",
                        "id": "12345",
                        "isOpenAccess": "Y",
                        "citedByCount": 7,
                    }
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("sport nutrition", limit=5)
    assert len(papers) == 1
    assert papers[0].title == "Sports Nutrition Review"
    assert papers[0].year == _EXPECTED_YEAR_2024
    assert papers[0].authors == ["Ada Lovelace", "Grace Hopper"]
    assert papers[0].open_access is True
    assert papers[0].url == "https://europepmc.org/article/MED/12345"


@pytest.mark.anyio
async def test_europe_pmc_raises_on_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuropePMCClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"wrong": []}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    with pytest.raises(EuropePMCResponseError):
        await client.search("x", limit=3)


@pytest.mark.anyio
async def test_europe_pmc_skips_items_without_title(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuropePMCClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "resultList": {
                "result": [
                    {"title": "  "},
                    {"title": "Valid", "pubYear": 2023},
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=3)
    assert len(papers) == 1
    assert papers[0].title == "Valid"


@pytest.mark.anyio
async def test_europe_pmc_handles_missing_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuropePMCClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"resultList": {"result": [{"title": "Minimal"}]}}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("x", limit=3)
    assert len(papers) == 1
    assert papers[0].authors == []
    assert papers[0].abstract is None
    assert papers[0].citation_count == 0
