"""CORE API v3 wrapper returning NormalizedPaper models."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper


class CoreResponseError(RuntimeError):
    """Raised when CORE response payload is malformed."""


class CoreClient:
    """Small bounded client for CORE works search."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://api.core.ac.uk/v3",
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
        if not query.strip():
            return []

        payload = await self._request_json(
            path="/search/works",
            params={"q": query, "limit": str(limit)},
        )

        raw_items = payload.get("results")
        if not isinstance(raw_items, list):
            raise CoreResponseError("CORE payload missing results list")

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
        headers = {"Authorization": f"Bearer {self._api_key}"}
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
                        raise CoreResponseError("CORE payload must be a JSON object")
                    return cast(dict[str, Any], payload)

        raise CoreResponseError("CORE request failed")

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> NormalizedPaper | None:
        title = str(item.get("title") or "").strip()
        if not title:
            return None

        year_value = item.get("yearPublished")
        year = year_value if isinstance(year_value, int) else None

        doi_value = item.get("doi")
        doi = doi_value.strip() if isinstance(doi_value, str) and doi_value.strip() else None

        abstract_value = item.get("abstract")
        abstract = (
            abstract_value.strip()
            if isinstance(abstract_value, str) and abstract_value.strip()
            else None
        )

        authors: list[str] = []
        raw_authors = item.get("authors")
        if isinstance(raw_authors, list):
            for author_obj in cast(list[object], raw_authors):
                if isinstance(author_obj, dict):
                    name = author_obj.get("name")
                    if isinstance(name, str) and name.strip():
                        authors.append(name.strip())

        download_url = item.get("downloadUrl")
        url = (
            download_url.strip() if isinstance(download_url, str) and download_url.strip() else None
        )

        open_access = bool(item.get("isOpenAccess") is True)

        return NormalizedPaper(
            title=title,
            year=year,
            doi=doi,
            abstract=abstract,
            authors=authors,
            url=url,
            source="core",
            semantic_score=0.0,
            citation_count=0,
            open_access=open_access,
        )
