"""Crossref API wrapper returning NormalizedPaper models."""

from __future__ import annotations

from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper


class CrossrefResponseError(RuntimeError):
    """Raised when Crossref response payload is malformed."""


class CrossrefClient:
    """Small bounded client for Crossref works search."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://api.crossref.org",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str, *, limit: int, max_pages: int = 1) -> list[NormalizedPaper]:
        """Search Crossref and return normalized papers."""

        if not query.strip():
            return []

        papers: list[NormalizedPaper] = []
        for page_idx in range(max(1, max_pages)):
            payload = await self._request_json(
                path="/works",
                params={
                    "query.bibliographic": query,
                    "rows": str(limit),
                    "offset": str(page_idx * limit),
                },
            )

            message = payload.get("message")
            if not isinstance(message, dict):
                raise CrossrefResponseError("Crossref payload missing message object")
            message_mapping = cast(dict[str, Any], message)

            raw_items = message_mapping.get("items")
            if not isinstance(raw_items, list):
                raise CrossrefResponseError("Crossref payload missing list field: message.items")

            if not raw_items:
                break

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
                        raise CrossrefResponseError("Crossref payload must be a JSON object")
                    return cast(dict[str, Any], payload)

        raise CrossrefResponseError("Crossref request failed")

    @staticmethod
    def _extract_title(item: dict[str, Any]) -> str:
        title_list = item.get("title")
        if isinstance(title_list, list) and title_list:
            first_title = cast(object, title_list[0])
            if isinstance(first_title, str):
                return first_title.strip()
        return ""

    @staticmethod
    def _extract_year(item: dict[str, Any]) -> int | None:
        published_print = item.get("published-print")
        published_online = item.get("published-online")
        for date_source in (published_print, published_online):
            if not isinstance(date_source, dict):
                continue
            source_mapping = cast(dict[str, Any], date_source)
            date_parts = source_mapping.get("date-parts")
            if isinstance(date_parts, list) and date_parts:
                first = cast(object, date_parts[0])
                if isinstance(first, list) and first:
                    first_year = cast(object, first[0])
                    if isinstance(first_year, int):
                        return first_year
        return None

    @staticmethod
    def _extract_authors(item: dict[str, Any]) -> list[str]:
        authors: list[str] = []
        author_list = item.get("author")
        if not isinstance(author_list, list):
            return authors

        for author_obj in cast(list[object], author_list):
            if not isinstance(author_obj, dict):
                continue
            author = cast(dict[str, Any], author_obj)
            given = author.get("given")
            family = author.get("family")
            name_parts: list[str] = []
            if isinstance(given, str) and given.strip():
                name_parts.append(given.strip())
            if isinstance(family, str) and family.strip():
                name_parts.append(family.strip())
            if name_parts:
                authors.append(" ".join(name_parts))

        return authors

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> NormalizedPaper | None:
        title = CrossrefClient._extract_title(item)
        if not title:
            return None

        year = CrossrefClient._extract_year(item)

        doi_value = item.get("DOI")
        doi = doi_value.strip() if isinstance(doi_value, str) and doi_value.strip() else None

        authors = CrossrefClient._extract_authors(item)

        url_value = item.get("URL")
        url = url_value.strip() if isinstance(url_value, str) and url_value.strip() else None

        citation_count = 0
        references_count_value = item.get("is-referenced-by-count")
        if isinstance(references_count_value, int):
            citation_count = max(0, references_count_value)

        return NormalizedPaper(
            title=title,
            year=year,
            doi=doi,
            abstract=None,
            authors=authors,
            url=url,
            source="crossref",
            semantic_score=0.0,
            citation_count=citation_count,
            open_access=False,
        )
