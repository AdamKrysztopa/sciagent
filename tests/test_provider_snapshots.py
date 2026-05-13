"""Provider snapshot tests - pin normalization behavior using monkeypatch."""

from __future__ import annotations

# ruff: noqa: PLR2004
from typing import Any

import httpx
import pytest

from agt.tools.arxiv_api import ArxivClient
from agt.tools.base_search import BaseSearchClient
from agt.tools.core_ac import CoreClient
from agt.tools.crossref import CrossrefClient
from agt.tools.dimensions import DimensionsClient
from agt.tools.europe_pmc import EuropePMCClient
from agt.tools.google_scholar import GoogleScholarClient
from agt.tools.openalex import OpenAlexClient
from agt.tools.opencitations import OpenCitationsClient
from agt.tools.pubmed import PubMedClient
from agt.tools.semantic_scholar import SemanticScholarClient


def _http_error(status: int) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError(
        f"HTTP {status}",
        request=httpx.Request("GET", "https://example.com"),
        response=httpx.Response(status),
    )


# ---------------------------------------------------------------------------
# XML / text fixtures
# ---------------------------------------------------------------------------

_ARXIV_ATOM_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>https://arxiv.org/abs/2001.00001</id>
    <title>Quantum Computing Fundamentals</title>
    <summary>An introduction to quantum computing.</summary>
    <published>2020-01-01T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
  </entry>
  <entry>
    <id>https://arxiv.org/abs/2021.00002</id>
    <title>Advanced Quantum Algorithms</title>
    <summary>Deep dive into quantum algorithms.</summary>
    <published>2021-03-15T00:00:00Z</published>
    <author><name>Bob Jones</name></author>
  </entry>
</feed>
"""

_ARXIV_EMPTY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
</feed>
"""

_BASE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>
  <result>
    <record>
      <title>Machine Learning Review</title>
      <year>2023</year>
      <doi>10.1234/ml.2023</doi>
      <description>An overview of machine learning methods.</description>
      <url>https://example.com/ml-review</url>
      <creator>Jane Doe</creator>
      <accessRights>open access</accessRights>
    </record>
    <record>
      <title>Deep Learning Applications</title>
      <year>2022</year>
      <doi>10.1234/dl.2022</doi>
      <description>Applications of deep learning.</description>
      <url>https://example.com/dl-apps</url>
      <creator>John Smith</creator>
      <accessRights>closed</accessRights>
    </record>
  </result>
</response>
"""

_BASE_EMPTY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>
  <result>
  </result>
</response>
"""

_PUBMED_ESEARCH_JSON = '{"esearchresult": {"idlist": ["12345678", "87654321"]}}'
_PUBMED_ESEARCH_EMPTY_JSON = '{"esearchresult": {"idlist": []}}'

_PUBMED_EFETCH_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <Title>Journal of Medicine</Title>
          <JournalIssue>
            <PubDate><Year>2023</Year></PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>Cancer Research Advances</ArticleTitle>
        <Abstract>
          <AbstractText>New advances in cancer research.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author ValidYN="Y">
            <LastName>Smith</LastName>
            <ForeName>John</ForeName>
          </Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">12345678</ArticleId>
        <ArticleId IdType="doi">10.1000/test.doi</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>87654321</PMID>
      <Article>
        <ArticleTitle>Another Medical Study</ArticleTitle>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">87654321</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


