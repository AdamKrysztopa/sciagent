"""BASE SRU API wrapper returning NormalizedPaper models."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper


class BaseSearchResponseError(RuntimeError):
    """Raised when BASE payload is malformed."""


class BaseSearchClient:
    """Small bounded BASE SRU client."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url

    async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
        if not query.strip():
            return []

        xml_text = await self._request_text(
            params={
                "func": "PerformSearch",
                "query": query,
                "hits": str(limit),
                "format": "xml",
            }
        )
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise BaseSearchResponseError("BASE XML parse failed") from exc

        papers: list[NormalizedPaper] = []
        for record in root.findall(".//record"):
            title = " ".join((record.findtext("title", default="") or "").split())
            if not title:
                continue
            year = None
            year_text = (record.findtext("year", default="") or "").strip()
            if year_text.isdigit():
                year = int(year_text)
            doi = (record.findtext("doi", default="") or "").strip() or None
            abstract = (record.findtext("description", default="") or "").strip() or None
            url = (record.findtext("url", default="") or "").strip() or None
            creator = (record.findtext("creator", default="") or "").strip()
            authors = [creator] if creator else []
            access = (record.findtext("accessRights", default="") or "").lower()
            open_access = "open" in access or "free" in access
            papers.append(
                NormalizedPaper(
                    title=title,
                    year=year,
                    doi=doi,
                    abstract=abstract,
                    authors=authors,
                    url=url,
                    source="base",
                    semantic_score=0.0,
                    citation_count=0,
                    open_access=open_access,
                )
            )
        return papers

    async def _request_text(self, *, params: dict[str, str]) -> str:
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
                    response = await client.get(self._base_url, params=params)
                    response.raise_for_status()
                    return response.text

        raise BaseSearchResponseError("BASE request failed")
