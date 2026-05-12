from __future__ import annotations

# ruff: noqa: I001, PLR0913, PLR2004

from dataclasses import dataclass
from typing import Any

import pytest

from agt.config import Settings
from agt.models import FilterEditContract, NormalizedPaper, SourceTerminalState
from agt.tools import search_papers as search_module
from agt.tools.search_papers import _depth_max_pages  # pyright: ignore[reportPrivateUsage]
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
        query="papers",
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


@pytest.mark.anyio
async def test_search_papers_respects_requested_limit_above_source_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
        "AGT_SEMANTIC_SCHOLAR_LIMIT": 10,
    })

    papers = [
        NormalizedPaper(
            title=f"Transformer study {index}",
            abstract="Transformer attention benchmark",
            year=2024,
            semantic_score=0.8,
        )
        for index in range(20)
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
        query="transformer attention papers",
        limit=20,
        settings=settings,
        thread_id="thread-limit",
    )

    assert len(ranked) == 20
    assert metadata.total_after_filter == 20


@pytest.mark.anyio
async def test_search_papers_uses_deterministic_query_expansions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    captured_queries: list[str] = []

    class _ExpansionClient:
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
            if query == "retrieval augmented":
                return [
                    NormalizedPaper(
                        title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
                        abstract="retrieval augmented generation benchmark",
                        year=2020,
                        semantic_score=0.9,
                    )
                ]
            return []

    def _expansion_factory(**kwargs: object) -> _ExpansionClient:
        _ = kwargs
        return _ExpansionClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _expansion_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, metadata = await search_module.search_papers(
        query="retrieval augmented generation survey",
        limit=10,
        settings=settings,
        thread_id="thread-expand",
    )

    assert ranked
    assert ranked[0].title == "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
    assert "retrieval augmented" in captured_queries
    assert metadata.search_plan is not None
    assert "retrieval augmented" in metadata.search_plan.rewritten_queries


# ── _depth_max_pages unit tests ────────────────────────────────────────────


def _make_settings(max_pages: int = 2) -> Settings:
    return Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SEARCH_MAX_PAGES": max_pages,
    })


def test_depth_max_pages_quick_always_returns_one() -> None:
    settings = _make_settings(max_pages=3)
    assert _depth_max_pages("quick", settings) == 1


def test_depth_max_pages_balanced_returns_settings_value() -> None:
    settings = _make_settings(max_pages=2)
    assert _depth_max_pages("balanced", settings) == 2


def test_depth_max_pages_none_returns_settings_value() -> None:
    settings = _make_settings(max_pages=2)
    assert _depth_max_pages(None, settings) == 2


def test_depth_max_pages_deep_returns_capped_triple() -> None:
    # settings.search_max_pages=2 → 2*3=6, within cap of 10
    settings = _make_settings(max_pages=2)
    assert _depth_max_pages("deep", settings) == 6


def test_depth_max_pages_deep_caps_at_ten() -> None:
    # settings.search_max_pages=5 → 5*3=15, capped at 10
    settings = _make_settings(max_pages=5)
    assert _depth_max_pages("deep", settings) == 10


@pytest.mark.anyio
async def test_search_papers_skips_generic_editing_single_keyword_expansion(
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
            title="CRISPR therapeutic overview",
            abstract="Therapeutic applications of CRISPR genome editing.",
            year=2024,
            semantic_score=0.8,
        )
    ]

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(papers))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    _, metadata = await search_module.search_papers(
        query="CRISPR gene editing therapeutic applications not older than 2022",
        limit=20,
        settings=settings,
        thread_id="thread-editing-expansion",
    )

    assert metadata.search_plan is not None
    assert "editing" not in metadata.search_plan.rewritten_queries


