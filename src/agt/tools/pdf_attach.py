"""Attach open-access PDFs to Zotero items after upsert (SCI-0302, AGT-13)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx
import structlog

from agt.config import Settings
from agt.models import NormalizedPaper, WriteResult
from agt.tools.zotero_upsert import ZOTERO_API_BASE, library_prefix

_logger = structlog.get_logger("agt.pdf_attach")

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204
_PDF_MAGIC = b"%PDF"


@dataclass(slots=True)
class PdfAttachResult:
    """Aggregate outcome of PDF attachment attempts."""

    attached: int
    failed: int
    skipped: int


def is_valid_pdf(data: bytes) -> bool:
    """Return True if data starts with the PDF magic bytes."""
    return data[:4] == _PDF_MAGIC


def sha256_hex(data: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of data."""
    return hashlib.sha256(data).hexdigest()


def save_pdf(data: bytes, pdf_dir: Path) -> Path:
    """Save data to pdf_dir/{sha256}.pdf, creating pdf_dir if needed."""
    pdf_dir.mkdir(parents=True, exist_ok=True)
    dest = pdf_dir / f"{sha256_hex(data)}.pdf"
    dest.write_bytes(data)
    return dest


async def fetch_pdf_bytes(
    url: str,
    *,
    client: httpx.AsyncClient,
    timeout: float = 60.0,
) -> bytes:
    """Download url and return raw bytes.

    Follows redirects (required for arXiv → S3).
    Raises ValueError if the response body is not a PDF.
    Raises httpx.HTTPError on connection or HTTP failures.
    """
    response = await client.get(url, follow_redirects=True, timeout=timeout)
    response.raise_for_status()
    data = response.content
    if not is_valid_pdf(data):
        raise ValueError(f"Response from {url!r} is not a PDF (magic={data[:8]!r})")
    return data


async def _create_attachment_item(
    client: httpx.AsyncClient,
    prefix: str,
    headers: dict[str, str],
    item_key: str,
    filename: str,
) -> str | None:
    """Create an imported_file attachment in Zotero and return its key."""
    payload = [
        {
            "itemType": "attachment",
            "linkMode": "imported_file",
            "parentItem": item_key,
            "title": filename,
            "contentType": "application/pdf",
            "charset": "",
        }
    ]
    resp = await client.post(f"{prefix}/items", headers=headers, json=payload)
    if resp.status_code not in {HTTP_OK, HTTP_CREATED}:
        _logger.warning(
            "create_attachment_item_failed",
            status=resp.status_code,
            item_key=item_key,
        )
        return None
    body_raw: object = resp.json()
    if not isinstance(body_raw, dict):
        return None
    body = cast(dict[str, object], body_raw)
    successful_raw = body.get("successful")
    if not isinstance(successful_raw, dict) or not successful_raw:
        return None
    successful = cast(dict[str, object], successful_raw)
    first: object = next(iter(successful.values()))
    if not isinstance(first, dict):
        return None
    first_item = cast(dict[str, object], first)
    attachment_key = first_item.get("key")
    return str(attachment_key) if isinstance(attachment_key, str) else None


async def _upload_pdf_to_zotero(  # noqa: PLR0911, PLR0913
    client: httpx.AsyncClient,
    prefix: str,
    headers: dict[str, str],
    attachment_key: str,
    pdf_bytes: bytes,
    filename: str,
) -> bool:
    """Three-step Zotero binary upload: authorize → S3 PUT → register."""
    md5_hex = hashlib.md5(pdf_bytes).hexdigest()
    mtime_ms = int(time.time() * 1000)
    file_endpoint = f"{prefix}/items/{attachment_key}/file"

    # Step 1: Get upload authorization
    auth_resp = await client.post(
        file_endpoint,
        headers={**headers, "If-None-Match": "*"},
        data={
            "md5": md5_hex,
            "filename": filename,
            "filesize": str(len(pdf_bytes)),
            "mtime": str(mtime_ms),
            "params": "1",
        },
    )
    if auth_resp.status_code not in {HTTP_OK, HTTP_CREATED}:
        _logger.warning("pdf_upload_auth_failed", status=auth_resp.status_code)
        return False
    auth_raw: object = auth_resp.json()
    if not isinstance(auth_raw, dict):
        return False
    auth = cast(dict[str, object], auth_raw)

    if auth.get("exists") == 1:
        return True

    upload_url = auth.get("url")
    raw_ct = auth.get("contentType", "application/octet-stream")
    content_type = raw_ct if isinstance(raw_ct, str) else "application/octet-stream"
    raw_prefix = auth.get("prefix")
    raw_suffix = auth.get("suffix")
    prefix_bytes = (raw_prefix if isinstance(raw_prefix, str) else "").encode()
    suffix_bytes = (raw_suffix if isinstance(raw_suffix, str) else "").encode()
    upload_key = auth.get("uploadKey")

    if not isinstance(upload_url, str) or not isinstance(upload_key, str):
        _logger.warning("pdf_upload_auth_missing_fields", auth_keys=list(auth.keys()))
        return False

    # Step 2: Upload to S3 (raw body = prefix_bytes + pdf_bytes + suffix_bytes)
    body: bytes = prefix_bytes + pdf_bytes + suffix_bytes
    s3_resp = await client.post(
        upload_url,
        content=body,
        headers={"Content-Type": content_type},
    )
    if s3_resp.status_code not in {HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT}:
        _logger.warning("pdf_s3_upload_failed", status=s3_resp.status_code)
        return False

    # Step 3: Register the completed upload with Zotero
    register_resp = await client.post(
        file_endpoint,
        headers={**headers, "If-Match": md5_hex},
        data={"upload": upload_key},
    )
    if register_resp.status_code not in {HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT}:
        _logger.warning("pdf_register_upload_failed", status=register_resp.status_code)
        return False
    return True


