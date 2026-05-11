"""Tests for src/agt/tools/gap_finder.py (SCI-0304)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from agt.config import Settings
from agt.models import GapSuggestion, NormalizedPaper, SearchMetadata
from agt.providers.protocol import LLMProvider
from agt.tools.gap_finder import find_gaps
from agt.tools.zotero_upsert import normalize_doi
from agt.zotero.collection_inspector import LibraryIndex

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Secret:
    value: str

    def get_secret_value(self) -> str:
        return self.value


@dataclass(slots=True)
class _Settings:
    zotero_api_key: _Secret | None = field(default_factory=lambda: _Secret("test-key"))
    zotero_library_id: str | None = "12345"
    zotero_library_type: str = "user"
    timeout_seconds: int = 30
    semantic_scholar_rate_limit_per_minute: int = 100
    openalex_rate_limit_per_minute: int = 100
    crossref_rate_limit_per_minute: int = 80
    pubmed_rate_limit_per_minute: int = 100
    europe_pmc_rate_limit_per_minute: int = 100
    core_rate_limit_per_minute: int = 60
    arxiv_rate_limit_per_minute: int = 20
    opencitations_rate_limit_per_minute: int = 60
    base_rate_limit_per_minute: int = 40
    dimensions_rate_limit_per_minute: int = 40
    google_scholar_rate_limit_per_minute: int = 20
    zotero_rate_limit_per_minute: int = 60
    llm_rate_limit_per_minute: int = 120
    enable_fallback_retrieval: bool = False


def _make_zotero_item(*, key: str, title: str) -> dict[str, Any]:
    return {
        "key": key,
        "data": {
            "key": key,
            "title": title,
            "DOI": f"10.9999/{key}",
            "abstractNote": "abstract",
            "url": "https://ex.com",
            "creators": [{"firstName": "A", "lastName": "B"}],
        },
    }


def _paper(
    *,
    title: str = "New Paper",
    doi: str | None = "10.1111/new",
    authors: list[str] | None = None,
) -> NormalizedPaper:
    return NormalizedPaper(
        title=title,
        doi=doi,
        authors=authors or ["Author, A"],
    )


class _FakeProvider:
    def __init__(self, response: str) -> None:
        self._response = response

    def invoke(self, prompt: str) -> str:
        return self._response

    async def ainvoke(self, prompt: str) -> str:
        return self._response

    def bind_tools(self, tools: object) -> LLMProvider:
        return self  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tests: empty collection
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_collection_returns_empty_suggestion() -> None:
    """When the collection has no items, return a GapSuggestion with empty papers."""
    empty_index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=[])

    with patch(
        "agt.tools.gap_finder.fetch_library_index",
        new=AsyncMock(return_value=empty_index),
    ):
        result = await find_gaps("Empty", cast(Settings, _Settings()), _FakeProvider("{}"))

    assert isinstance(result, GapSuggestion)
    assert result.papers == []


# ---------------------------------------------------------------------------
# Tests: LLM parse failure returns graceful empty result
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_llm_parse_failure_returns_empty_gracefully() -> None:
    """When the LLM returns invalid JSON, find_gaps returns an empty GapSuggestion."""
    items = [_make_zotero_item(key="K1", title="Some Paper")]
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=items)

    # LLM returns invalid JSON (not parseable as a dict with 'queries')
    with patch(
        "agt.tools.gap_finder.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        result = await find_gaps(
            "TestCol",
            cast(Settings, _Settings()),
            _FakeProvider("not valid json at all !!!"),
        )

    assert isinstance(result, GapSuggestion)
    assert result.papers == []


@pytest.mark.anyio
async def test_llm_invocation_failure_returns_empty_gracefully() -> None:
    """When the LLM raises an exception, find_gaps returns an empty GapSuggestion."""
    items = [_make_zotero_item(key="K2", title="Another Paper")]
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=items)

    class _FailProvider:
        def invoke(self, prompt: str) -> str:
            raise RuntimeError("LLM down")

        async def ainvoke(self, prompt: str) -> str:
            raise RuntimeError("LLM down")

        def bind_tools(self, tools: object) -> LLMProvider:
            return self  # type: ignore[return-value]

    with patch(
        "agt.tools.gap_finder.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        result = await find_gaps("TestCol", cast(Settings, _Settings()), _FailProvider())

    assert isinstance(result, GapSuggestion)
    assert result.papers == []


# ---------------------------------------------------------------------------
# Tests: existing papers filtered out of gap suggestions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_existing_papers_are_filtered_from_gap_results() -> None:
    """Papers already in the library are not included in gap suggestions."""
    existing_doi = "10.1234/existing"
    index = LibraryIndex(
        doi_set=frozenset([normalize_doi(existing_doi) or ""]),
        fingerprint_set=frozenset(),
        items=[_make_zotero_item(key="K1", title="Existing Paper")],
    )

    # LLM suggests queries
    llm_json = json.dumps({
        "reasoning": "Some gaps exist",
        "queries": ["quantum computing"],
    })

    # search_papers returns one paper that is already in the library
    existing_paper = _paper(title="Existing Paper", doi=existing_doi)
    new_paper = _paper(title="Brand New Paper", doi="10.5555/brandnew")

    fake_metadata = SearchMetadata(original_query="q", regex_query="q")

    async def fake_search(
        query: str, limit: int = 10, *, settings: object = None, **kwargs: object
    ) -> tuple[list[NormalizedPaper], SearchMetadata]:
        return [existing_paper, new_paper], fake_metadata

    with (
        patch(
            "agt.tools.gap_finder.fetch_library_index",
            new=AsyncMock(return_value=index),
        ),
        patch(
            "agt.tools.gap_finder.search_papers",
            new=AsyncMock(side_effect=fake_search),
        ),
    ):
        result = await find_gaps(
            "TestCol",
            cast(Settings, _Settings()),
            _FakeProvider(llm_json),
        )

    assert isinstance(result, GapSuggestion)
    # Only brand new paper should be in suggestions
    assert all(p.doi != existing_doi for p in result.papers)
    new_dois = [p.doi for p in result.papers]
    assert "10.5555/brandnew" in new_dois


# ---------------------------------------------------------------------------
# Tests: deduplication across queries
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_duplicate_results_across_queries_are_deduplicated() -> None:
    """The same paper returned by multiple queries appears only once."""
    index = LibraryIndex(
        doi_set=frozenset(),
        fingerprint_set=frozenset(),
        items=[_make_zotero_item(key="K1", title="Seed Paper")],
    )

    llm_json = json.dumps({
        "reasoning": "Check multiple angles",
        "queries": ["query A", "query B"],
    })

    duplicate_paper = _paper(title="Duplicate Result", doi="10.7777/dup")
    fake_metadata = SearchMetadata(original_query="q", regex_query="q")

    call_count = 0

    async def fake_search(
        query: str, limit: int = 10, *, settings: object = None, **kwargs: object
    ) -> tuple[list[NormalizedPaper], SearchMetadata]:
        nonlocal call_count
        call_count += 1
        return [duplicate_paper], fake_metadata

    with (
        patch(
            "agt.tools.gap_finder.fetch_library_index",
            new=AsyncMock(return_value=index),
        ),
        patch(
            "agt.tools.gap_finder.search_papers",
            new=AsyncMock(side_effect=fake_search),
        ),
    ):
        result = await find_gaps(
            "TestCol",
            cast(Settings, _Settings()),
            _FakeProvider(llm_json),
        )

    # Should only appear once despite two queries returning the same paper
    dois = [p.doi for p in result.papers]
    assert dois.count("10.7777/dup") == 1


# ---------------------------------------------------------------------------
# Tests: search failure per query is handled gracefully
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_search_failure_per_query_does_not_raise() -> None:
    """A search_papers exception on a query is swallowed; other queries proceed."""
    index = LibraryIndex(
        doi_set=frozenset(),
        fingerprint_set=frozenset(),
        items=[_make_zotero_item(key="K1", title="Seed")],
    )

    llm_json = json.dumps({
        "reasoning": "Some gaps",
        "queries": ["failing query", "working query"],
    })

    good_paper = _paper(title="Good Paper", doi="10.1234/good")
    fake_metadata = SearchMetadata(original_query="q", regex_query="q")

    call_count = 0

    async def fake_search(
        query: str, limit: int = 10, *, settings: object = None, **kwargs: object
    ) -> tuple[list[NormalizedPaper], SearchMetadata]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("search backend unreachable")
        return [good_paper], fake_metadata

    with (
        patch(
            "agt.tools.gap_finder.fetch_library_index",
            new=AsyncMock(return_value=index),
        ),
        patch(
            "agt.tools.gap_finder.search_papers",
            new=AsyncMock(side_effect=fake_search),
        ),
    ):
        result = await find_gaps(
            "TestCol",
            cast(Settings, _Settings()),
            _FakeProvider(llm_json),
        )

    # Working query result should be present
    assert any(p.doi == "10.1234/good" for p in result.papers)
    assert result.reasoning == "Some gaps"
