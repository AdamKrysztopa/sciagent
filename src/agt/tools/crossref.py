"""Crossref API wrapper returning NormalizedPaper models."""

from __future__ import annotations

from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import ItemType, NormalizedAuthor, NormalizedPaper

_CROSSREF_TYPE_MAP: dict[str, ItemType] = {
    "journal-article": "journal_article",
    "proceedings-article": "conference_paper",
    "book-chapter": "book_chapter",
    "posted-content": "preprint",
}


class CrossrefResponseError(RuntimeError):
    """Raised when Crossref response payload is malformed."""


_CROSSREF_UA_BASE = "SciAgent/0.1 (https://github.com/AdamKrysztopa/sciagent)"


class CrossrefClient:
    """Small bounded client for Crossref works search."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        retries: int,
        mailto: str | None = None,
        base_url: str = "https://api.crossref.org",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._mailto = mailto
        self._base_url = base_url.rstrip("/")

    def _user_agent(self) -> str:
        ua = _CROSSREF_UA_BASE
        if self._mailto:
            ua += f" mailto:{self._mailto}"
        return ua

    async def search(
        self,
        query: str,
        *,
        limit: int,
        author_names: list[str] | None = None,
        max_pages: int = 1,
    ) -> list[NormalizedPaper]:
        """Search Crossref and return normalized papers."""

        if not query.strip():
            return []

        papers: list[NormalizedPaper] = []
        for page_idx in range(max(1, max_pages)):
            params: dict[str, str] = {
                "query.bibliographic": query,
                "rows": str(limit),
                "offset": str(page_idx * limit),
            }
            if author_names:
                params["query.author"] = " ".join(author_names)
            payload = await self._request_json(
                path="/works",
                params=params,
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
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds,
                    headers={"User-Agent": self._user_agent()},
                ) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 429:  # noqa: PLR2004
                        raise RuntimeError("crossref rate limit (HTTP 429)")
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
    def _extract_authors(item: dict[str, Any]) -> list[NormalizedAuthor]:
        authors: list[NormalizedAuthor] = []
        author_list = item.get("author")
        if not isinstance(author_list, list):
            return authors

        for author_obj in cast(list[object], author_list):
            if not isinstance(author_obj, dict):
                continue
            author = cast(dict[str, Any], author_obj)
            given_raw = author.get("given")
            family_raw = author.get("family")
            given = given_raw.strip() if isinstance(given_raw, str) and given_raw.strip() else None
            family = (
                family_raw.strip() if isinstance(family_raw, str) and family_raw.strip() else None
            )
            name_parts: list[str] = []
            if given:
                name_parts.append(given)
            if family:
                name_parts.append(family)
            if name_parts:
                authors.append(
                    NormalizedAuthor(
                        name=" ".join(name_parts),
                        family=family,
                        given=given,
                        source="crossref",
                    )
                )

        return authors

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> NormalizedPaper | None:  # noqa: PLR0912, PLR0915
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

        pdf_url: str | None = None
        link_raw = item.get("link")
        if isinstance(link_raw, list):
            best: str | None = None
            vor: str | None = None
            for link_obj in cast(list[object], link_raw):
                if not isinstance(link_obj, dict):
                    continue
                link = cast(dict[str, Any], link_obj)
                if link.get("content-type") != "application/pdf":
                    continue
                link_url = link.get("URL")
                if not isinstance(link_url, str) or not link_url.strip():
                    continue
                if best is None:
                    best = link_url.strip()
                if link.get("content-version") in ("vor", "am") and vor is None:
                    vor = link_url.strip()
            pdf_url = vor or best

        open_access = False
        license_raw = item.get("license")
        if isinstance(license_raw, list):
            for lic_obj in cast(list[object], license_raw):
                if not isinstance(lic_obj, dict):
                    continue
                lic_url = cast(dict[str, Any], lic_obj).get("URL")
                if isinstance(lic_url, str) and "creativecommons.org" in lic_url.lower():
                    open_access = True
                    break

        venue: str | None = None
        container_title = item.get("container-title")
        if isinstance(container_title, list) and container_title:
            first_ct = cast(object, container_title[0])
            if isinstance(first_ct, str) and first_ct.strip():
                venue = first_ct.strip()

        item_type: ItemType | None = _CROSSREF_TYPE_MAP.get(str(item.get("type") or ""))

        volume: str | None = None
        vol_val = item.get("volume")
        if isinstance(vol_val, str) and vol_val.strip():
            volume = vol_val.strip()

        issue: str | None = None
        iss_val = item.get("issue")
        if isinstance(iss_val, str) and iss_val.strip():
            issue = iss_val.strip()

        pages: str | None = None
        page_val = item.get("page")
        if isinstance(page_val, str) and page_val.strip():
            pages = page_val.strip()

        return NormalizedPaper(
            title=title,
            year=year,
            doi=doi,
            abstract=None,
            authors=authors,
            url=url,
            pdf_url=pdf_url,
            source="crossref",
            semantic_score=0.0,
            citation_count=citation_count,
            open_access=open_access,
            venue=venue,
            item_type=item_type,
            volume=volume,
            issue=issue,
            pages=pages,
        )
