from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from agt.tools.pubmed import PubMedClient, PubMedResponseError

_EXPECTED_YEAR_2024 = 2024


@pytest.mark.anyio
async def test_pubmed_search_normalizes_results(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PubMedClient(timeout_seconds=5, retries=1)

    async def _fake_esearch(*, query: str, limit: int) -> list[str]:
        _ = query
        _ = limit
        return ["12345"]

    async def _fake_efetch(*, ids: list[str]) -> ET.Element:
        _ = ids
        return ET.fromstring(
            """
            <PubmedArticleSet>
              <PubmedArticle>
                <MedlineCitation>
                  <PMID>12345</PMID>
                  <Article>
                    <ArticleTitle>Sports Nutrition Review</ArticleTitle>
                    <Abstract>
                      <AbstractText>Useful summary.</AbstractText>
                    </Abstract>
                    <AuthorList>
                      <Author><ForeName>Ada</ForeName><LastName>Lovelace</LastName></Author>
                    </AuthorList>
                    <Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal>
                  </Article>
                </MedlineCitation>
                <PubmedData>
                  <ArticleIdList>
                    <ArticleId IdType="doi">10.1/abc</ArticleId>
                  </ArticleIdList>
                </PubmedData>
              </PubmedArticle>
            </PubmedArticleSet>
            """
        )

    monkeypatch.setattr(client, "_esearch", _fake_esearch)
    monkeypatch.setattr(client, "_efetch", _fake_efetch)

    papers = await client.search("sport nutrition", limit=5)
    assert len(papers) == 1
    assert papers[0].title == "Sports Nutrition Review"
    assert papers[0].year == _EXPECTED_YEAR_2024
    assert papers[0].doi == "10.1/abc"
    assert papers[0].authors == ["Ada Lovelace"]
    assert papers[0].url == "https://pubmed.ncbi.nlm.nih.gov/12345/"


@pytest.mark.anyio
async def test_pubmed_search_handles_missing_optional_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = PubMedClient(timeout_seconds=5, retries=1)

    async def _fake_esearch(*, query: str, limit: int) -> list[str]:
        _ = query
        _ = limit
        return ["12345"]

    async def _fake_efetch(*, ids: list[str]) -> ET.Element:
        _ = ids
        return ET.fromstring(
            """
            <PubmedArticleSet>
              <PubmedArticle>
                <MedlineCitation>
                  <PMID>12345</PMID>
                  <Article>
                    <ArticleTitle>Minimal Record</ArticleTitle>
                  </Article>
                </MedlineCitation>
              </PubmedArticle>
            </PubmedArticleSet>
            """
        )

    monkeypatch.setattr(client, "_esearch", _fake_esearch)
    monkeypatch.setattr(client, "_efetch", _fake_efetch)

    papers = await client.search("x", limit=3)
    assert len(papers) == 1
    assert papers[0].abstract is None
    assert papers[0].authors == []
    assert papers[0].year is None


@pytest.mark.anyio
async def test_pubmed_search_returns_empty_when_no_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    client = PubMedClient(timeout_seconds=5, retries=1)

    async def _fake_esearch(*, query: str, limit: int) -> list[str]:
        _ = query
        _ = limit
        return []

    monkeypatch.setattr(client, "_esearch", _fake_esearch)

    papers = await client.search("x", limit=3)
    assert papers == []


@pytest.mark.anyio
async def test_pubmed_search_raises_on_malformed_esearch_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = PubMedClient(timeout_seconds=5, retries=1)

    async def _fake_request_text(*, path: str, params: dict[str, str]) -> str:
        _ = path
        _ = params
        return "{}"

    monkeypatch.setattr(client, "_request_text", _fake_request_text)

    with pytest.raises(PubMedResponseError):
        await client.search("x", limit=3)
