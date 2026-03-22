from __future__ import annotations

from typing import Any

import pytest

from agt.tools.semantic_scholar import SemanticScholarClient, SemanticScholarResponseError

EXPECTED_SEMANTIC_SCORE = 0.9
EXPECTED_CITATION_COUNT = 42
EXPECTED_ARXIV_ID = "2401.12345"


@pytest.mark.anyio
async def test_semantic_scholar_returns_only_normalized_papers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SemanticScholarClient(api_key=None, timeout_seconds=5, retries=1)

    async def _fake_request_json(
        *,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        _ = path
        _ = params
        _ = headers
        return {
            "data": [
                {
                    "title": "Paper A",
                    "year": 2026,
                    "abstract": "Abstract",
                    "url": "https://example.org",
                    "isOpenAccess": True,
                    "authors": [{"name": "Alice"}],
                    "externalIds": {"DOI": "10.1/abc", "ArXiv": "2401.12345"},
                    "score": 0.9,
                    "citationCount": 42,
                },
                {
                    "title": "",
                    "year": 2026,
                },
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    papers = await client.search("test", limit=5)

    assert len(papers) == 1
    assert papers[0].title == "Paper A"
    assert papers[0].semantic_score == EXPECTED_SEMANTIC_SCORE
    assert papers[0].citation_count == EXPECTED_CITATION_COUNT
    assert papers[0].arxiv_id == EXPECTED_ARXIV_ID


@pytest.mark.anyio
async def test_semantic_scholar_malformed_payload_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SemanticScholarClient(api_key=None, timeout_seconds=5, retries=1)

    async def _fake_request_json(
        *,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        _ = path
        _ = params
        _ = headers
        return {"wrong": []}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)

    with pytest.raises(SemanticScholarResponseError):
        await client.search("test", limit=5)
