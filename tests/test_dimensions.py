from __future__ import annotations

# ruff: noqa: I001, PLR2004

from typing import Any

import pytest

from agt.tools.dimensions import DimensionsClient, DimensionsResponseError


@pytest.mark.anyio
async def test_dimensions_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DimensionsClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_auth() -> str:
        return "token"

    async def _fake_dsl_search(*, query: str, limit: int, token: str) -> dict[str, Any]:
        _ = query
        _ = limit
        _ = token
        return {
            "publications": [
                {
                    "title": "Paper",
                    "year": 2024,
                    "doi": "10.1/abc",
                    "times_cited": 12,
                    "open_access": True,
                    "authors": [{"raw_name": "Ada"}],
                }
            ]
        }

    monkeypatch.setattr(client, "_authenticate", _fake_auth)
    monkeypatch.setattr(client, "_dsl_search", _fake_dsl_search)

    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].citation_count == 12


@pytest.mark.anyio
async def test_dimensions_handles_missing_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DimensionsClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_auth() -> str:
        return "token"

    async def _fake_dsl_search(*, query: str, limit: int, token: str) -> dict[str, Any]:
        _ = query
        _ = limit
        _ = token
        return {"publications": [{"title": "Paper"}]}

    monkeypatch.setattr(client, "_authenticate", _fake_auth)
    monkeypatch.setattr(client, "_dsl_search", _fake_dsl_search)
    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].authors == []


@pytest.mark.anyio
async def test_dimensions_raises_on_bad_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DimensionsClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_auth() -> str:
        return "token"

    async def _fake_dsl_search(*, query: str, limit: int, token: str) -> dict[str, Any]:
        _ = query
        _ = limit
        _ = token
        return {"wrong": []}

    monkeypatch.setattr(client, "_authenticate", _fake_auth)
    monkeypatch.setattr(client, "_dsl_search", _fake_dsl_search)
    with pytest.raises(DimensionsResponseError):
        await client.search("query", limit=5)
