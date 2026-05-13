"""Tests for citation_expander and related OpenCitations methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest

from agt.models import NormalizedPaper
from agt.tools.citation_expander import (
    expand_citations,
    fetch_openalex_by_dois,
    parse_oa_item,
)
from agt.tools.opencitations import OpenCitationsClient

_EXPECTED_YEAR = 2022
_EXPECTED_CITATION_COUNT = 100
_EXPECTED_RESULT_COUNT = 2


@dataclass
class _FakeRuntime:
    timeout_seconds: int = 10
    retries: int = 1


@dataclass
class _FakeSettings:
    runtime: _FakeRuntime = field(default_factory=_FakeRuntime)
    mailto: str | None = None


# ---------------------------------------------------------------------------
# _parse_oa_item
# ---------------------------------------------------------------------------


def test_parse_oa_item_valid_work() -> None:
    item: dict[str, object] = {
        "title": "Graph Neural Networks",
        "doi": "https://doi.org/10.1000/test",
        "publication_year": 2022,
        "cited_by_count": 100,
        "authorships": [
            {
                "author": {
                    "display_name": "Alice Smith",
                    "id": "https://openalex.org/A123",
                    "orcid": None,
                }
            }
        ],
        "primary_location": {"pdf_url": "https://example.com/paper.pdf"},
    }
    paper = parse_oa_item(item)
    assert paper is not None
    assert paper.title == "Graph Neural Networks"
    assert paper.doi == "10.1000/test"
    assert paper.year == _EXPECTED_YEAR
    assert paper.citation_count == _EXPECTED_CITATION_COUNT
    assert len(paper.authors) == 1
    assert paper.authors[0].name == "Alice Smith"
    assert paper.authors[0].openalex_id == "A123"
    assert paper.oa_url == "https://example.com/paper.pdf"
    assert paper.source == "openalex"


def test_parse_oa_item_missing_title_returns_none() -> None:
    item: dict[str, object] = {
        "title": "",
        "doi": "10.1000/test",
        "publication_year": 2022,
        "cited_by_count": 0,
        "authorships": [],
    }
    assert parse_oa_item(item) is None


def test_parse_oa_item_non_dict_returns_none() -> None:
    assert parse_oa_item("not a dict") is None
    assert parse_oa_item(None) is None
    assert parse_oa_item(42) is None  # type: ignore[arg-type]


def test_parse_oa_item_no_doi() -> None:
    item: dict[str, object] = {
        "title": "Some Paper",
        "doi": None,
        "publication_year": 2020,
        "cited_by_count": 5,
        "authorships": [],
    }
    paper = parse_oa_item(item)
    assert paper is not None
    assert paper.doi is None


# ---------------------------------------------------------------------------
# _fetch_openalex_by_dois
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fetch_openalex_by_dois_empty_list_returns_immediately() -> None:
    with patch("agt.tools.citation_expander.httpx.AsyncClient") as mock_client:
        result = await fetch_openalex_by_dois([], mailto=None)
    assert result == []
    mock_client.assert_not_called()


# ---------------------------------------------------------------------------
# expand_citations
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_expand_citations_empty_seed_dois_returns_empty() -> None:
    with patch("agt.tools.citation_expander.httpx.AsyncClient") as mock_client:
        result = await expand_citations([])
    assert result == []
    mock_client.assert_not_called()


@pytest.mark.anyio
async def test_expand_citations_direction_references_only() -> None:
    """Only references should be fetched when direction='references'."""
    oc_refs = ["10.1000/ref1", "10.1000/ref2"]

    with (
        patch(
            "agt.tools.citation_expander.OpenCitationsClient.references",
            new_callable=AsyncMock,
            return_value=oc_refs,
        ) as mock_refs,
        patch(
            "agt.tools.citation_expander.OpenCitationsClient.citations",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_cits,
        patch(
            "agt.tools.citation_expander.fetch_openalex_by_dois",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        await expand_citations(
            ["10.1000/seed"],
            settings=_FakeSettings(),  # type: ignore[arg-type]
            direction="references",
        )

    mock_refs.assert_called_once()
    mock_cits.assert_not_called()


@pytest.mark.anyio
async def test_expand_citations_returns_tagged_papers() -> None:
    """expand_citations sets citation_relation correctly on returned papers."""
    ref_paper = NormalizedPaper(
        title="Ref Paper", doi="10.1/ref", source="openalex", sources=["openalex"]
    )
    cit_paper = NormalizedPaper(
        title="Cit Paper", doi="10.1/cit", source="openalex", sources=["openalex"]
    )

    with (
        patch(
            "agt.tools.citation_expander.OpenCitationsClient.references",
            new_callable=AsyncMock,
            return_value=["10.1/ref"],
        ),
        patch(
            "agt.tools.citation_expander.OpenCitationsClient.citations",
            new_callable=AsyncMock,
            return_value=["10.1/cit"],
        ),
        patch(
            "agt.tools.citation_expander.fetch_openalex_by_dois",
            new_callable=AsyncMock,
            side_effect=[[ref_paper], [cit_paper]],
        ),
    ):
        results = await expand_citations(
            ["10.1/seed"],
            settings=_FakeSettings(),  # type: ignore[arg-type]
        )

    assert len(results) == _EXPECTED_RESULT_COUNT
    relations = {p.title: p.citation_relation for p in results}
    assert relations["Ref Paper"] == "references"
    assert relations["Cit Paper"] == "cited_by"


# ---------------------------------------------------------------------------
# OpenCitationsClient.references
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_opencitations_references_returns_cited_dois(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str) -> object:
        _ = path
        return [
            {"cited": "10.1000/a", "citing": "10.1000/seed"},
            {"cited": "10.1000/b", "citing": "10.1000/seed"},
        ]

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    result = await client.references("10.1000/seed")
    assert result == ["10.1000/a", "10.1000/b"]


@pytest.mark.anyio
async def test_opencitations_references_empty_doi_returns_empty() -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)
    result = await client.references("   ")
    assert result == []


@pytest.mark.anyio
async def test_opencitations_references_non_list_payload_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str) -> object:
        _ = path
        return {"error": "bad payload"}

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    result = await client.references("10.1000/seed")
    assert result == []


# ---------------------------------------------------------------------------
# OpenCitationsClient.citations
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_opencitations_citations_returns_citing_dois(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake_request_json(*, path: str) -> object:
        _ = path
        return [
            {"citing": "10.1000/x", "cited": "10.1000/seed"},
            {"citing": "10.1000/y", "cited": "10.1000/seed"},
        ]

    monkeypatch.setattr(client, "_request_json", _fake_request_json)
    result = await client.citations("10.1000/seed")
    assert result == ["10.1000/x", "10.1000/y"]


@pytest.mark.anyio
async def test_opencitations_citations_empty_doi_returns_empty() -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)
    result = await client.citations("")
    assert result == []
