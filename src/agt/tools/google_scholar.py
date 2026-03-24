"""Google Scholar retrieval via SerpAPI (optional/experimental)."""

# ruff: noqa: PLR0912, PLR2004
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper


class GoogleScholarResponseError(RuntimeError):
    """Raised when SerpAPI payload is malformed."""


class GoogleScholarClient:
    """Small bounded SerpAPI client for scholar search."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://serpapi.com/search.json",
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url

    async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
        if not query.strip():
            return []

        payload = await self._request_json(
            params={
                "engine": "google_scholar",
                "q": query,
                "num": str(limit),
                "api_key": self._api_key,
            }
        )

        raw_results = payload.get("organic_results")
        if not isinstance(raw_results, list):
            raise GoogleScholarResponseError("SerpAPI payload missing organic_results list")

        papers: list[NormalizedPaper] = []
        for item_obj in cast(list[object], raw_results):
            if not isinstance(item_obj, dict):
                continue
            item = cast(dict[str, Any], item_obj)
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            year = None
            pub_info = item.get("publication_info")
            if isinstance(pub_info, dict):
                summary = pub_info.get("summary")
                if isinstance(summary, str):
                    for token in summary.split():
                        if len(token) == 4 and token.isdigit():
                            year = int(token)
                            break
            citation_count = 0
            inline_links = item.get("inline_links")
            if isinstance(inline_links, dict):
                cited = inline_links.get("cited_by")
                if isinstance(cited, dict):
                    total = cited.get("total")
                    if isinstance(total, int):
                        citation_count = max(0, total)
            snippet = item.get("snippet")
            abstract = snippet.strip() if isinstance(snippet, str) and snippet.strip() else None
            link = item.get("link")
            url = link.strip() if isinstance(link, str) and link.strip() else None
            authors: list[str] = []
            if isinstance(pub_info, dict):
                raw_authors = pub_info.get("authors")
                if isinstance(raw_authors, list):
                    authors = [str(a).strip() for a in raw_authors if str(a).strip()]
            papers.append(
                NormalizedPaper(
                    title=title,
                    year=year,
                    abstract=abstract,
                    authors=authors,
                    url=url,
                    source="google_scholar",
                    semantic_score=0.0,
                    citation_count=citation_count,
                    open_access=False,
                )
            )
        return papers

    async def _request_json(self, *, params: dict[str, str]) -> dict[str, Any]:
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
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise GoogleScholarResponseError("SerpAPI payload must be JSON object")
                    return cast(dict[str, Any], payload)

        raise GoogleScholarResponseError("SerpAPI request failed")