@pytest.mark.anyio
async def test_search_papers_refines_broad_two_keyword_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    captured_queries: list[str] = []

    broad_results = [
        NormalizedPaper(
            title="Transformers Are Effective for Time Series Forecasting",
            abstract="Forecasting transformers for time series tasks.",
            year=2023,
            semantic_score=0.9,
            citation_count=100,
        ),
        NormalizedPaper(
            title="General Time Series Forecasting with Transformers",
            abstract="Transformer forecasting models for time series.",
            year=2024,
            semantic_score=0.8,
            citation_count=90,
        ),
    ]
    anchor = NormalizedPaper(
        title="Temporal Fusion Transformers for interpretable multi-horizon time series forecasting",
        abstract="Transformer forecasting for time series with multi-horizon outputs.",
        year=2021,
        semantic_score=0.95,
        citation_count=250,
        doi="10.1016/j.ijforecast.2021.03.012",
    )

    class _RefinementClient:
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
            if query == "time series":
                return broad_results
            if query == "time series forecasting transformer":
                return [anchor]
            return []

    def _refinement_factory(**kwargs: object) -> _RefinementClient:
        _ = kwargs
        return _RefinementClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _refinement_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, _ = await search_module.search_papers(
        query="the most cited 2020 and newer timeseries papers - list 5",
        limit=20,
        settings=settings,
        thread_id="thread-refine",
    )

    assert any(paper.doi == "10.1016/j.ijforecast.2021.03.012" for paper in ranked)
    assert "time series forecasting transformer" in captured_queries


@pytest.mark.anyio
async def test_search_papers_refinement_ignores_singularized_analysis_noise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    captured_queries: list[str] = []

    broad_results = [
        NormalizedPaper(
            title="Power General Time Series Analysis by Pretrained LM",
            abstract="General analysis of time series modelling.",
            year=2023,
            semantic_score=0.95,
            citation_count=900,
        ),
        NormalizedPaper(
            title="Are Transformers Effective for Time Series Forecasting?",
            abstract="Transformer forecasting models for time series.",
            year=2023,
            semantic_score=0.94,
            citation_count=2400,
        ),
    ]
    anchor = NormalizedPaper(
        title="Temporal Fusion Transformers for interpretable multi-horizon time series forecasting",
        abstract="Transformer forecasting for time series with multi-horizon outputs.",
        year=2021,
        semantic_score=0.95,
        citation_count=250,
        doi="10.1016/j.ijforecast.2021.03.012",
    )

    class _RefinementClient:
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
            if query == "time series":
                return broad_results
            if query == "time series forecasting transformer":
                return [anchor]
            return []

    def _refinement_factory(**kwargs: object) -> _RefinementClient:
        _ = kwargs
        return _RefinementClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _refinement_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, _ = await search_module.search_papers(
        query="the most cited 2020 and newer timeseries papers - list 5",
        limit=20,
        settings=settings,
        thread_id="thread-analysis-refine",
    )

    assert any(paper.doi == "10.1016/j.ijforecast.2021.03.012" for paper in ranked)
    assert "time series forecasting transformer" in captured_queries
    assert all("analysi" not in query for query in captured_queries)


