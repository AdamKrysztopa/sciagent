from __future__ import annotations

from typing import Any

import pytest

from agt.tools.core_ac import CoreClient, CoreResponseError


@pytest.mark.anyio
async def test_core_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CoreClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "results": [
                {
                    "title": "Paper",
                    "yearPublished": 2024,
                    "doi": "10.1/abc",
                    "abstract": "Summary",
                    "authors": [{"name": "Ada Lovelace"}],
                    "downloadUrl": "https://x",
                    "isOpenAccess": True,
                }
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].source == "core"
    assert papers[0].open_access is True


@pytest.mark.anyio
async def test_core_handles_missing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CoreClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"results": [{"title": "Minimal"}]}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].authors == []


@pytest.mark.anyio
async def test_core_raises_on_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CoreClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"wrong": []}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    with pytest.raises(CoreResponseError):
        await client.search("query", limit=5)
