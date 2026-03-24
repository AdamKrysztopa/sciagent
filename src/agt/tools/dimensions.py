"""Dimensions API wrapper returning NormalizedPaper models."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper


class DimensionsResponseError(RuntimeError):
    """Raised when Dimensions payload is malformed."""


class DimensionsClient:
    """Small bounded client for Dimensions DSL search."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://app.dimensions.ai/api",
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None

    async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
        if not query.strip():
            return []

        token = await self._authenticate()
        payload = await self._dsl_search(query=query, limit=limit, token=token)
        raw_items = payload.get("publications")
        if not isinstance(raw_items, list):
            raise DimensionsResponseError("Dimensions payload missing publications list")

        papers: list[NormalizedPaper] = []
        for item_obj in cast(list[object], raw_items):
            if not isinstance(item_obj, dict):
                continue
            item = cast(dict[str, Any], item_obj)
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            year = item.get("year") if isinstance(item.get("year"), int) else None
            doi = item.get("doi") if isinstance(item.get("doi"), str) else None
            if isinstance(doi, str):
                doi = doi.strip() or None
            citation_count = item.get("times_cited")
            if not isinstance(citation_count, int):
                citation_count = 0
            open_access = bool(item.get("open_access") is True)
            authors: list[str] = []
            raw_authors = item.get("authors")
            if isinstance(raw_authors, list):
                for author_obj in cast(list[object], raw_authors):
                    if isinstance(author_obj, dict):
                        name = author_obj.get("raw_name")
                        if isinstance(name, str) and name.strip():
                            authors.append(name.strip())
            papers.append(
                NormalizedPaper(
                    title=title,
                    year=year,
                    doi=doi,
                    abstract=None,
                    authors=authors,
                    url=None,
                    source="dimensions",
                    semantic_score=0.0,
                    citation_count=max(0, int(citation_count)),
                    open_access=open_access,
                )
            )
        return papers

    async def _authenticate(self) -> str:
        if self._token is not None:
            return self._token

        payload = await self._request_json(
            method="POST",
            path="/authenticate",
            headers={"Authorization": f"JWT {self._api_key}"},
            json_body={},
        )
        token = payload.get("token")
        if not isinstance(token, str) or not token.strip():
            raise DimensionsResponseError("Dimensions auth payload missing token")
        self._token = token.strip()
        return self._token

    async def _dsl_search(self, *, query: str, limit: int, token: str) -> dict[str, Any]:
        dsl = (
            'search publications in full_data for "'
            + query.replace('"', "")
            + f'" return publications[title+year+doi+times_cited+open_access+authors] limit {limit}'
        )
        return await self._request_json(
            method="POST",
            path="/dsl.json",
            headers={"Authorization": f"JWT {token}"},
            json_body={"query": dsl},
        )

    async def _request_json(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        json_body: dict[str, object],
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
                    response = await client.request(method, url, headers=headers, json=json_body)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise DimensionsResponseError("Dimensions payload must be JSON object")
                    return cast(dict[str, Any], payload)

        raise DimensionsResponseError("Dimensions request failed")