@pytest.mark.anyio
async def test_search_papers_refines_from_shorter_variant_source_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    captured_queries: list[str] = []

    broad_results = [
        NormalizedPaper(
            title="The prevalence and long-term health effects of Long Covid",
            abstract="Long-term effects and symptoms after infection.",
            year=2022,
            semantic_score=0.9,
            citation_count=800,
            open_access=True,
        ),
        NormalizedPaper(
            title="Global prevalence of long COVID symptoms",
            abstract="Symptoms after COVID-19 infection.",
            year=2022,
            semantic_score=0.8,
            citation_count=700,
            open_access=True,
        ),
    ]
    shorter_variant_results = [
        NormalizedPaper(
            title="Long COVID mechanisms and recommendations for care",
            abstract="Mechanisms and recommendations for long COVID care.",
            year=2023,
            semantic_score=0.82,
            citation_count=600,
            open_access=True,
        ),
        NormalizedPaper(
            title="Long COVID mechanisms and management",
            abstract="Mechanisms and management strategies for long COVID.",
            year=2022,
            semantic_score=0.75,
            citation_count=250,
            open_access=True,
        ),
        NormalizedPaper(
            title="Long COVID recommendations for rehabilitation",
            abstract="Recommendations for rehabilitation after long COVID.",
            year=2022,
            semantic_score=0.7,
            citation_count=200,
            open_access=True,
        ),
    ]
    anchor = NormalizedPaper(
        title="Long COVID: major findings, mechanisms and recommendations",
        abstract="Mechanisms and recommendations for long COVID care.",
        year=2023,
        semantic_score=0.95,
        citation_count=4000,
        doi="10.1038/s41579-022-00846-2",
        open_access=True,
    )

    class _RefinementClient:
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
            if query == "covid long term effects":
                return broad_results
            if query == "covid long":
                return shorter_variant_results
            if query.startswith("covid long recommendation"):
                return [anchor]
            return []

    def _refinement_factory(**kwargs: object) -> _RefinementClient:
        _ = kwargs
        return _RefinementClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _refinement_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, _ = await search_module.search_papers(
        query="open access papers on COVID long-term effects after 2021",
        limit=20,
        settings=settings,
        thread_id="thread-short-refine",
    )

    assert any(paper.doi == "10.1038/s41579-022-00846-2" for paper in ranked)
    assert any(query.startswith("covid long recommendation") for query in captured_queries)


@pytest.mark.anyio
async def test_search_papers_prefers_more_specific_abstract_backed_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    captured_queries: list[str] = []

    generic_results = [
        NormalizedPaper(
            title="Benchmarking Retrieval-Augmented Generation for Medicine",
            abstract="Clinical benchmarking for retrieval-augmented generation systems.",
            year=2024,
            semantic_score=0.9,
            citation_count=400,
        )
    ]
    specific_results = [
        NormalizedPaper(
            title="REALM: Retrieval-Augmented Language Model Pre-Training",
            abstract="Pre-training for knowledge-intensive tasks with retrieval augmentation.",
            year=2020,
            semantic_score=0.95,
            citation_count=515,
        )
    ]
    anchor = NormalizedPaper(
        title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        abstract="Sequence-to-sequence generation for knowledge-intensive NLP tasks.",
        year=2020,
        semantic_score=0.99,
        citation_count=18,
        doi="10.48550/arXiv.2005.11401",
    )

    class _RefinementClient:
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
            if query == "retrieval augmented generation survey":
                return specific_results
            if query == "retrieval augmented generation":
                return specific_results
            if query == "retrieval augmented":
                return generic_results
            if "knowledge" in query:
                return [anchor]
            return []

    def _refinement_factory(**kwargs: object) -> _RefinementClient:
        _ = kwargs
        return _RefinementClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _refinement_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, _ = await search_module.search_papers(
        query="retrieval augmented generation survey",
        limit=20,
        settings=settings,
        thread_id="thread-knowledge-refine",
    )

    assert any(paper.doi == "10.48550/arXiv.2005.11401" for paper in ranked)
    assert any("knowledge" in query for query in captured_queries)


