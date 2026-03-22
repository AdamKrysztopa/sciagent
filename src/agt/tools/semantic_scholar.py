"""Semantic Scholar API wrapper that returns only NormalizedPaper models."""

from __future__ import annotations

from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper


class SemanticScholarResponseError(RuntimeError):
    """Raised when the API response is malformed or unsupported."""


class SemanticScholarClient:
    """Small bounded client for Semantic Scholar Graph API."""

    _fields = (
        "title,year,abstract,url,isOpenAccess,authors,externalIds,"
        "score,citationCount,influentialCitationCount"
    )

    def __init__(
        self,
        *,
        api_key: str | None,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://api.semanticscholar.org/graph/v1",
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url.rstrip("/")

    async def search(
        self,
        query: str,
        *,
        limit: int,
        year_min: int | None = None,
        year_max: int | None = None,
    ) -> list[NormalizedPaper]:
        """Search papers and normalize into internal model list."""

        if not query.strip():
            return []

        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        params: dict[str, str] = {
            "query": query,
            "limit": str(limit),
            "fields": self._fields,
        }
        if year_min is not None or year_max is not None:
            lower = str(year_min) if year_min is not None else ""
            upper = str(year_max) if year_max is not None else ""
            params["year"] = f"{lower}-{upper}"

        response_data = await self._request_json(
            path="/paper/search",
            params=params,
            headers=headers,
        )

        raw_items = response_data.get("data")
        if not isinstance(raw_items, list):
            error_parts: list[str] = []
            error_value = response_data.get("error")
            if isinstance(error_value, str) and error_value.strip():
                error_parts.append(error_value.strip())

            message_value = response_data.get("message")
            if isinstance(message_value, str) and message_value.strip():
                error_parts.append(message_value.strip())

            if error_parts:
                joined = " | ".join(error_parts)
                raise SemanticScholarResponseError(
                    f"Semantic Scholar returned unexpected payload without data list: {joined}"
                )

            raise SemanticScholarResponseError("Semantic Scholar payload missing list field: data")

        papers: list[NormalizedPaper] = []
        for item_obj in cast(list[object], raw_items):
            if not isinstance(item_obj, dict):
                continue
            normalized = self._normalize_item(cast(dict[str, Any], item_obj))
            if normalized is not None:
                papers.append(normalized)
        return papers

    async def _request_json(
        self,
        *,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any]:
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
                    response = await client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise SemanticScholarResponseError(
                            "Semantic Scholar payload must be a JSON object"
                        )
                    return cast(dict[str, Any], payload)

        raise SemanticScholarResponseError("Semantic Scholar request failed")

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> NormalizedPaper | None:
        title = str(item.get("title") or "").strip()
        if not title:
            return None

        year_value = item.get("year")
        year: int | None = None
        if isinstance(year_value, int):
            year = year_value

        abstract_value = item.get("abstract")
        abstract = str(abstract_value).strip() if isinstance(abstract_value, str) else None

        url_value = item.get("url")
        url = str(url_value).strip() if isinstance(url_value, str) else None

        authors: list[str] = []
        raw_authors = item.get("authors")
        if isinstance(raw_authors, list):
            for author_obj in cast(list[object], raw_authors):
                if isinstance(author_obj, dict):
                    author = cast(dict[str, Any], author_obj)
                    name = author.get("name")
                    if isinstance(name, str) and name.strip():
                        authors.append(name.strip())

        doi: str | None = None
        arxiv_id: str | None = None
        external_ids = item.get("externalIds")
        if isinstance(external_ids, dict):
            external_ids_mapping = cast(dict[str, Any], external_ids)
            doi_value = external_ids_mapping.get("DOI")
            if isinstance(doi_value, str) and doi_value.strip():
                doi = doi_value.strip()
            arxiv_value = external_ids_mapping.get("ArXiv")
            if isinstance(arxiv_value, str) and arxiv_value.strip():
                arxiv_id = arxiv_value.strip()

        semantic_score = 0.0
        raw_score = item.get("score")
        if isinstance(raw_score, (int, float)):
            semantic_score = float(raw_score)

        citation_count = 0
        raw_citations = item.get("citationCount")
        if isinstance(raw_citations, int):
            citation_count = max(0, raw_citations)

        influential_citation_count = 0
        raw_influential = item.get("influentialCitationCount")
        if isinstance(raw_influential, int):
            influential_citation_count = max(0, raw_influential)

        open_access = bool(item.get("isOpenAccess") is True)

        return NormalizedPaper(
            title=title,
            year=year,
            doi=doi,
            arxiv_id=arxiv_id,
            abstract=abstract,
            authors=authors,
            url=url,
            source="semantic_scholar",
            semantic_score=semantic_score,
            citation_count=citation_count,
            influential_citation_count=influential_citation_count,
            open_access=open_access,
        )
