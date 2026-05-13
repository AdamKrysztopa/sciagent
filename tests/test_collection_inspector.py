"""Tests for src/agt/zotero/collection_inspector.py (SCI-0301)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from agt.config import Settings
from agt.models import NormalizedAuthor, NormalizedPaper
from agt.tools.zotero_upsert import normalize_doi, title_author_fingerprint
from agt.zotero.collection_inspector import (
    LibraryIndex,
    classify_paper,
    fetch_library_index,
)

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


def _make_zotero_item(
    *,
    key: str,
    title: str,
    doi: str = "",
    authors: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a minimal Zotero item structure."""
    creators: list[dict[str, str]] = []
    for first, last in authors or []:
        creators.append({"creatorType": "author", "firstName": first, "lastName": last})
    return {
        "key": key,
        "data": {
            "key": key,
            "title": title,
            "DOI": doi,
            "creators": creators,
            "abstractNote": "",
            "url": "",
        },
    }


def _paper(
    *,
    title: str = "Test Paper",
    doi: str | None = None,
    authors: list[str] | None = None,
) -> NormalizedPaper:
    author_names = authors or ["Smith, John"]
    return NormalizedPaper(
        title=title,
        doi=doi,
        authors=[NormalizedAuthor(name=a) for a in author_names],
    )


# ---------------------------------------------------------------------------
# classify_paper tests
# ---------------------------------------------------------------------------


def test_classify_paper_in_library_by_doi() -> None:
    """A paper whose DOI appears in the index is classified as in_library."""
    doi = "10.1234/test"
    index = LibraryIndex(
        doi_set=frozenset([normalize_doi(doi) or ""]),
        fingerprint_set=frozenset(),
    )
    paper = _paper(doi=doi, authors=["Jones, Alice"])
    assert classify_paper(paper, index) == "in_library"


def test_classify_paper_possible_duplicate_by_fingerprint() -> None:
    """A paper matching by title+author fingerprint but not DOI is a possible_duplicate."""
    title = "Machine Learning in Medicine"
    authors = ["Smith, John"]
    fp = title_author_fingerprint(title, authors)
    index = LibraryIndex(
        doi_set=frozenset(),
        fingerprint_set=frozenset([fp]),
    )
    # Different DOI so it won't match by DOI
    paper = _paper(title=title, doi="10.9999/different", authors=authors)
    assert classify_paper(paper, index) == "possible_duplicate"


def test_classify_paper_new_when_no_match() -> None:
    """A paper with no matching DOI or fingerprint is classified as new."""
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset())
    paper = _paper(title="Novel Findings", doi="10.1234/novel", authors=["Brown, Eve"])
    assert classify_paper(paper, index) == "new"


def test_classify_paper_doi_match_takes_priority_over_fingerprint() -> None:
    """DOI match should return in_library even if fingerprint also matches."""
    doi = "10.1234/exact"
    title = "Exact Match Paper"
    authors = ["Doe, Jane"]
    fp = title_author_fingerprint(title, authors)
    index = LibraryIndex(
        doi_set=frozenset([normalize_doi(doi) or ""]),
        fingerprint_set=frozenset([fp]),
    )
    paper = _paper(title=title, doi=doi, authors=authors)
    assert classify_paper(paper, index) == "in_library"


def test_classify_paper_no_doi_only_fingerprint() -> None:
    """Paper with no DOI falls back to fingerprint matching."""
    title = "Fingerprint Only Paper"
    authors = ["Garcia, Maria"]
    fp = title_author_fingerprint(title, authors)
    index = LibraryIndex(
        doi_set=frozenset(),
        fingerprint_set=frozenset([fp]),
    )
    paper = _paper(title=title, doi=None, authors=authors)
    assert classify_paper(paper, index) == "possible_duplicate"


# ---------------------------------------------------------------------------
# fetch_library_index — graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fetch_library_index_returns_empty_when_no_api_key() -> None:
    """Returns empty LibraryIndex without making HTTP calls when key is absent."""

    @dataclass(slots=True)
    class _NoKeySetting:
        zotero_api_key: None = None
        zotero_library_id: str | None = "999"
        zotero_library_type: str = "user"
        timeout_seconds: int = 30

    index = await fetch_library_index(cast(Settings, _NoKeySetting()))
    assert index.doi_set == frozenset()
    assert index.fingerprint_set == frozenset()
    assert index.items == []


@pytest.mark.anyio
async def test_fetch_library_index_returns_empty_when_no_library_id() -> None:
    """Returns empty LibraryIndex without making HTTP calls when library_id is absent."""

    @dataclass(slots=True)
    class _NoLibSetting:
        zotero_api_key: _Secret = field(default_factory=lambda: _Secret("key"))
        zotero_library_id: None = None
        zotero_library_type: str = "user"
        timeout_seconds: int = 30

    index = await fetch_library_index(cast(Settings, _NoLibSetting()))
    assert index.doi_set == frozenset()
    assert index.fingerprint_set == frozenset()


# ---------------------------------------------------------------------------
# fetch_library_index — with mocked HTTP
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fetch_library_index_whole_library() -> None:
    """Fetches /users/{id}/items/top and builds the correct index."""
    item1 = _make_zotero_item(
        key="AAA111",
        title="Paper One",
        doi="10.1234/one",
        authors=[("John", "Smith")],
    )
    item2 = _make_zotero_item(
        key="BBB222",
        title="Paper Two",
        doi="",
        authors=[("Alice", "Jones")],
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [item1, item2]

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    settings = cast(Settings, _Settings())
    index = await fetch_library_index(settings, client=mock_client)

    _EXPECTED_ITEM_COUNT = 2
    # DOI for item1 should be present, item2 has no DOI
    assert "10.1234/one" in index.doi_set
    assert len(index.items) == _EXPECTED_ITEM_COUNT
    assert len(index.fingerprint_set) == _EXPECTED_ITEM_COUNT  # both have title + author


@pytest.mark.anyio
async def test_fetch_library_index_collection_not_found_returns_empty() -> None:
    """Returns empty LibraryIndex when collection name does not match anything."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = []  # no collections matching the name

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    settings = cast(Settings, _Settings())
    index = await fetch_library_index(
        settings,
        collection_name="NonExistent",
        client=mock_client,
    )
    assert index.doi_set == frozenset()
    assert index.items == []


@pytest.mark.anyio
async def test_fetch_library_index_with_collection_name() -> None:
    """Fetches collection items when collection_name is provided."""
    collections_response = MagicMock()
    collections_response.raise_for_status = MagicMock()
    collections_response.json.return_value = [
        {
            "key": "COL001",
            "data": {"key": "COL001", "name": "MyCollection"},
        }
    ]

    items_response = MagicMock()
    items_response.raise_for_status = MagicMock()
    items_response.json.return_value = [
        _make_zotero_item(
            key="ITM001",
            title="Collection Paper",
            doi="10.5678/col",
            authors=[("Bob", "Brown")],
        )
    ]

    call_count = 0

    async def side_effect(url: str, **kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return collections_response
        return items_response

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=side_effect)

    settings = cast(Settings, _Settings())
    index = await fetch_library_index(
        settings,
        collection_name="MyCollection",
        client=mock_client,
    )
    assert "10.5678/col" in index.doi_set
    assert len(index.items) == 1