@pytest.mark.anyio
async def test_search_papers_refinement_fetches_second_openalex_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    openalex_max_pages_by_query: dict[str, int] = {}

    broad_results = [
        NormalizedPaper(
            title="Transformers Are Effective for Time Series Forecasting",
            abstract="Forecasting transformers for time series tasks.",
            year=2023,
            semantic_score=0.9,
            citation_count=100,
        ),
        NormalizedPaper(
            title="General Time Series Forecasting with Transformers",
            abstract="Transformer forecasting models for time series.",
            year=2024,
            semantic_score=0.8,
            citation_count=90,
        ),
    ]
    anchor = NormalizedPaper(
        title="Temporal Fusion Transformers for interpretable multi-horizon time series forecasting",
        abstract="Transformer forecasting for time series with multi-horizon outputs.",
        year=2021,
        semantic_score=0.95,
        citation_count=250,
        doi="10.1016/j.ijforecast.2021.03.012",
    )

    class _SemanticClient:
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
            if query == "time series":
                return broad_results
            return []

    class _OpenAlexClient:
        async def search(
            self,
            query: str,
            *,
            limit: int,
            year_min: int | None = None,
            max_pages: int = 1,
        ) -> list[NormalizedPaper]:
            _ = limit
            _ = year_min
            openalex_max_pages_by_query[query] = max_pages
            if query == "time series forecasting transformer" and max_pages >= 2:
                return [anchor]
            return []

    def _semantic_factory(**kwargs: object) -> _SemanticClient:
        _ = kwargs
        return _SemanticClient()

    def _openalex_factory(**kwargs: object) -> _OpenAlexClient:
        _ = kwargs
        return _OpenAlexClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _semantic_factory)
    monkeypatch.setattr(search_module, "OpenAlexClient", _openalex_factory)
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, _ = await search_module.search_papers(
        query="the most cited 2020 and newer timeseries papers - list 5",
        limit=20,
        settings=settings,
        thread_id="thread-openalex-refine",
    )

    assert any(paper.doi == "10.1016/j.ijforecast.2021.03.012" for paper in ranked)
    assert openalex_max_pages_by_query.get("time series forecasting transformer") == 2


@pytest.mark.anyio
async def test_fallback_disabled_skips_fallback_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
        "AGT_CORE_API_KEY": "core-secret",
    })

    called_fallback = {"core": 0}

    class _CoreClient:
        async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
            _ = query
            _ = limit
            called_fallback["core"] += 1
            return [NormalizedPaper(title="Fallback paper", semantic_score=0.8)]

    def _core_factory(**kwargs: object) -> _CoreClient:
        _ = kwargs
        return _CoreClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CoreClient", _core_factory)

    with pytest.raises(SemanticScholarResponseError):
        await search_module.search_papers(
            query="test",
            settings=settings,
            thread_id="thread-1",
        )

    assert called_fallback["core"] == 0


@pytest.mark.anyio
async def test_fallback_enabled_fills_results_with_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
        "AGT_CORE_API_KEY": "core-secret",
        "AGT_ENABLE_FALLBACK_RETRIEVAL": True,
    })

    class _CoreClient:
        async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
            _ = query
            _ = limit
            return [
                NormalizedPaper(
                    title="Fallback paper",
                    semantic_score=0.8,
                    year=2026,
                )
            ]

    def _core_factory(**kwargs: object) -> _CoreClient:
        _ = kwargs
        return _CoreClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CoreClient", _core_factory)

    papers, metadata = await search_module.search_papers(
        query="papers",
        settings=settings,
        thread_id="thread-1",
    )

    assert len(papers) == 1
    assert papers[0].source == "core:fallback"
    assert "core:fallback" in metadata.sources_used


@pytest.mark.anyio
async def test_fallback_and_primary_duplicates_merge_to_one_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
        "AGT_CORE_API_KEY": "core-secret",
    })

    primary = [
        NormalizedPaper(
            title="Shared DOI paper",
            doi="10.1000/shared",
            semantic_score=0.6,
            year=2025,
        )
    ]
    fallback = [
        NormalizedPaper(
            title="Shared DOI paper",
            doi="10.1000/shared",
            semantic_score=0.2,
            year=2024,
        )
    ]

    class _CoreClient:
        async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
            _ = query
            _ = limit
            return fallback

    def _core_factory(**kwargs: object) -> _CoreClient:
        _ = kwargs
        return _CoreClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(primary))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CoreClient", _core_factory)

    papers, _ = await search_module.search_papers(
        query="papers",
        settings=settings,
        thread_id="thread-1",
        fallback_mode="force",
    )

    assert len(papers) == 1
    assert papers[0].title == "Shared DOI paper"
    assert papers[0].index == 0


