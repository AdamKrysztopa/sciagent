"""Tests for src/agt/tools/pdf_attach.py (SCI-0302, AGT-13)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from agt.config import Settings
from agt.models import CollectionResult, ItemWriteOutcome, NormalizedPaper, WriteResult
from agt.tools.arxiv_api import ArxivClient
from agt.tools.pdf_attach import (
    attach_pdfs_to_items,
    fetch_pdf_bytes,
    is_valid_pdf,
    save_pdf,
    sha256_hex,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PDF = b"%PDF-1.4 fake content for testing"
_ARXIV_ATTENTION_PDF_URL = "https://arxiv.org/pdf/1706.03762"


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
    enable_pdf_attachment: bool = False
    pdf_download_timeout: int = 60
    resolved_pdf_dir: Path = field(default_factory=lambda: Path("/tmp/sciagent_test_pdfs"))


def _paper(
    *,
    title: str = "Test Paper",
    open_access: bool = True,
    pdf_url: str | None = "https://example.com/paper.pdf",
    doi: str | None = None,
    arxiv_id: str | None = None,
) -> NormalizedPaper:
    return NormalizedPaper(
        title=title,
        open_access=open_access,
        pdf_url=pdf_url,
        doi=doi,
        arxiv_id=arxiv_id,
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
# Unit tests: helper functions
# ---------------------------------------------------------------------------


def test_is_valid_pdf_true() -> None:
    assert is_valid_pdf(b"%PDF-1.4 hello") is True


def test_is_valid_pdf_false_for_html() -> None:
    assert is_valid_pdf(b"<html><body>Not a PDF</body></html>") is False


def test_is_valid_pdf_false_for_empty() -> None:
    assert is_valid_pdf(b"") is False


def test_sha256_hex_length_and_type() -> None:
    result = sha256_hex(b"hello world")
    assert isinstance(result, str)
    assert len(result) == 64  # noqa: PLR2004
    assert result == hashlib.sha256(b"hello world").hexdigest()


def test_sha256_hex_deterministic() -> None:
    assert sha256_hex(b"data") == sha256_hex(b"data")


def test_save_pdf_creates_file(tmp_path: Path) -> None:
    dest = save_pdf(_FAKE_PDF, tmp_path)
    assert dest.exists()
    assert dest.read_bytes() == _FAKE_PDF
    assert dest.name == f"{sha256_hex(_FAKE_PDF)}.pdf"


def test_save_pdf_creates_missing_dir(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c"
    dest = save_pdf(_FAKE_PDF, nested)
    assert dest.exists()


def test_save_pdf_idempotent(tmp_path: Path) -> None:
    save_pdf(_FAKE_PDF, tmp_path)
    dest = save_pdf(_FAKE_PDF, tmp_path)
    assert dest.exists()


# ---------------------------------------------------------------------------
# Unit tests: fetch_pdf_bytes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fetch_pdf_bytes_success() -> None:
    mock_resp = MagicMock()
    mock_resp.content = _FAKE_PDF
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    data = await fetch_pdf_bytes("https://example.com/paper.pdf", client=mock_client)
    assert data == _FAKE_PDF
    mock_client.get.assert_called_once_with(
        "https://example.com/paper.pdf",
        follow_redirects=True,
        timeout=60.0,
    )


@pytest.mark.anyio
async def test_fetch_pdf_bytes_raises_for_non_pdf() -> None:
    mock_resp = MagicMock()
    mock_resp.content = b"<html>not a pdf</html>"
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with pytest.raises(ValueError, match="not a PDF"):
        await fetch_pdf_bytes("https://example.com/page.html", client=mock_client)


@pytest.mark.anyio
async def test_fetch_pdf_bytes_propagates_http_error() -> None:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(httpx.ConnectError):
        await fetch_pdf_bytes("https://example.com/paper.pdf", client=mock_client)


# ---------------------------------------------------------------------------
# Unit tests: attach_pdfs_to_items — no credentials (all-skip)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_attach_returns_all_skipped_when_no_api_key() -> None:
    @dataclass(slots=True)
    class _NoKey:
        zotero_api_key: None = None
        zotero_library_id: str | None = "123"
        zotero_library_type: str = "user"
        timeout_seconds: int = 30
        enable_pdf_attachment: bool = False
        pdf_download_timeout: int = 60

    papers = [_paper(), _paper(title="P2")]
    outcomes = [_created_outcome(0, "K1"), _created_outcome(1, "K2")]
    wr = _write_result(outcomes)

    result = await attach_pdfs_to_items(papers, wr, cast(Settings, _NoKey()))
    assert result.attached == 0
    assert result.failed == 0
    assert result.skipped == 2  # noqa: PLR2004


@pytest.mark.anyio
async def test_attach_returns_all_skipped_when_no_library_id() -> None:
    @dataclass(slots=True)
    class _NoLib:
        zotero_api_key: _Secret = field(default_factory=lambda: _Secret("key"))
        zotero_library_id: None = None
        zotero_library_type: str = "user"
        timeout_seconds: int = 30
        enable_pdf_attachment: bool = False
        pdf_download_timeout: int = 60

    papers = [_paper()]
    wr = _write_result([_created_outcome(0, "K1")])

    result = await attach_pdfs_to_items(papers, wr, cast(Settings, _NoLib()))
    assert result.skipped == 1
    assert result.attached == 0


# ---------------------------------------------------------------------------
# Unit tests: linked_url path (enable_pdf_attachment=False)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_closed_access_paper_with_pdf_url_is_not_skipped() -> None:
    paper = _paper(open_access=False, pdf_url="https://example.com/p.pdf")
    wr = _write_result([_created_outcome(0, "K1")])
    settings = cast(Settings, _Settings())

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_resp)

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.skipped == 0
    assert result.attached == 1
    assert result.failed == 0


@pytest.mark.anyio
async def test_paper_without_pdf_url_is_skipped() -> None:
    paper = _paper(open_access=True, pdf_url=None)
    wr = _write_result([_created_outcome(0, "K1")])
    settings = cast(Settings, _Settings())

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    mock_client.post.assert_not_called()
    assert result.skipped == 1


@pytest.mark.anyio
async def test_paper_with_no_item_key_in_write_result_is_skipped() -> None:
    paper = _paper(open_access=True, pdf_url="https://example.com/p.pdf")
    wr = _write_result([ItemWriteOutcome(index=0, title="Paper", status="unchanged")])
    settings = cast(Settings, _Settings())

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    mock_client.post.assert_not_called()
    assert result.skipped == 1


@pytest.mark.anyio
async def test_successful_pdf_attachment() -> None:
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
    call_args = mock_client.post.call_args
    posted_url: str = call_args[0][0]
    assert posted_url.endswith("/items")
    posted_body: list[dict[str, object]] = call_args[1]["json"]
    assert posted_body[0]["parentItem"] == "KEY001"
    assert posted_body[0]["linkMode"] == "linked_url"


@pytest.mark.anyio
async def test_failed_post_increments_failed_without_raising() -> None:
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
    paper = _paper(open_access=True, pdf_url="https://example.com/full.pdf")
    wr = _write_result([_created_outcome(0, "KEY003")])
    settings = cast(Settings, _Settings())

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.failed == 1
    assert result.attached == 0


@pytest.mark.anyio
async def test_mixed_batch_counts() -> None:
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
    assert result.attached == 2  # noqa: PLR2004
    assert result.skipped == 1
    assert result.failed == 0


# ---------------------------------------------------------------------------
# Unit tests: imported_file path (enable_pdf_attachment=True)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _SettingsWithDownload:
    zotero_api_key: _Secret = field(default_factory=lambda: _Secret("test-key"))
    zotero_library_id: str = "12345"
    zotero_library_type: str = "user"
    timeout_seconds: int = 30
    enable_pdf_attachment: bool = True
    pdf_download_timeout: int = 60
    resolved_pdf_dir: Path = field(default_factory=lambda: Path("/tmp/sciagent_test_pdfs"))


def _make_create_item_resp(key: str = "ATT0001") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value={"successful": {"0": {"key": key}}})
    return resp


def _make_auth_resp(upload_key: str = "UKEY1") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(
        return_value={
            "url": "https://s3.amazonaws.com/zotero-upload",
            "contentType": "application/octet-stream",
            "prefix": b"".decode(),
            "suffix": b"".decode(),
            "uploadKey": upload_key,
        }
    )
    return resp


def _make_auth_exists_resp() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value={"exists": 1})
    return resp


def _make_ok_resp(status: int = 204) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    return resp


@pytest.mark.anyio
async def test_imported_file_full_upload_path() -> None:
    """When enable_pdf_attachment=True, full 4-step upload is performed."""
    paper = _paper(
        open_access=True,
        pdf_url="https://arxiv.org/pdf/1706.03762",
        arxiv_id="1706.03762",
    )
    wr = _write_result([_created_outcome(0, "PARENT1")])
    settings = cast(Settings, _SettingsWithDownload())

    # Sequence: get PDF → create attachment item → get auth → S3 upload → register
    pdf_resp = MagicMock()
    pdf_resp.content = _FAKE_PDF
    pdf_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=pdf_resp)
    mock_client.post = AsyncMock(
        side_effect=[
            _make_create_item_resp("ATT001"),  # create imported_file item
            _make_auth_resp("UKEY1"),  # get upload auth
            _make_ok_resp(204),  # S3 upload
            _make_ok_resp(204),  # register upload
        ]
    )

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.attached == 1
    assert result.failed == 0
    assert result.skipped == 0
    assert mock_client.get.call_count == 1
    assert mock_client.post.call_count == 4  # noqa: PLR2004


@pytest.mark.anyio
async def test_imported_file_already_exists_on_s3() -> None:
    """When Zotero reports file already exists, counts as attached."""
    paper = _paper(open_access=True, pdf_url="https://arxiv.org/pdf/1706.03762")
    wr = _write_result([_created_outcome(0, "PARENT2")])
    settings = cast(Settings, _SettingsWithDownload())

    pdf_resp = MagicMock()
    pdf_resp.content = _FAKE_PDF
    pdf_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=pdf_resp)
    mock_client.post = AsyncMock(
        side_effect=[
            _make_create_item_resp("ATT002"),
            _make_auth_exists_resp(),
        ]
    )

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.attached == 1
    assert mock_client.post.call_count == 2  # noqa: PLR2004


@pytest.mark.anyio
async def test_imported_file_download_failure_does_not_raise() -> None:
    """PDF download failure increments failed, never raises."""
    paper = _paper(open_access=True, pdf_url="https://example.com/broken.pdf")
    wr = _write_result([_created_outcome(0, "PARENT3")])
    settings = cast(Settings, _SettingsWithDownload())

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.failed == 1
    assert result.attached == 0


@pytest.mark.anyio
async def test_imported_file_invalid_pdf_response_does_not_raise() -> None:
    """Non-PDF response body increments failed, never raises."""
    paper = _paper(open_access=True, pdf_url="https://example.com/html.html")
    wr = _write_result([_created_outcome(0, "PARENT4")])
    settings = cast(Settings, _SettingsWithDownload())

    html_resp = MagicMock()
    html_resp.content = b"<html>Not a PDF</html>"
    html_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=html_resp)

    result = await attach_pdfs_to_items([paper], wr, settings, client=mock_client)
    assert result.failed == 1
    assert result.attached == 0


# ---------------------------------------------------------------------------
# Integration test: real arXiv PDF download (requires network)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_arxiv_attention_is_all_you_need_pdf_download() -> None:
    """Fetch 'Attention Is All You Need' via arXiv search and download its PDF.

    Requires network access. Searches arXiv for the paper to discover
    the pdf_url, then downloads the binary and verifies it is a real PDF.
    """
    # Try to discover the PDF URL via the search tool; fall back if rate-limited.
    arxiv = ArxivClient(timeout_seconds=30, retries=1)
    pdf_url: str | None = None
    try:
        results = await arxiv.search("attention is all you need transformer", limit=5)
        target = next(
            (p for p in results if p.arxiv_id and p.arxiv_id.startswith("1706.03762")),
            None,
        )
        pdf_url = target.pdf_url if target is not None else None
    except Exception:
        pass  # rate-limited or network error; proceed with known URL below
    pdf_url = pdf_url or _ARXIV_ATTENTION_PDF_URL

    async with httpx.AsyncClient() as download_client:
        pdf_bytes = await fetch_pdf_bytes(pdf_url, client=download_client, timeout=60.0)

    assert is_valid_pdf(pdf_bytes), "Downloaded bytes are not a valid PDF"
    digest = sha256_hex(pdf_bytes)
    assert len(digest) == 64  # noqa: PLR2004
    assert pdf_bytes[:4] == b"%PDF"
    # Sanity-check size: the paper is ~2MB
    assert len(pdf_bytes) > 500_000, f"PDF too small: {len(pdf_bytes)} bytes"  # noqa: PLR2004