# ===========================================================================
# OpenAlexClient  (patches _request_json)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_openalex_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "results": [
                {
                    "title": "Quantum Gravity Theory",
                    "publication_year": 2022,
                    "doi": "https://doi.org/10.1234/qg",
                    "cited_by_count": 10,
                    "authorships": [{"author": {"display_name": "Alice"}}],
                },
                {
                    "title": "String Theory Review",
                    "publication_year": 2021,
                    "doi": "https://doi.org/10.1234/st",
                    "cited_by_count": 5,
                    "authorships": [],
                },
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake)
    papers = await client.search("quantum", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "Quantum Gravity Theory"
    assert papers[0].doi == "10.1234/qg"
    assert papers[0].year == 2022


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_openalex_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"results": []}

    monkeypatch.setattr(client, "_request_json", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_openalex_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("quantum", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_openalex_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAlexClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("quantum", limit=5)


# ===========================================================================
# CrossrefClient  (patches _request_json)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_crossref_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "message": {
                "items": [
                    {
                        "title": ["RAG in Practice"],
                        "published-print": {"date-parts": [[2024, 5, 1]]},
                        "DOI": "10.1234/rag",
                        "author": [{"given": "Ada", "family": "Lovelace"}],
                        "is-referenced-by-count": 12,
                    },
                    {
                        "title": ["Vector Databases Explained"],
                        "published-online": {"date-parts": [[2023, 1, 1]]},
                        "DOI": "10.1234/vdb",
                        "author": [{"given": "Alan", "family": "Turing"}],
                        "is-referenced-by-count": 7,
                    },
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake)
    papers = await client.search("rag", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "RAG in Practice"
    assert papers[0].doi == "10.1234/rag"
    assert papers[0].year == 2024


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_crossref_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"message": {"items": []}}

    monkeypatch.setattr(client, "_request_json", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_crossref_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("rag", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_crossref_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CrossrefClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("rag", limit=5)


# ===========================================================================
# ArxivClient  (patches _request_text)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_arxiv_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ArxivClient(timeout_seconds=5, retries=1)

    async def _fake(*, query: dict[str, str]) -> str:
        _ = query
        return _ARXIV_ATOM_XML

    monkeypatch.setattr(client, "_request_text", _fake)
    papers = await client.search("quantum", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "Quantum Computing Fundamentals"
    assert papers[0].year == 2020


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_arxiv_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ArxivClient(timeout_seconds=5, retries=1)

    async def _fake(*, query: dict[str, str]) -> str:
        _ = query
        return _ARXIV_EMPTY_XML

    monkeypatch.setattr(client, "_request_text", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_arxiv_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ArxivClient(timeout_seconds=5, retries=1)

    async def _fake(*, query: dict[str, str]) -> str:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_text", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("quantum", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_arxiv_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ArxivClient(timeout_seconds=5, retries=1)

    async def _fake(*, query: dict[str, str]) -> str:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_text", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("quantum", limit=5)


# ===========================================================================
# EuropePMCClient  (patches _request_json)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_europe_pmc_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuropePMCClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "resultList": {
                "result": [
                    {
                        "title": "COVID Vaccine Efficacy",
                        "pubYear": "2022",
                        "doi": "10.1234/cv",
                        "abstractText": "A study of vaccine efficacy.",
                        "authorString": "Smith J, Doe A",
                        "source": "MED",
                        "id": "34567890",
                        "isOpenAccess": "Y",
                        "citedByCount": 30,
                    },
                    {
                        "title": "Pandemic Preparedness Review",
                        "pubYear": "2021",
                        "doi": "10.1234/pp",
                        "authorString": "Jones B",
                        "source": "MED",
                        "id": "98765432",
                        "isOpenAccess": "N",
                        "citedByCount": 5,
                    },
                ]
            }
        }

    monkeypatch.setattr(client, "_request_json", _fake)
    papers = await client.search("covid", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "COVID Vaccine Efficacy"
    assert papers[0].doi == "10.1234/cv"
    assert papers[0].year == 2022


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_europe_pmc_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuropePMCClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"resultList": {"result": []}}

    monkeypatch.setattr(client, "_request_json", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_europe_pmc_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuropePMCClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("covid", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_europe_pmc_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuropePMCClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("covid", limit=5)


# ===========================================================================
# PubMedClient  (patches _request_text)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_pubmed_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PubMedClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> str:
        _ = params
        if "esearch" in path:
            return _PUBMED_ESEARCH_JSON
        return _PUBMED_EFETCH_XML

    monkeypatch.setattr(client, "_request_text", _fake)
    papers = await client.search("cancer", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "Cancer Research Advances"
    assert papers[0].year == 2023


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_pubmed_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PubMedClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> str:
        _ = path
        _ = params
        return _PUBMED_ESEARCH_EMPTY_JSON

    monkeypatch.setattr(client, "_request_text", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_pubmed_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PubMedClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> str:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_text", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("cancer", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_pubmed_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PubMedClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> str:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_text", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("cancer", limit=5)


# ===========================================================================
# BaseSearchClient  (patches _request_text)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_base_search_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BaseSearchClient(timeout_seconds=5, retries=1)

    async def _fake(*, params: dict[str, str]) -> str:
        _ = params
        return _BASE_XML

    monkeypatch.setattr(client, "_request_text", _fake)
    papers = await client.search("machine learning", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "Machine Learning Review"
    assert papers[0].year == 2023


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_base_search_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BaseSearchClient(timeout_seconds=5, retries=1)

    async def _fake(*, params: dict[str, str]) -> str:
        _ = params
        return _BASE_EMPTY_XML

    monkeypatch.setattr(client, "_request_text", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_base_search_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BaseSearchClient(timeout_seconds=5, retries=1)

    async def _fake(*, params: dict[str, str]) -> str:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_text", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("machine learning", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_base_search_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BaseSearchClient(timeout_seconds=5, retries=1)

    async def _fake(*, params: dict[str, str]) -> str:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_text", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("machine learning", limit=5)


# ===========================================================================
# SemanticScholarClient  (patches _request_json)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_semantic_scholar_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SemanticScholarClient(api_key=None, timeout_seconds=5, retries=1)

    async def _fake(
        *,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        _ = path
        _ = params
        _ = headers
        return {
            "data": [
                {
                    "title": "Neural Networks Survey",
                    "year": 2023,
                    "abstract": "A comprehensive survey.",
                    "url": "https://semanticscholar.org/paper/abc",
                    "isOpenAccess": True,
                    "authors": [{"name": "Alice"}],
                    "externalIds": {"DOI": "10.1234/nn"},
                    "citationCount": 20,
                    "influentialCitationCount": 4,
                    "venue": "Nature",
                    "publicationTypes": ["JournalArticle"],
                },
                {
                    "title": "Transformer Architectures",
                    "year": 2022,
                    "abstract": None,
                    "url": None,
                    "isOpenAccess": False,
                    "authors": [],
                    "externalIds": {},
                    "citationCount": 8,
                    "influentialCitationCount": 1,
                    "venue": None,
                    "publicationTypes": None,
                },
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake)
    papers = await client.search("neural networks", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "Neural Networks Survey"
    assert papers[0].doi == "10.1234/nn"
    assert papers[0].year == 2023


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_semantic_scholar_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SemanticScholarClient(api_key=None, timeout_seconds=5, retries=1)

    async def _fake(
        *,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        _ = path
        _ = params
        _ = headers
        return {"data": []}

    monkeypatch.setattr(client, "_request_json", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_semantic_scholar_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SemanticScholarClient(api_key=None, timeout_seconds=5, retries=1)

    async def _fake(
        *,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("neural networks", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_semantic_scholar_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SemanticScholarClient(api_key=None, timeout_seconds=5, retries=1)

    async def _fake(
        *,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("neural networks", limit=5)


# ===========================================================================
# OpenCitationsClient  (patches _request_json; citation_count, not search)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_opencitations_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str) -> object:
        _ = path
        return [{"count": "42"}]

    monkeypatch.setattr(client, "_request_json", _fake)
    result = await client.citation_count("10.1234/test")
    assert result == 42


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_opencitations_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str) -> object:
        _ = path
        return []

    monkeypatch.setattr(client, "_request_json", _fake)
    assert await client.citation_count("10.1234/test") is None


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_opencitations_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str) -> object:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.citation_count("10.1234/test")


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_opencitations_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCitationsClient(timeout_seconds=5, retries=1)

    async def _fake(*, path: str) -> object:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.citation_count("10.1234/test")


# ===========================================================================
# CoreClient  (patches _request_json; requires api_key)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_core_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CoreClient(api_key="test-key", timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {
            "results": [
                {
                    "title": "Open Access Research Methods",
                    "yearPublished": 2023,
                    "doi": "10.1234/oa",
                    "abstract": "Methods for open access research.",
                    "authors": [{"name": "Eva Brown"}],
                    "downloadUrl": "https://core.ac.uk/download/123.pdf",
                    "isOpenAccess": True,
                },
                {
                    "title": "Institutional Repositories Review",
                    "yearPublished": 2022,
                    "doi": "10.1234/ir",
                    "abstract": "A review of institutional repositories.",
                    "authors": [{"name": "Frank White"}],
                    "downloadUrl": "https://core.ac.uk/download/456.pdf",
                    "isOpenAccess": True,
                },
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake)
    papers = await client.search("open access", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "Open Access Research Methods"
    assert papers[0].doi == "10.1234/oa"
    assert papers[0].year == 2023


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_core_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CoreClient(api_key="test-key", timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        _ = path
        _ = params
        return {"results": []}

    monkeypatch.setattr(client, "_request_json", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_core_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CoreClient(api_key="test-key", timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("open access", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_core_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CoreClient(api_key="test-key", timeout_seconds=5, retries=1)

    async def _fake(*, path: str, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("open access", limit=5)


# ===========================================================================
# DimensionsClient  (patches _request_json; two-step auth+search)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_dimensions_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DimensionsClient(api_key="test-key", timeout_seconds=5, retries=1)

    async def _fake(
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        json_body: dict[str, object],
    ) -> dict[str, Any]:
        _ = method
        _ = headers
        _ = json_body
        if "/authenticate" in path:
            return {"token": "test-token"}
        return {
            "publications": [
                {
                    "title": "Climate Change Impact",
                    "year": 2023,
                    "doi": "10.1234/cc",
                    "times_cited": 25,
                    "open_access": True,
                    "authors": [{"raw_name": "Green, A."}],
                },
                {
                    "title": "Renewable Energy Trends",
                    "year": 2022,
                    "doi": "10.1234/re",
                    "times_cited": 10,
                    "open_access": False,
                    "authors": [{"raw_name": "Solar, B."}],
                },
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake)
    papers = await client.search("climate", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "Climate Change Impact"
    assert papers[0].doi == "10.1234/cc"
    assert papers[0].year == 2023


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_dimensions_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DimensionsClient(api_key="test-key", timeout_seconds=5, retries=1)

    async def _fake(
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        json_body: dict[str, object],
    ) -> dict[str, Any]:
        _ = method
        _ = headers
        _ = json_body
        if "/authenticate" in path:
            return {"token": "test-token"}
        return {"publications": []}

    monkeypatch.setattr(client, "_request_json", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_dimensions_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DimensionsClient(api_key="test-key", timeout_seconds=5, retries=1)

    async def _fake(
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        json_body: dict[str, object],
    ) -> dict[str, Any]:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("climate", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_dimensions_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DimensionsClient(api_key="test-key", timeout_seconds=5, retries=1)

    async def _fake(
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        json_body: dict[str, object],
    ) -> dict[str, Any]:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("climate", limit=5)


# ===========================================================================
# GoogleScholarClient  (patches _request_json; requires api_key)
# ===========================================================================


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_google_scholar_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GoogleScholarClient(api_key="test-serpapi-key", timeout_seconds=5, retries=1)

    async def _fake(*, params: dict[str, str]) -> dict[str, Any]:
        _ = params
        return {
            "organic_results": [
                {
                    "title": "Graph Neural Networks",
                    "snippet": "A survey of graph neural networks.",
                    "link": "https://scholar.google.com/paper1",
                    "publication_info": {
                        "summary": "Nature, 2023",
                        "authors": ["Alice Chen"],
                    },
                    "inline_links": {"cited_by": {"total": 50}},
                },
                {
                    "title": "Knowledge Graphs",
                    "snippet": "Introduction to knowledge graphs.",
                    "link": "https://scholar.google.com/paper2",
                    "publication_info": {
                        "summary": "Science, 2022",
                        "authors": ["Bob Lee"],
                    },
                    "inline_links": {"cited_by": {"total": 20}},
                },
            ]
        }

    monkeypatch.setattr(client, "_request_json", _fake)
    papers = await client.search("graph neural networks", limit=5)
    assert len(papers) == 2
    assert papers[0].title == "Graph Neural Networks"
    assert papers[0].year == 2023


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_google_scholar_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GoogleScholarClient(api_key="test-serpapi-key", timeout_seconds=5, retries=1)

    async def _fake(*, params: dict[str, str]) -> dict[str, Any]:
        _ = params
        return {"organic_results": []}

    monkeypatch.setattr(client, "_request_json", _fake)
    assert await client.search("nothing", limit=5) == []


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_google_scholar_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GoogleScholarClient(api_key="test-serpapi-key", timeout_seconds=5, retries=1)

    async def _fake(*, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(500)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("graphs", limit=5)


@pytest.mark.provider_snapshot
@pytest.mark.anyio
async def test_google_scholar_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GoogleScholarClient(api_key="test-serpapi-key", timeout_seconds=5, retries=1)

    async def _fake(*, params: dict[str, str]) -> dict[str, Any]:
        raise _http_error(429)

    monkeypatch.setattr(client, "_request_json", _fake)
    with pytest.raises(httpx.HTTPStatusError):
        await client.search("graphs", limit=5)