@pytest.mark.anyio
async def test_mixed_primary_fallback_order_and_indices_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
        "AGT_CORE_API_KEY": "core-secret",
        "AGT_ENABLE_FALLBACK_RETRIEVAL": True,
    })

    primary = [
        NormalizedPaper(
            title="Primary older paper",
            year=2018,
            semantic_score=0.2,
            citation_count=1,
        )
    ]
    fallback = [
        NormalizedPaper(
            title="Fallback newer paper",
            year=2026,
            semantic_score=0.7,
            citation_count=30,
        ),
        NormalizedPaper(
            title="Fallback second paper",
            year=2025,
            semantic_score=0.6,
            citation_count=20,
        ),
    ]

    class _CoreClient:
        async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
            _ = query
            _ = limit
            return fallback

    def _core_factory(**kwargs: object) -> _CoreClient:
        _ = kwargs
        return _CoreClient()

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(primary))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CoreClient", _core_factory)

    papers, metadata = await search_module.search_papers(
        query="papers",
        limit=3,
        settings=settings,
        thread_id="thread-1",
    )

    assert [paper.index for paper in papers] == [0, 1, 2]
    assert papers[0].title == "Fallback newer paper"
    assert papers[1].title == "Fallback second paper"
    assert papers[2].title == "Primary older paper"
    assert "core:fallback" in metadata.sources_used


# ---------------------------------------------------------------------------
# AGT-28 — SearchPlan and deterministic filter contract tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_search_plan_produced_with_hard_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    """SearchPlan is built before retrieval and captures hard year filter."""
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    papers = [
        NormalizedPaper(title="Time series forecasting survey", year=2024, semantic_score=0.5),
        NormalizedPaper(title="Time series forecasting classic", year=2019, semantic_score=0.9),
    ]

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(papers))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    _, metadata = await search_module.search_papers(
        query="time-series forecasting not older than 2024",
        settings=settings,
        thread_id="t1",
    )

    plan = metadata.search_plan
    assert plan is not None
    assert plan.original_query == "time-series forecasting not older than 2024"
    assert plan.hard_filters.min_year == 2024
    assert plan.hard_filters.min_year is not None


@pytest.mark.anyio
async def test_hard_year_filter_no_violation_survives_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No paper violating a hard min_year filter survives after ranking (AGT-28 AC)."""
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    papers = [
        NormalizedPaper(title="Machine learning advances 2024", year=2024, semantic_score=0.4),
        NormalizedPaper(title="Machine learning survey 2025", year=2025, semantic_score=0.6),
        NormalizedPaper(title="Machine learning classic 2020", year=2020, semantic_score=0.99),
        NormalizedPaper(title="Machine learning old 2019", year=2019, semantic_score=0.95),
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
        query="machine learning not older than 2024",
        settings=settings,
        thread_id="t2",
    )

    for paper in ranked:
        assert paper.year is not None and paper.year >= 2024, (
            f"Paper '{paper.title}' (year={paper.year}) violated hard min_year=2024"
        )
    assert metadata.search_plan is not None
    assert metadata.search_plan.hard_filters.min_year == 2024
    assert "year_min" in metadata.search_plan.filters_enforced_post_merge


@pytest.mark.anyio
async def test_hard_exclusion_filter_no_violation_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Papers matching an exclusion keyword must be removed before ranking (AGT-28 AC)."""
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    papers = [
        NormalizedPaper(
            title="Transformers for NLP",
            abstract="attention is all you need deep learning",
            year=2023,
            semantic_score=0.8,
        ),
        NormalizedPaper(
            title="CNN image classification not transformers",
            abstract="convolutional neural network vision detection",
            year=2023,
            semantic_score=0.5,
        ),
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
        query="deep learning but not transformers",
        settings=settings,
        thread_id="t3",
    )

    for paper in ranked:
        text = f"{paper.title} {paper.abstract or ''}".lower()
        assert "transformers" not in text, (
            f"Paper '{paper.title}' matched exclusion keyword 'transformers'"
        )
    assert metadata.search_plan is not None
    assert "transformers" in metadata.search_plan.hard_filters.exclude_keywords


