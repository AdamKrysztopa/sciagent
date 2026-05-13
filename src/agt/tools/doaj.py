"""DOAJ v3 API wrapper returning NormalizedPaper models."""

from __future__ import annotations

from typing import cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedAuthor, NormalizedPaper
from agt.tools.capabilities import DOAJ_CAPS
from agt.tools.provider_base import SearchProviderBase

_DOAJ_API_BASE = "https://doaj.org/api/v3"


class DOAJResponseError(RuntimeError):
    """Raised when DOAJ response payload is malformed."""


class DOAJClient(SearchProviderBase):
    """DOAJ v3 API wrapper returning NormalizedPaper models.

    All results from DOAJ are open access by definition.
    API: GET https://doaj.org/api/v3/search/articles/{query}?pageSize=N
    """

    capabilities_ = DOAJ_CAPS

    def __init__(
        self,
        *,
        mailto: str | None = None,
        timeout: float = 15.0,
        base_url: str = _DOAJ_API_BASE,
    ) -> None:
        super().__init__(mailto=mailto, timeout=timeout)
        self._base_url = base_url.rstrip("/")

    async def _search_impl(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]:
        if not query.strip():
            return []

        url = f"{self._base_url}/search/articles/{query}"
        params: dict[str, str] = {"pageSize": str(min(limit, 100))}

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            )),
            reraise=True,
        ):
            with attempt:
                response = await self._client.get(url, params=params)
                if response.status_code == 429:  # noqa: PLR2004
                    raise RuntimeError("doaj rate limit (HTTP 429)")
                response.raise_for_status()
                payload_obj: object = response.json()
                if not isinstance(payload_obj, dict):
                    raise DOAJResponseError("DOAJ payload must be a JSON object")
                payload_dict = cast(dict[str, object], payload_obj)

                raw_results = payload_dict.get("results")
                if raw_results is None:
                    return []
                if not isinstance(raw_results, list):
                    raise DOAJResponseError("DOAJ payload missing list field: results")

                papers: list[NormalizedPaper] = []
                for item_obj in cast(list[object], raw_results):
                    if not isinstance(item_obj, dict):
                        continue
                    paper = self._normalize_item(cast(dict[str, object], item_obj))
                    if paper is not None:
                        papers.append(paper)
                return papers

        raise DOAJResponseError("DOAJ request failed after retries")

    @staticmethod
    def _normalize_item(item: dict[str, object]) -> NormalizedPaper | None:  # noqa: PLR0912, PLR0915
        bibjson_raw = item.get("bibjson")
        if not isinstance(bibjson_raw, dict):
            return None
        bibjson = cast(dict[str, object], bibjson_raw)

        title_raw = bibjson.get("title")
        title = title_raw.strip() if isinstance(title_raw, str) else ""
        if not title:
            return None

        abstract_raw = bibjson.get("abstract")
        abstract = (
            abstract_raw.strip() if isinstance(abstract_raw, str) and abstract_raw.strip() else None
        )

        authors: list[NormalizedAuthor] = []
        author_list = bibjson.get("author")
        if isinstance(author_list, list):
            for author_obj in cast(list[object], author_list):
                if isinstance(author_obj, dict):
                    author = cast(dict[str, object], author_obj)
                    name_raw = author.get("name")
                    if isinstance(name_raw, str) and name_raw.strip():
                        authors.append(NormalizedAuthor(name=name_raw.strip(), source="doaj"))

        year: int | None = None
        year_raw = bibjson.get("year")
        if isinstance(year_raw, str) and year_raw.isdigit():
            year = int(year_raw)
        elif isinstance(year_raw, int):
            year = year_raw

        doi: str | None = None
        identifier_list = bibjson.get("identifier")
        if isinstance(identifier_list, list):
            for id_obj in cast(list[object], identifier_list):
                if isinstance(id_obj, dict):
                    id_item = cast(dict[str, object], id_obj)
                    id_type = id_item.get("type")
                    if id_type == "doi":
                        id_val = id_item.get("id")
                        if isinstance(id_val, str) and id_val.strip():
                            doi = id_val.strip()
                            break

        journal_raw = bibjson.get("journal")
        venue: str | None = None
        if isinstance(journal_raw, dict):
            journal = cast(dict[str, object], journal_raw)
            title_val = journal.get("title")
            if isinstance(title_val, str) and title_val.strip():
                venue = title_val.strip()

        url: str | None = None
        link_list = item.get("link")
        if isinstance(link_list, list):
            for link_obj in cast(list[object], link_list):
                if isinstance(link_obj, dict):
                    link = cast(dict[str, object], link_obj)
                    link_type = link.get("type")
                    if link_type == "fulltext":
                        url_val = link.get("url")
                        if isinstance(url_val, str) and url_val.strip():
                            url = url_val.strip()
                            break

        return NormalizedPaper(
            title=title,
            year=year,
            doi=doi,
            abstract=abstract,
            authors=authors,
            url=url,
            source="doaj",
            semantic_score=0.0,
            citation_count=0,
            open_access=True,
            venue=venue,
        )
