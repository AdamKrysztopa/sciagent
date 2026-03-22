from __future__ import annotations

# ruff: noqa: I001, PLR2004

from typing import Any

import pytest

from agt.tools.google_scholar import GoogleScholarClient, GoogleScholarResponseError


@pytest.mark.anyio
async def test_google_scholar_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GoogleScholarClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_request_json(*, params: dict[str, str]) -> dict[str, Any]:
        _ = params
        return {
            "organic_results": [
                {
                    "title": "Paper",
                    "snippet": "summary",
                    "link": "https://example.org",
                    "publication_info": {"summary": "Ada - 2024"},
                    "inline_links": {"cited_by": {"total": 7}},
                }
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].year == 2024


@pytest.mark.anyio
async def test_google_scholar_handles_missing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GoogleScholarClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_request_json(*, params: dict[str, str]) -> dict[str, Any]:
        _ = params
        return {"organic_results": [{"title": "Paper"}]}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].citation_count == 0


@pytest.mark.anyio
async def test_google_scholar_raises_on_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GoogleScholarClient(api_key="k", timeout_seconds=5, retries=1)

    async def _fake_request_json(*, params: dict[str, str]) -> dict[str, Any]:
        _ = params
        return {"wrong": []}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    with pytest.raises(GoogleScholarResponseError):
        await client.search("query", limit=5)
