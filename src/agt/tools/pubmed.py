"""PubMed E-Utilities wrapper returning NormalizedPaper models."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, cast

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from agt.models import NormalizedPaper

_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


class PubMedResponseError(RuntimeError):
    """Raised when PubMed response payload is malformed."""


class PubMedClient:
    """Bounded PubMed client using E-Utilities esearch + efetch."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        retries: int,
        api_key: str | None = None,
        base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str, *, limit: int) -> list[NormalizedPaper]:
        """Search PubMed and return normalized papers."""

        if not query.strip():
            return []

        ids = await self._esearch(query=query, limit=limit)
        if not ids:
            return []

        root = await self._efetch(ids=ids)
        papers: list[NormalizedPaper] = []
        for article in root.findall(".//PubmedArticle"):
            normalized = self._normalize_article(article)
            if normalized is not None:
                papers.append(normalized)
        return papers

    async def _esearch(self, *, query: str, limit: int) -> list[str]:
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": str(limit),
        }
        if self._api_key:
            params["api_key"] = self._api_key

        payload = await self._request_json(path="/esearch.fcgi", params=params)
        esearch_result = payload.get("esearchresult")
        if not isinstance(esearch_result, dict):
            raise PubMedResponseError("PubMed payload missing esearchresult object")
        esearch_mapping = cast(dict[str, object], esearch_result)

        raw_ids = esearch_mapping.get("idlist")
        if not isinstance(raw_ids, list):
            raise PubMedResponseError("PubMed payload missing esearchresult.idlist")

        ids: list[str] = []
        for raw in cast(list[object], raw_ids):
            if isinstance(raw, str) and raw.strip():
                ids.append(raw.strip())
        return ids

    async def _efetch(self, *, ids: list[str]) -> ET.Element:
        params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        }
        if self._api_key:
            params["api_key"] = self._api_key

        payload = await self._request_text(path="/efetch.fcgi", params=params)
        try:
            return ET.fromstring(payload)
        except ET.ParseError as exc:
            raise PubMedResponseError("PubMed efetch XML parse failed") from exc

    async def _request_json(self, *, path: str, params: dict[str, str]) -> dict[str, Any]:
        text = await self._request_text(path=path, params=params)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PubMedResponseError("PubMed payload must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise PubMedResponseError("PubMed payload must be a JSON object")
        return cast(dict[str, Any], payload)

    async def _request_text(self, *, path: str, params: dict[str, str]) -> str:
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
                    return response.text

        raise PubMedResponseError("PubMed request failed")

    @staticmethod
    def _normalize_article(article: ET.Element) -> NormalizedPaper | None:
        title = " ".join(article.findtext(".//ArticleTitle", default="").split())
        if not title:
            return None

        pmid = article.findtext(".//MedlineCitation/PMID")
        if pmid is not None:
            pmid = pmid.strip() or None

        year = PubMedClient._extract_year(article)
        abstract = PubMedClient._extract_abstract(article)
        authors = PubMedClient._extract_authors(article)
        doi = PubMedClient._extract_doi(article)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None

        return NormalizedPaper(
            title=title,
            year=year,
            doi=doi,
            abstract=abstract,
            authors=authors,
            url=url,
            source="pubmed",
            semantic_score=0.0,
            citation_count=0,
            open_access=False,
        )

    @staticmethod
    def _extract_year(article: ET.Element) -> int | None:
        year_text = article.findtext(".//PubDate/Year")
        if isinstance(year_text, str) and year_text.isdigit():
            return int(year_text)
        medline_date = article.findtext(".//PubDate/MedlineDate", default="")
        match = _YEAR_RE.search(medline_date)
        if match:
            return int(match.group(0))
        return None

    @staticmethod
    def _extract_abstract(article: ET.Element) -> str | None:
        abstract_nodes = article.findall(".//Abstract/AbstractText")
        chunks: list[str] = []
        for node in abstract_nodes:
            text = "".join(node.itertext()).strip()
            if text:
                chunks.append(text)
        if not chunks:
            return None
        return " ".join(chunks)

    @staticmethod
    def _extract_authors(article: ET.Element) -> list[str]:
        authors: list[str] = []
        for node in article.findall(".//AuthorList/Author"):
            fore = (node.findtext("ForeName") or "").strip()
            last = (node.findtext("LastName") or "").strip()
            collective = (node.findtext("CollectiveName") or "").strip()
            if fore or last:
                authors.append(" ".join(part for part in (fore, last) if part))
            elif collective:
                authors.append(collective)
        return authors

    @staticmethod
    def _extract_doi(article: ET.Element) -> str | None:
        for node in article.findall(".//ArticleIdList/ArticleId"):
            if node.attrib.get("IdType", "").lower() == "doi":
                text = "".join(node.itertext()).strip()
                if text:
                    return text
        return None