async def attach_pdfs_to_items(  # noqa: PLR0912, PLR0915
    papers: list[NormalizedPaper],
    write_result: WriteResult,
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> PdfAttachResult:
    """Attach open-access PDFs to newly-created Zotero items.

    When ``settings.enable_pdf_attachment`` is True, downloads the PDF binary
    and uploads it as an ``imported_file`` attachment (binary stored in Zotero).
    Otherwise creates a ``linked_url`` attachment (URL link, no binary stored).

    Attachment failures never corrupt item writes — every error is caught,
    logged, and counted in ``result.failed``.
    If Zotero credentials are absent, returns an all-skipped result.
    """
    if settings.zotero_api_key is None or settings.zotero_library_id is None:
        return PdfAttachResult(attached=0, failed=0, skipped=len(papers))

    key_by_index: dict[int, str] = {}
    for outcome in write_result.outcomes:
        if outcome.status == "created" and outcome.item_key is not None:
            key_by_index[outcome.index] = outcome.item_key

    zotero_headers = {"Zotero-API-Key": settings.zotero_api_key.get_secret_value()}
    lib_prefix = library_prefix(settings)
    enable_download = settings.enable_pdf_attachment
    download_timeout = float(settings.pdf_download_timeout)

    owns_client = client is None
    api_client = client or httpx.AsyncClient(
        base_url=ZOTERO_API_BASE,
        timeout=settings.timeout_seconds,
    )

    attached = 0
    failed = 0
    skipped = 0

    try:
        for idx, paper in enumerate(papers):
            if paper.pdf_url is None:
                skipped += 1
                continue

            item_key = key_by_index.get(idx)
            if item_key is None:
                skipped += 1
                continue

            if enable_download:
                try:
                    pdf_bytes = await fetch_pdf_bytes(
                        paper.pdf_url,
                        client=api_client,
                        timeout=download_timeout,
                    )
                    safe_id = (paper.arxiv_id or "paper").replace("/", "_")
                    filename = f"{safe_id}.pdf"
                    attachment_key = await _create_attachment_item(
                        api_client, lib_prefix, zotero_headers, item_key, filename
                    )
                    if attachment_key is None:
                        failed += 1
                        continue
                    ok = await _upload_pdf_to_zotero(
                        api_client,
                        lib_prefix,
                        zotero_headers,
                        attachment_key,
                        pdf_bytes,
                        filename,
                    )
                    if ok:
                        attached += 1
                    else:
                        failed += 1
                except Exception as exc:
                    _logger.warning(
                        "pdf_download_attach_failed",
                        item_key=item_key,
                        pdf_url=paper.pdf_url,
                        error=str(exc),
                    )
                    failed += 1
            else:
                attachment_payload = [
                    {
                        "itemType": "attachment",
                        "linkMode": "linked_url",
                        "url": paper.pdf_url,
                        "title": "PDF",
                        "contentType": "application/pdf",
                        "parentItem": item_key,
                    }
                ]
                try:
                    resp = await api_client.post(
                        f"{lib_prefix}/items",
                        headers=zotero_headers,
                        json=attachment_payload,
                    )
                    if resp.status_code in {HTTP_OK, HTTP_CREATED}:
                        attached += 1
                    else:
                        _logger.warning(
                            "pdf_attach_http_error",
                            item_key=item_key,
                            status_code=resp.status_code,
                            response_text=resp.text[:200],
                        )
                        failed += 1
                except httpx.HTTPError as exc:
                    _logger.warning(
                        "pdf_attach_request_failed",
                        item_key=item_key,
                        error=str(exc),
                    )
                    failed += 1
    finally:
        if owns_client:
            await api_client.aclose()

    return PdfAttachResult(attached=attached, failed=failed, skipped=skipped)
