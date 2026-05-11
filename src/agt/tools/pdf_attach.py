"""Attach open-access PDFs to Zotero items after upsert (SCI-0302)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from agt.config import Settings
from agt.models import NormalizedPaper, WriteResult
from agt.tools.zotero_upsert import ZOTERO_API_BASE, library_prefix

_logger = structlog.get_logger("agt.pdf_attach")

HTTP_OK = 200
HTTP_CREATED = 201


@dataclass(slots=True)
class PdfAttachResult:
    """Aggregate outcome of PDF attachment attempts."""

    attached: int
    failed: int
    skipped: int


async def attach_pdfs_to_items(
    papers: list[NormalizedPaper],
    write_result: WriteResult,
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> PdfAttachResult:
    """Attach open-access PDF URLs to newly-created Zotero items.

    Only processes papers where ``paper.open_access`` is True and
    ``paper.pdf_url`` is not None.  Matches each paper to its Zotero
    ``item_key`` via ``write_result.outcomes`` (status="created", same index).

    A failed attachment POST increments ``failed`` but never raises.
    If Zotero credentials are absent, returns an all-skipped result.
    """
    if settings.zotero_api_key is None or settings.zotero_library_id is None:
        return PdfAttachResult(attached=0, failed=0, skipped=len(papers))

    # Build index: paper_index -> item_key for created items
    key_by_index: dict[int, str] = {}
    for outcome in write_result.outcomes:
        if outcome.status == "created" and outcome.item_key is not None:
            key_by_index[outcome.index] = outcome.item_key

    headers = {"Zotero-API-Key": settings.zotero_api_key.get_secret_value()}
    prefix = library_prefix(settings)

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
            if not paper.open_access or paper.pdf_url is None:
                skipped += 1
                continue

            item_key = key_by_index.get(idx)
            if item_key is None:
                skipped += 1
                continue

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
                    f"{prefix}/items",
                    headers=headers,
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
