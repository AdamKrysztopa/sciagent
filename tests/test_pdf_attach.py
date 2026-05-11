"""Tests for src/agt/tools/pdf_attach.py (SCI-0302)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from agt.config import Settings
from agt.models import CollectionResult, ItemWriteOutcome, NormalizedPaper, WriteResult
from agt.tools.pdf_attach import attach_pdfs_to_items

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


def _paper(
    *,
    title: str = "Test Paper",
    open_access: bool = True,
    pdf_url: str | None = "https://example.com/paper.pdf",
    doi: str | None = None,
) -> NormalizedPaper:
    return NormalizedPaper(
        title=title,
        open_access=open_access,
        pdf_url=pdf_url,
        doi=doi,
        authors=["Smith, John"],
    )


def _write_result(outcomes: list[ItemWriteOutcome]) -> WriteResult:
    created = sum(1 for o in outcomes if o.status == "created")
    unchanged = sum(1 for o in outcomes if o.status == "unchanged")
    failed = sum(1 for o in outcomes if o.status == "failed")
    return WriteResult(
        created=created,
        unchanged=unchanged,
        failed=failed,
        collection=CollectionResult(key="COL001", name="Test", reused=True),
        outcomes=outcomes,
    )


def _created_outcome(index: int, item_key: str) -> ItemWriteOutcome:
    return ItemWriteOutcome(
        index=index,
        title="Paper",
        status="created",
        item_key=item_key,
    )


# ---------------------------------------------------------------------------
# Tests: no credentials
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_attach_returns_all_skipped_when_no_api_key() -> None:
    """When zotero_api_key is None, all papers are skipped without HTTP calls."""

    @dataclass(slots=True)
    class _NoKey:
        zotero_api_key: None = None
        zotero_library_id: str | None = "123"
        zotero_library_type: str = "user"
        timeout_seconds: int = 30

    papers = [_paper(), _paper(title="P2")]
    outcomes = [_created_outcome(0, "K1"), _created_outcome(1, "K2")]
    wr = _write_result(outcomes)

    result = await attach_pdfs_to_items(papers, wr, cast(Settings, _NoKey()))
    _EXPECTED_SKIP_COUNT = 2
    assert result.attached == 0
    assert result.failed == 0
    assert result.skipped == _EXPECTED_SKIP_COUNT


@pytest.mark.anyio
async def test_attach_returns_all_skipped_when_no_library_id() -> None:
    """When zotero_library_id is None, all papers are skipped."""

    @dataclass(slots=True)
    class _NoLib:
        zotero_api_key: _Secret = field(default_factory=lambda: _Secret("key"))
        zotero_library_id: None = None
        zotero_library_type: str = "user"
        timeout_seconds: int = 30

    papers = [_paper()]
    wr = _write_result([_created_outcome(0, "K1")])

    result = await attach_pdfs_to_items(papers, wr, cast(Settings, _NoLib()))
    assert result.skipped == 1
    assert result.attached == 0


# ---------------------------------------------------------------------------
# Tests: non-open-access papers are skipped
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_closed_access_paper_is_skipped() -> None:
    """Papers with open_access=False are not processed."""
    paper = _paper(open_access=False)
    wr = _write_result([_created_outcome(0, "K1")])
    settings = cast(Settings, _Settings())

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    mock_client.post.assert_not_called()
    assert result.skipped == 1
    assert result.attached == 0
    assert result.failed == 0


@pytest.mark.anyio
async def test_paper_without_pdf_url_is_skipped() -> None:
    """Papers with pdf_url=None are skipped even if open_access=True."""
    paper = _paper(open_access=True, pdf_url=None)
    wr = _write_result([_created_outcome(0, "K1")])
    settings = cast(Settings, _Settings())

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    mock_client.post.assert_not_called()
    assert result.skipped == 1


# ---------------------------------------------------------------------------
# Tests: paper not in write_result (no item_key)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_paper_with_no_item_key_in_write_result_is_skipped() -> None:
    """Papers whose index has no created outcome are skipped."""
    paper = _paper(open_access=True, pdf_url="https://example.com/p.pdf")
    # write_result has no created outcome for index 0
    wr = _write_result([ItemWriteOutcome(index=0, title="Paper", status="unchanged")])
    settings = cast(Settings, _Settings())

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    mock_client.post.assert_not_called()
    assert result.skipped == 1


# ---------------------------------------------------------------------------
# Tests: successful attachment
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_successful_pdf_attachment() -> None:
    """Open-access paper with a created item_key gets a linked_url attachment."""
    paper = _paper(open_access=True, pdf_url="https://example.com/full.pdf")
    wr = _write_result([_created_outcome(0, "KEY001")])
    settings = cast(Settings, _Settings())

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.attached == 1
    assert result.failed == 0
    assert result.skipped == 0
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    # Verify endpoint contains item key
    assert "KEY001" in call_kwargs[0][0]


# ---------------------------------------------------------------------------
# Tests: failed POST increments failed, does not raise
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_failed_post_increments_failed_without_raising() -> None:
    """A non-2xx POST response increments failed and does not raise."""
    paper = _paper(open_access=True, pdf_url="https://example.com/full.pdf")
    wr = _write_result([_created_outcome(0, "KEY002")])
    settings = cast(Settings, _Settings())

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.failed == 1
    assert result.attached == 0


@pytest.mark.anyio
async def test_http_error_increments_failed_without_raising() -> None:
    """An httpx.HTTPError increments failed without propagating the exception."""
    paper = _paper(open_access=True, pdf_url="https://example.com/full.pdf")
    wr = _write_result([_created_outcome(0, "KEY003")])
    settings = cast(Settings, _Settings())

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.failed == 1
    assert result.attached == 0


# ---------------------------------------------------------------------------
# Tests: mixed batch
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_mixed_batch_counts() -> None:
    """Verify correct counts for a batch with open, closed, and no-key outcomes."""
    papers = [
        _paper(title="OA Paper", open_access=True, pdf_url="https://ex.com/1.pdf"),
        _paper(title="Closed Paper", open_access=False, pdf_url="https://ex.com/2.pdf"),
        _paper(title="No URL", open_access=True, pdf_url=None),
    ]
    outcomes = [
        _created_outcome(0, "K1"),
        _created_outcome(1, "K2"),
        _created_outcome(2, "K3"),
    ]
    wr = _write_result(outcomes)
    settings = cast(Settings, _Settings())

    mock_resp = MagicMock()
    mock_resp.status_code = 201

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    result = await attach_pdfs_to_items(papers, wr, settings, client=mock_client)
    _EXPECTED_SKIP_COUNT = 2
    # Only the first paper should be attached
    assert result.attached == 1
    assert result.skipped == _EXPECTED_SKIP_COUNT
    assert result.failed == 0
