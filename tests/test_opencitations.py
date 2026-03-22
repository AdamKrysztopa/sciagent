from __future__ import annotations

# ruff: noqa: I001, PLR2004

import pytest

from agt.tools.opencitations import OpenCitationsClient, OpenCitationsResponseError


@pytest.mark.anyio
async def test_opencitations_parses_count(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str) -> object:
        _ = path
        return [{"count": "42"}]

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    count = await client.citation_count("10.1234/abc")
    assert count == 42


@pytest.mark.anyio
async def test_opencitations_returns_none_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str) -> object:
        _ = path
        return []

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    count = await client.citation_count("10.1234/abc")
    assert count is None


@pytest.mark.anyio
async def test_opencitations_raises_on_bad_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str) -> object:
        _ = path
        return {"count": 1}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    with pytest.raises(OpenCitationsResponseError):
        await client.citation_count("10.1234/abc")