@pytest.mark.anyio
async def test_search_plan_source_policy_lists_all_primary_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SearchPlan.source_policy lists all 7 primary sources (AGT-28 AC)."""
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(
        search_module,
        "SemanticScholarClient",
        _fake_client_factory([
            NormalizedPaper(title="Graph neural network survey", year=2025, semantic_score=0.5)
        ]),
    )
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    _, metadata = await search_module.search_papers(
        query="graph neural networks",
        settings=settings,
        thread_id="t4",
    )

    plan = metadata.search_plan
    assert plan is not None
    primary_names = {sc.name for sc in plan.source_policy if sc.tier == "primary"}
    assert primary_names == {
        "semantic_scholar",
        "openalex",
        "crossref",
        "pubmed",
        "europe_pmc",
        "arxiv",
        "base",
    }


@pytest.mark.anyio
async def test_search_plan_year_push_down_recorded_for_semantic_scholar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SearchPlan records year_min push-down for semantic_scholar and openalex (AGT-28 AC)."""
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(
        search_module,
        "SemanticScholarClient",
        _fake_client_factory([
            NormalizedPaper(title="Causal inference methods", year=2025, semantic_score=0.5)
        ]),
    )
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    _, metadata = await search_module.search_papers(
        query="causal inference since 2022",
        settings=settings,
        thread_id="t5",
    )

    plan = metadata.search_plan
    assert plan is not None
    assert "year_min" in plan.filters_pushed_down.get("semantic_scholar", [])
    assert "year_min" in plan.filters_pushed_down.get("openalex", [])
    assert "year_min" in plan.filters_enforced_post_merge


