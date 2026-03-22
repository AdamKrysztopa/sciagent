"""Zotero upsert tool adapter."""

from __future__ import annotations

from dataclasses import dataclass

from agt.models import NormalizedPaper


@dataclass(slots=True)
class UpsertResult:
    created: int
    unchanged: int
    failed: int


async def upsert_papers(collection_name: str, papers: list[NormalizedPaper]) -> UpsertResult:
    """Return placeholder write result while integration is pending."""

    if not collection_name.strip():
        return UpsertResult(created=0, unchanged=0, failed=len(papers))
    return UpsertResult(created=len(papers), unchanged=0, failed=0)
