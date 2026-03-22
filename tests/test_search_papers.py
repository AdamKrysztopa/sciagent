from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from agt.config import Settings
from agt.models import NormalizedPaper
from agt.tools import search_papers as search_module
from agt.tools.semantic_scholar import SemanticScholarResponseError


@dataclass
class _FakeClient:
    papers: list[NormalizedPaper]

    async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
        _ = query
        _ = limit
        return self.papers


class _FakeGuardrails:
    def acquire(self, service: str, thread_id: str) -> None:
        _ = service
        _ = thread_id


def _fake_get_guardrails() -> _FakeGuardrails:
    return _FakeGuardrails()


def _fake_client_factory(papers: list[NormalizedPaper]) -> Any:
    def _factory(**kwargs: object) -> _FakeClient:
        _ = kwargs
        return _FakeClient(papers)

    return _factory


@pytest.mark.anyio
async def test_search_papers_ranks_and_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    papers = [
        NormalizedPaper(title="A", year=2025, semantic_score=0.4, open_access=False),
        NormalizedPaper(title="B", year=2026, semantic_score=0.5, open_access=True),
    ]

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(papers))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))

    ranked = await search_module.search_papers(
        query="test",
        settings=settings,
        thread_id="thread-1",
    )

    assert [paper.index for paper in ranked] == [0, 1]
    assert ranked[0].title == "B"


@pytest.mark.anyio
async def test_search_papers_raises_when_all_sources_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    class _FailClient:
        async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
            _ = query
            _ = limit
            raise RuntimeError("boom")

    def _fail_factory(**kwargs: object) -> _FailClient:
        _ = kwargs
        return _FailClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fail_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _fail_factory)
    monkeypatch.setattr(search_module, "CrossrefClient", _fail_factory)

    with pytest.raises(SemanticScholarResponseError, match="all retrieval providers failed"):
        await search_module.search_papers(
            query="test",
            settings=settings,
            thread_id="thread-1",
        )
