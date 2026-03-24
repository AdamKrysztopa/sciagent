"""Europe PMC API wrapper returning NormalizedPaper models."""

from __future__ import annotations

from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper


class EuropePMCResponseError(RuntimeError):
    """Raised when Europe PMC response payload is malformed."""


class EuropePMCClient:
    """Small bounded client for Europe PMC search."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://www.ebi.ac.uk/europepmc/webservices/rest",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
        """Search Europe PMC and return normalized papers."""

        if not query.strip():
            return []

        payload = await self._request_json(
            path="/search",
            params={
                "query": query,
                "format": "json",
                "pageSize": str(limit),
            },
        )

        raw_result_list = payload.get("resultList")
        if not isinstance(raw_result_list, dict):
            raise EuropePMCResponseError("Europe PMC payload missing resultList object")
        result_list = cast(dict[str, Any], raw_result_list)

        raw_items = result_list.get("result")
        if not isinstance(raw_items, list):
            raise EuropePMCResponseError("Europe PMC payload missing resultList.result")

        papers: list[NormalizedPaper] = []
        for item_obj in cast(list[object], raw_items):
            if not isinstance(item_obj, dict):
                continue
            normalized = self._normalize_item(cast(dict[str, Any], item_obj))
            if normalized is not None:
                papers.append(normalized)
        return papers

    async def _request_json(self, *, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
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
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise EuropePMCResponseError("Europe PMC payload must be a JSON object")
                    return cast(dict[str, Any], payload)

        raise EuropePMCResponseError("Europe PMC request failed")

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> NormalizedPaper | None:
        title_value = item.get("title")
        title = title_value.strip() if isinstance(title_value, str) else ""
        if not title:
            return None

        year: int | None = None
        pub_year = item.get("pubYear")
        if isinstance(pub_year, str) and pub_year.isdigit():
            year = int(pub_year)
        elif isinstance(pub_year, int):
            year = pub_year

        doi = item.get("doi") if isinstance(item.get("doi"), str) else None
        if isinstance(doi, str):
            doi = doi.strip() or None

        abstract_text = item.get("abstractText")
        abstract = (
            abstract_text.strip()
            if isinstance(abstract_text, str) and abstract_text.strip()
            else None
        )

        authors: list[str] = []
        author_string = item.get("authorString")
        if isinstance(author_string, str) and author_string.strip():
            raw_authors = [part.strip() for part in author_string.split(",")]
            authors = [author for author in raw_authors if author]

        source = item.get("source") if isinstance(item.get("source"), str) else ""
        item_id = item.get("id") if isinstance(item.get("id"), str) else ""
        url = f"https://europepmc.org/article/{source}/{item_id}" if source and item_id else None

        open_access_raw = item.get("isOpenAccess")
        open_access = bool(isinstance(open_access_raw, str) and open_access_raw.upper() == "Y")

        citation_count = 0
        cited_by = item.get("citedByCount")
        if isinstance(cited_by, int):
            citation_count = max(0, cited_by)
        elif isinstance(cited_by, str) and cited_by.isdigit():
            citation_count = int(cited_by)

        return NormalizedPaper(
            title=title,
            year=year,
            doi=doi,
            abstract=abstract,
            authors=authors,
            url=url,
            source="europe_pmc",
            semantic_score=0.0,
            citation_count=citation_count,
            open_access=open_access,
        )