@pytest.mark.anyio
async def test_search_plan_rewritten_queries_captured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SearchPlan.rewritten_queries includes at least the primary retrieval query (AGT-28 AC)."""
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(
        search_module,
        "SemanticScholarClient",
        _fake_client_factory([
            NormalizedPaper(
                title="Time series forecasting method selection", year=2024, semantic_score=0.6
            )
        ]),
    )
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    _, metadata = await search_module.search_papers(
        query="method selection time-series forecasting based on data characteristics not older than 2024",
        settings=settings,
        thread_id="t6",
    )

    plan = metadata.search_plan
    assert plan is not None
    assert len(plan.rewritten_queries) >= 1
    # The topic_query should be non-empty
    assert plan.topic_query


@pytest.mark.anyio
async def test_search_papers_filters_provider_scored_off_topic_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    relevant = [
        NormalizedPaper(
            title="Feature-based time-series forecasting method selection",
            abstract="We study automatic model selection for time series forecasting tasks.",
            year=2025,
            citation_count=12,
            open_access=True,
            semantic_score=18.0,
        )
    ]
    off_topic = [
        NormalizedPaper(
            title="Global fertility in 204 countries and territories, 1950-2021, with forecasts to 2100",
            abstract="Population forecasting trends across world regions.",
            year=2024,
            citation_count=545,
            open_access=True,
            semantic_score=28.0,
        )
    ]

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(relevant))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory(off_topic))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    papers, metadata = await search_module.search_papers(
        query="time-series forecasting method selection based on the tineseries data itself, not older than 2024",
        settings=settings,
        thread_id="thread-off-topic",
    )

    assert [paper.title for paper in papers] == [
        "Feature-based time-series forecasting method selection"
    ]
    assert metadata.search_plan is not None
    assert "topic_relevance" in metadata.search_plan.filters_enforced_post_merge


@pytest.mark.anyio
async def test_search_papers_reports_progress_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    messages: list[str] = []

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(
        search_module,
        "SemanticScholarClient",
        _fake_client_factory([
            NormalizedPaper(
                title="Time series forecasting survey",
                abstract="A survey of time series forecasting methods.",
                year=2025,
                semantic_score=0.7,
            )
        ]),
    )
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    papers, _ = await search_module.search_papers(
        query="time series forecasting",
        settings=settings,
        thread_id="thread-progress",
        progress=messages.append,
    )

    assert papers
    assert messages == [
        "retrieving primary sources",
        "enriching citations",
        "reranking and filtering merged results",
    ]


@pytest.mark.anyio
async def test_search_papers_applies_filter_edit_to_constraints_and_plan(
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
            title="Graph neural retrieval methods",
            abstract="Graph neural networks for document retrieval.",
            year=2026,
            semantic_score=0.8,
        ),
        NormalizedPaper(
            title="Graph neural classic methods",
            abstract="Graph neural networks for older benchmarks.",
            year=2024,
            semantic_score=0.7,
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

    filter_edit = FilterEditContract.model_validate({
        "original_query": "transformers after 2020",
        "hard_filters": {
            "min_year": 2025,
            "include_keywords": ["graph", "neural"],
        },
        "result_limit": 1,
    })

    ranked, metadata = await search_module.search_papers(
        query="transformers after 2020",
        settings=settings,
        thread_id="thread-filter-edit",
        filter_edit=filter_edit,
    )

    assert captured_queries
    assert captured_queries[0] == "graph neural"
    assert [paper.title for paper in ranked] == ["Graph neural retrieval methods"]
    assert len(ranked) == 1
    plan = metadata.search_plan
    assert plan is not None
    assert plan.original_query == "transformers after 2020"
    assert plan.hard_filters.min_year == 2025
    assert plan.hard_filters.include_keywords == ["graph", "neural"]
    assert metadata.total_after_filter == 1


@pytest.mark.anyio
async def test_search_papers_populates_explanation(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
    })

    papers = [
        NormalizedPaper(
            title="Attention is all you need",
            abstract="We propose a transformer model based solely on attention mechanisms.",
            year=2017,
            semantic_score=0.9,
            citation_count=60_000,
            source="semantic_scholar",
        ),
    ]

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(papers))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    ranked, _ = await search_module.search_papers(
        query="transformer attention mechanism",
        settings=settings,
        thread_id="thread-explain",
    )

    assert len(ranked) == 1
    assert ranked[0].explanation is not None
    assert ranked[0].explanation != ""
    assert "semantic scholar" in ranked[0].explanation
    assert "2017" in ranked[0].explanation


@pytest.mark.anyio
async def test_source_states_populated_for_queried_and_skipped_no_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "123",
        "AGT_SUMMARIZATION_USE_LLM": False,
        # core/dimensions/google_scholar keys intentionally absent
    })
    papers = [
        NormalizedPaper(title="Queried paper", semantic_score=0.9, year=2024),
    ]

    monkeypatch.setattr(search_module, "get_guardrails", _fake_get_guardrails)
    monkeypatch.setattr(search_module, "SemanticScholarClient", _fake_client_factory(papers))
    monkeypatch.setattr(search_module, "OpenAlexClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "CrossrefClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "PubMedClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "EuropePMCClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "ArxivClient", _fake_client_factory([]))
    monkeypatch.setattr(search_module, "BaseSearchClient", _fake_client_factory([]))

    _, metadata = await search_module.search_papers(
        query="source state test",
        settings=settings,
        thread_id="thread-states",
    )

    states = metadata.source_states
    # semantic_scholar returned papers → queried
    assert states.get("semantic_scholar") == "queried"
    # other primary sources returned nothing → zero_results
    for name in ("openalex", "crossref", "pubmed", "europe_pmc", "arxiv", "base"):
        assert states.get(name) == "zero_results", (
            f"{name} expected zero_results, got {states.get(name)}"
        )
    # key-absent fallback sources → skipped_no_key
    for name in ("core", "dimensions", "google_scholar"):
        assert states.get(name) == "skipped_no_key", (
            f"{name} expected skipped_no_key, got {states.get(name)}"
        )
    # all expected sources present
    assert len(states) == 10
    # all values are valid SourceTerminalState literals
    valid: set[SourceTerminalState] = {
        "queried",
        "skipped_no_key",
        "skipped_disabled",
        "rate_limited",
        "zero_results",
        "failed",
    }
    for name, state in states.items():
        assert state in valid, f"{name}: unexpected state {state!r}"
