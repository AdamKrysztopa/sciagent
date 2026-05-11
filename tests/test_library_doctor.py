"""Tests for src/agt/zotero/library_doctor.py (SCI-0303)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from agt.config import Settings
from agt.models import DoctorReport
from agt.zotero.collection_inspector import LibraryIndex
from agt.zotero.library_doctor import scan_collection

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


def _make_item(  # noqa: PLR0913
    *,
    key: str,
    title: str = "A Paper",
    doi: str = "10.1234/x",
    abstract: str = "Some abstract text.",
    url: str = "https://example.com/paper",
    authors: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    creators = [
        {"creatorType": "author", "firstName": first, "lastName": last}
        for first, last in (authors or [("John", "Smith")])
    ]
    return {
        "key": key,
        "data": {
            "key": key,
            "title": title,
            "DOI": doi,
            "abstractNote": abstract,
            "url": url,
            "creators": creators,
        },
    }


# ---------------------------------------------------------------------------
# Tests: empty collection
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_collection_returns_empty_report() -> None:
    """Scanning an empty collection returns zero issues and zero duplicates."""
    empty_index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=[])

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=empty_index),
    ):
        report = await scan_collection("EmptyCollection", cast(Settings, _Settings()))

    assert isinstance(report, DoctorReport)
    assert report.total_items == 0
    assert report.issues == []
    assert report.duplicate_pairs == []


# ---------------------------------------------------------------------------
# Tests: issue classification
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_missing_doi_detected() -> None:
    """An item with an empty DOI gets a missing_doi issue."""
    item = _make_item(key="A1", doi="", url="https://ex.com")
    index = LibraryIndex(
        doi_set=frozenset(),
        fingerprint_set=frozenset(),
        items=[item],
    )

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        report = await scan_collection("C", cast(Settings, _Settings()))

    assert any("missing_doi" in i.issue_types for i in report.issues)


@pytest.mark.anyio
async def test_missing_abstract_detected() -> None:
    """An item with an empty abstractNote gets a missing_abstract issue."""
    item = _make_item(key="A2", abstract="", url="https://ex.com")
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=[item])

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        report = await scan_collection("C", cast(Settings, _Settings()))

    assert any("missing_abstract" in i.issue_types for i in report.issues)


@pytest.mark.anyio
async def test_missing_pdf_detected_when_no_url() -> None:
    """An item with no url field gets a missing_pdf issue."""
    item = _make_item(key="A3", url="")
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=[item])

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        report = await scan_collection("C", cast(Settings, _Settings()))

    assert any("missing_pdf" in i.issue_types for i in report.issues)


@pytest.mark.anyio
async def test_healthy_item_has_no_issues() -> None:
    """An item with DOI, abstract, and URL has no issues."""
    item = _make_item(
        key="GOOD1",
        doi="10.9999/good",
        abstract="Full abstract here.",
        url="https://ex.com/paper",
    )
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=[item])

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        report = await scan_collection("C", cast(Settings, _Settings()))

    assert report.issues == []


# ---------------------------------------------------------------------------
# Tests: duplicate detection
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_duplicate_doi_detected() -> None:
    """Two items with the same DOI are flagged as duplicates."""
    item1 = _make_item(key="DUP1", title="Paper Alpha", doi="10.1234/dup")
    item2 = _make_item(key="DUP2", title="Paper Beta", doi="10.1234/dup")
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=[item1, item2])

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        report = await scan_collection("C", cast(Settings, _Settings()))

    assert len(report.duplicate_pairs) == 1
    pair = report.duplicate_pairs[0]
    assert set(pair) == {"DUP1", "DUP2"}
    # DUP2 should have a duplicate issue
    dup_issue = next((i for i in report.issues if i.item_key == "DUP2"), None)
    assert dup_issue is not None
    assert "duplicate" in dup_issue.issue_types
    assert dup_issue.duplicate_of == "DUP1"


@pytest.mark.anyio
async def test_duplicate_fingerprint_detected() -> None:
    """Two items with same title+authors but different DOIs are flagged as duplicates."""
    item1 = _make_item(
        key="FP1",
        title="Same Title",
        doi="10.1111/a",
        authors=[("Jane", "Doe")],
    )
    item2 = _make_item(
        key="FP2",
        title="Same Title",
        doi="10.2222/b",
        authors=[("Jane", "Doe")],
    )
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=[item1, item2])

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        report = await scan_collection("C", cast(Settings, _Settings()))

    assert len(report.duplicate_pairs) >= 1


@pytest.mark.anyio
async def test_multiple_issues_on_one_item() -> None:
    """An item can accumulate multiple issue types."""
    item = _make_item(key="MULTI1", doi="", abstract="", url="")
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=[item])

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        report = await scan_collection("C", cast(Settings, _Settings()))

    assert len(report.issues) == 1
    issue = report.issues[0]
    assert "missing_doi" in issue.issue_types
    assert "missing_abstract" in issue.issue_types
    assert "missing_pdf" in issue.issue_types


@pytest.mark.anyio
async def test_total_items_count() -> None:
    """total_items matches the number of items returned by fetch_library_index."""
    items = [_make_item(key=f"ITM{i}", doi=f"10.x/{i}") for i in range(5)]
    index = LibraryIndex(doi_set=frozenset(), fingerprint_set=frozenset(), items=items)

    with patch(
        "agt.zotero.library_doctor.fetch_library_index",
        new=AsyncMock(return_value=index),
    ):
        report = await scan_collection("C", cast(Settings, _Settings()))

    _EXPECTED_ITEM_COUNT = 5
    assert report.total_items == _EXPECTED_ITEM_COUNT
    assert report.collection_name == "C"
