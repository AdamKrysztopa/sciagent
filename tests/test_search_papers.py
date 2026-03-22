from __future__ import annotations

# ruff: noqa: I001, PLR0913, PLR2004

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

    async def search(
        self,
        query: str,
        *,
        limit: int,
        year_min: int | None = None,
        year_max: int | None = None,
        max_pages: int = 1,
        categories: list[str] | None = None,
    ) -> list[NormalizedPaper]:
        _ = query
        _ = limit
        _ = year_min
        _ = year_max
        _ = max_pages
        _ = categories
        return self.papers


class _FakeGuardrails:
    def acquire(self, service: str, thread_id: str) -> None:
        _ = service
        _ = thread_id

    async def wait_for_token(self, service: str, thread_id: str, timeout_seconds: float) -> bool:
        _ = service
        _ = thread_id
        _ = timeout_seconds
        return True


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
        NormalizedPaper(title="Test paper A", year=2025, semantic_score=0.4, open_access=False),
        NormalizedPaper(title="Test paper B", year=2026, semantic_score=0.5, open_access=True),
    ]

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(papers))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, metadata = await search_module.search_papers(
        query="test",
        settings=settings,
        thread_id="thread-1",
    )

    assert [paper.index for paper in ranked] == [0, 1]
    assert ranked[0].title == "Test paper B"
    assert metadata.total_after_filter == 2


@pytest.mark.anyio
async def test_search_papers_applies_constraints_and_keyword_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    papers = [
        NormalizedPaper(
            title="Quantum optimizer",
            abstract="Open source benchmark",
            year=2026,
            citation_count=12,
            open_access=True,
            semantic_score=0.6,
        ),
        NormalizedPaper(
            title="Quantum optimizer old study",
            abstract="Legacy setup",
            year=2022,
            citation_count=300,
            open_access=True,
            semantic_score=0.9,
        ),
    ]

    captured_queries: list[str] = []

    class _CapturingClient:
        async def search(
            self,
            query: str,
            *,
            limit: int,
            year_min: int | None = None,
            year_max: int | None = None,
            max_pages: int = 1,
            categories: list[str] | None = None,
        ) -> list[NormalizedPaper]:
            _ = limit
            _ = year_min
            _ = year_max
            _ = max_pages
            _ = categories
            captured_queries.append(query)
            return papers

    def _capturing_factory(**kwargs: object) -> _CapturingClient:
        _ = kwargs
        return _CapturingClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _capturing_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, metadata = await search_module.search_papers(
        query="quantum optimizer after 2025 at least 10 citations open access",
        settings=settings,
        thread_id="thread-1",
    )

    assert len(ranked) == 1
    assert ranked[0].title == "Quantum optimizer"
    assert ranked[0].index == 0
    assert captured_queries
    assert "quantum" in captured_queries[0]
    assert metadata.total_after_filter == 1


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
        async def search(
            self,
            query: str,
            *,
            limit: int,
            year_min: int | None = None,
            year_max: int | None = None,
            max_pages: int = 1,
            categories: list[str] | None = None,
        ) -> list[NormalizedPaper]:
            _ = query
            _ = limit
            _ = year_min
            _ = year_max
            _ = max_pages
            _ = categories
            raise RuntimeError("boom")

    def _fail_factory(**kwargs: object) -> _FailClient:
        _ = kwargs
        return _FailClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fail_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _fail_factory)
    monkeypatch.setattr(search_module, "CrossrefClient", _fail_factory)
    monkeypatch.setattr(search_module, "PubMedClient", _fail_factory)
    monkeypatch.setattr(search_module, "EuropePMCClient", _fail_factory)
    monkeypatch.setattr(search_module, "ArxivClient", _fail_factory)
    monkeypatch.setattr(search_module, "BaseSearchClient", _fail_factory)

    with pytest.raises(SemanticScholarResponseError, match="all retrieval providers failed"):
        await search_module.search_papers(
            query="test",
            settings=settings,
            thread_id="thread-1",
        )


@pytest.mark.anyio
async def test_search_papers_calls_all_parallel_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    called: set[str] = set()

    class _NamedClient:
        def __init__(self, name: str) -> None:
            self.name = name

        async def search(self, query: str, **kwargs: object) -> list[NormalizedPaper]:
            _ = query
            _ = kwargs
            called.add(self.name)
            return [NormalizedPaper(title=f"{self.name} paper", semantic_score=0.1)]

    def _factory(name: str):
        def _inner(**kwargs: object) -> _NamedClient:
            _ = kwargs
            return _NamedClient(name)

        return _inner

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _factory("semantic_scholar"))
    monkeypatch.setattr(search_module, "OpenAlexClient", _factory("openalex"))
    monkeypatch.setattr(search_module, "CrossrefClient", _factory("crossref"))
    monkeypatch.setattr(search_module, "PubMedClient", _factory("pubmed"))
    monkeypatch.setattr(search_module, "EuropePMCClient", _factory("europe_pmc"))
    monkeypatch.setattr(search_module, "ArxivClient", _factory("arxiv"))
    monkeypatch.setattr(search_module, "BaseSearchClient", _factory("base"))

    papers, metadata = await search_module.search_papers(
        query="test",
        settings=settings,
        thread_id="thread-1",
    )

    assert papers
    assert {
        "semantic_scholar",
        "openalex",
        "crossref",
        "pubmed",
        "europe_pmc",
        "arxiv",
        "base",
    }.issubset(called)
    assert metadata.source_timings
