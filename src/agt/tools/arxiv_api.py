"""arXiv API wrapper returning NormalizedPaper models."""

# ruff: noqa: PLR2004
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper


class ArxivResponseError(RuntimeError):
    """Raised when arXiv payload is malformed."""


class ArxivClient:
    """Small bounded client for arXiv Atom feed search."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://export.arxiv.org/api/query",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url

    async def search(
        self,
        query: str,
        *,
        limit: int,
        categories: list[str] | None = None,
    ) -> list[NormalizedPaper]:
        if not query.strip():
            return []

        search_query = query
        if categories:
            cat_query = " OR ".join(f"cat:{cat}" for cat in categories if cat)
            if cat_query:
                search_query = f"({query}) AND ({cat_query})"

        payload = await self._request_text(
            query={
                "search_query": search_query,
                "start": "0",
                "max_results": str(limit),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
        )
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ArxivResponseError("arXiv XML parse failed") from exc

        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        papers: list[NormalizedPaper] = []
        for entry in root.findall("atom:entry", ns):
            title = " ".join(
                (entry.findtext("atom:title", default="", namespaces=ns) or "").split()
            )
            if not title:
                continue
            summary = " ".join(
                (entry.findtext("atom:summary", default="", namespaces=ns) or "").split()
            )
            abstract = summary or None
            entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            arxiv_id = entry_id.rsplit("/", 1)[-1] if entry_id else None
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
            year: int | None = None
            if len(published) >= 4 and published[:4].isdigit():
                year = int(published[:4])
            authors = []
            for author in entry.findall("atom:author", ns):
                name = (author.findtext("atom:name", default="", namespaces=ns) or "").strip()
                if name:
                    authors.append(name)
            pdf_url: str | None = None
            for link in entry.findall("atom:link", ns):
                href = (link.attrib.get("href") or "").strip()
                rel = (link.attrib.get("rel") or "").strip()
                link_type = (link.attrib.get("type") or "").strip()
                if href and (link_type == "application/pdf" or rel == "related"):
                    pdf_url = href
                    break
            papers.append(
                NormalizedPaper(
                    title=title,
                    year=year,
                    arxiv_id=arxiv_id,
                    abstract=abstract,
                    authors=authors,
                    url=pdf_url or entry_id or None,
                    source="arxiv",
                    semantic_score=0.0,
                    citation_count=0,
                    open_access=True,
                )
            )
        return papers

    async def _request_text(self, *, query: dict[str, str]) -> str:
        # arXiv asks clients to avoid burst traffic; keep a minimum pause per request.
        await asyncio.sleep(3.0)
        params = "&".join(f"{k}={quote_plus(v)}" for k, v in query.items())
        url = f"{self._base_url}?{params}"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            )),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text

        raise ArxivResponseError("arXiv request failed")
