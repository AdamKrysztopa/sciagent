"""OpenAlex API wrapper returning NormalizedPaper models."""

# ruff: noqa: PLR0912
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import re
from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import ItemType, NormalizedAuthor, NormalizedPaper

_OPENALEX_TYPE_MAP: dict[str, ItemType] = {
    "journal-article": "journal_article",
    "preprint": "preprint",
    "conference-paper": "conference_paper",
    "book-chapter": "book_chapter",
}


class OpenAlexResponseError(RuntimeError):
    """Raised when OpenAlex response payload is malformed."""


_OPENALEX_UA_BASE = "SciAgent/0.1 (https://github.com/AdamKrysztopa/sciagent)"


class OpenAlexClient:
    """Small bounded client for OpenAlex works search."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        retries: int,
        mailto: str | None = None,
        base_url: str = "https://api.openalex.org",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._mailto = mailto
        self._base_url = base_url.rstrip("/")

    def _user_agent(self) -> str:
        ua = _OPENALEX_UA_BASE
        if self._mailto:
            ua += f" mailto:{self._mailto}"
        return ua

    async def search(
        self,
        query: str,
        *,
        limit: int,
        year_min: int | None = None,
        author_ids: list[str] | None = None,
        max_pages: int = 1,
    ) -> list[NormalizedPaper]:
        """Search OpenAlex and return normalized papers."""

        if not query.strip():
            return []

        papers: list[NormalizedPaper] = []
        cursor = "*"
        for _ in range(max(1, max_pages)):
            params: dict[str, str] = {
                "search": query,
                "per-page": str(limit),
            }
            filter_parts: list[str] = []
            if year_min is not None:
                filter_parts.append(f"publication_year:>{year_min - 1}")
            if author_ids:
                filter_parts.append("author.id:" + "|".join(author_ids))
            if filter_parts:
                params["filter"] = ",".join(filter_parts)
            if max_pages > 1:
                params["cursor"] = cursor

            payload = await self._request_json(
                path="/works",
                params=params,
            )

            raw_items = payload.get("results")
            if not isinstance(raw_items, list):
                raise OpenAlexResponseError("OpenAlex payload missing list field: results")

            if not raw_items:
                break

            for item_obj in cast(list[object], raw_items):
                if not isinstance(item_obj, dict):
                    continue
                normalized = self._normalize_item(cast(dict[str, Any], item_obj))
                if normalized is not None:
                    papers.append(normalized)

            if max_pages == 1:
                break

            meta = payload.get("meta")
            next_cursor: str | None = None
            if isinstance(meta, dict):
                candidate = meta.get("next_cursor")
                if isinstance(candidate, str) and candidate.strip():
                    next_cursor = candidate
            if next_cursor is None:
                break
            cursor = next_cursor
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
                        raise RuntimeError("openalex rate limit (HTTP 429)")
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise OpenAlexResponseError("OpenAlex payload must be a JSON object")
                    return cast(dict[str, Any], payload)

        raise OpenAlexResponseError("OpenAlex request failed")

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> NormalizedPaper | None:  # noqa: PLR0915
        title = re.sub(r"<[^>]+>", "", str(item.get("title") or "")).strip()
        if not title:
            return None

        year_value = item.get("publication_year")
        year = year_value if isinstance(year_value, int) else None

        doi = OpenAlexClient._extract_doi(item)

        abstract = OpenAlexClient._extract_abstract(item)

        authors: list[NormalizedAuthor] = []
        authorships = item.get("authorships")
        if isinstance(authorships, list):
            for authorship_obj in cast(list[object], authorships):
                if not isinstance(authorship_obj, dict):
                    continue
                authorship = cast(dict[str, Any], authorship_obj)
                author_data = authorship.get("author")
                if isinstance(author_data, dict):
                    author = cast(dict[str, Any], author_data)
                    display_name = author.get("display_name")
                    if isinstance(display_name, str) and display_name.strip():
                        raw_orcid = author.get("orcid")
                        orcid: str | None = None
                        if isinstance(raw_orcid, str) and raw_orcid.strip():
                            orcid = raw_orcid.strip().replace("https://orcid.org/", "")
                        raw_oa_id = author.get("id")
                        openalex_id: str | None = None
                        if isinstance(raw_oa_id, str) and raw_oa_id.strip():
                            openalex_id = raw_oa_id.strip()
                        authors.append(
                            NormalizedAuthor(
                                name=display_name.strip(),
                                orcid=orcid,
                                openalex_id=openalex_id,
                                source="openalex",
                            )
                        )

        url = None
        primary_location = item.get("primary_location")
        if isinstance(primary_location, dict):
            location = cast(dict[str, Any], primary_location)
            landing = location.get("landing_page_url")
            if isinstance(landing, str) and landing.strip():
                url = landing.strip()

        open_access = False
        pdf_url: str | None = None
        open_access_data = item.get("open_access")
        if isinstance(open_access_data, dict):
            open_access_mapping = cast(dict[str, Any], open_access_data)
            open_access = bool(open_access_mapping.get("is_oa") is True)
            oa_url = open_access_mapping.get("oa_url")
            if isinstance(oa_url, str) and oa_url.strip():
                pdf_url = oa_url.strip()

        if pdf_url is None and isinstance(primary_location, dict):
            loc_pdf = cast(dict[str, Any], primary_location).get("pdf_url")
            if isinstance(loc_pdf, str) and loc_pdf.strip():
                pdf_url = loc_pdf.strip()

        if pdf_url is None:
            best_oa = item.get("best_oa_location")
            if isinstance(best_oa, dict):
                best_oa_pdf = cast(dict[str, Any], best_oa).get("pdf_url")
                if isinstance(best_oa_pdf, str) and best_oa_pdf.strip():
                    pdf_url = best_oa_pdf.strip()

        if pdf_url is None:
            for loc_obj in cast(list[object], item.get("locations") or []):
                if not isinstance(loc_obj, dict):
                    continue
                loc_pdf = cast(dict[str, Any], loc_obj).get("pdf_url")
                if isinstance(loc_pdf, str) and loc_pdf.strip():
                    pdf_url = loc_pdf.strip()
                    break

        semantic_score = 0.0
        relevance_value = item.get("relevance_score")
        if isinstance(relevance_value, (int, float)):
            semantic_score = float(relevance_value)

        citation_count = OpenAlexClient._extract_citation_count(item)

        venue: str | None = None
        if isinstance(primary_location, dict):
            source_data = cast(dict[str, Any], primary_location).get("source")
            if isinstance(source_data, dict):
                dn = cast(dict[str, Any], source_data).get("display_name")
                if isinstance(dn, str) and dn.strip():
                    venue = dn.strip()

        item_type: ItemType | None = _OPENALEX_TYPE_MAP.get(str(item.get("type") or ""))

        volume: str | None = None
        issue: str | None = None
        pages: str | None = None
        biblio = item.get("biblio")
        if isinstance(biblio, dict):
            bib = cast(dict[str, Any], biblio)
            vol_val = bib.get("volume")
            if isinstance(vol_val, str) and vol_val.strip():
                volume = vol_val.strip()
            iss_val = bib.get("issue")
            if isinstance(iss_val, str) and iss_val.strip():
                issue = iss_val.strip()
            first_page = bib.get("first_page")
            last_page = bib.get("last_page")
            if isinstance(first_page, str) and first_page.strip():
                pages = first_page.strip()
                if isinstance(last_page, str) and last_page.strip():
                    pages = f"{first_page.strip()}-{last_page.strip()}"

        return NormalizedPaper(
            title=title,
            year=year,
            doi=doi,
            abstract=abstract,
            authors=authors,
            url=url,
            pdf_url=pdf_url,
            source="openalex",
            semantic_score=semantic_score,
            citation_count=citation_count,
            open_access=open_access,
            venue=venue,
            item_type=item_type,
            volume=volume,
            issue=issue,
            pages=pages,
        )

    @staticmethod
    def _extract_abstract(item: dict[str, Any]) -> str | None:
        abstract_index = item.get("abstract_inverted_index")
        if not isinstance(abstract_index, dict):
            return None

        terms_by_position: dict[int, str] = {}
        for raw_term, raw_positions in abstract_index.items():
            if not isinstance(raw_term, str) or not isinstance(raw_positions, list):
                continue
            for raw_position in cast(list[object], raw_positions):
                if not isinstance(raw_position, int) or raw_position < 0:
                    continue
                if raw_position not in terms_by_position:
                    terms_by_position[raw_position] = raw_term

        if not terms_by_position:
            return None

        ordered_terms = [term for _, term in sorted(terms_by_position.items())]
        return " ".join(ordered_terms).strip() or None

    @staticmethod
    def _extract_doi(item: dict[str, Any]) -> str | None:
        doi_value = item.get("doi")
        if not isinstance(doi_value, str) or not doi_value.strip():
            return None

        normalized_doi = doi_value.strip()
        prefix = "https://doi.org/"
        if normalized_doi.lower().startswith(prefix):
            normalized_doi = normalized_doi[len(prefix) :]
        return normalized_doi

    @staticmethod
    def _extract_citation_count(item: dict[str, Any]) -> int:
        cited_by_value = item.get("cited_by_count")
        if isinstance(cited_by_value, int):
            return max(0, cited_by_value)
        return 0
