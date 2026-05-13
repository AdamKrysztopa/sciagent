from __future__ import annotations

from typing import Any

import httpx
import pytest

from agt.config import Settings
from agt.models import NormalizedAuthor, NormalizedPaper
from agt.tools.zotero_upsert import (
    map_item_type,
    map_paper_to_item,
    split_creator_name,
    upsert_papers,
)

EXPECTED_VALIDATION_FAILURES = 2


def _settings() -> Settings:
    return Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_ZOTERO_LIBRARY_TYPE": "user",
    })


def _paper(
    *,
    title: str = "Paper A",
    doi: str | None = "10.1000/example",
    authors: list[str] | None = None,
) -> NormalizedPaper:
    author_names = authors if authors is not None else ["Ada Lovelace"]
    return NormalizedPaper(
        title=title,
        doi=doi,
        authors=[NormalizedAuthor(name=a) for a in author_names],
        year=2024,
        source="semantic_scholar",
    )


def _match(path: str, expected: str) -> bool:
    return path == expected


@pytest.mark.anyio
async def test_collection_resolver_reuses_canonical_name_with_parent() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {"key": "PARENT1", "data": {"name": "Parent Folder", "parentCollection": None}},
                    {"key": "CHILD1", "data": {"name": "My Inbox", "parentCollection": "PARENT1"}},
                ],
            )
        if (
            _match(request.url.path, "/users/12345/collections/CHILD1/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="  my   inbox  ",
        papers=[],
        settings=_settings(),
        parent_collection_name="parent folder",
        client=client,
    )
    await client.aclose()

    assert result.collection.key == "CHILD1"
    assert result.collection.reused is True
    assert result.collection.parent_key == "PARENT1"
    assert all(call != "POST /users/12345/collections" for call in calls)


@pytest.mark.anyio
async def test_mapper_and_validation_fail_before_write_call() -> None:
    posted_items = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posted_items
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=[])
        if _match(request.url.path, "/users/12345/items") and request.method == "POST":
            posted_items += 1
            return httpx.Response(200, json={"successful": {"0": {"key": "I1"}}})
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="Inbox",
        papers=[
            _paper(title="", doi="10.1000/bad-title"),
            _paper(title="Missing Authors", doi="10.1000/no-authors", authors=[]),
        ],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert posted_items == 0
    assert result.failed == EXPECTED_VALIDATION_FAILURES
    assert result.created == 0
    assert result.outcomes[0].reason == "Missing title"
    assert result.outcomes[1].reason == "Missing authors"


@pytest.mark.anyio
async def test_idempotent_upsert_rerun_uses_doi_dedup() -> None:
    existing_items: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=existing_items)
        if _match(request.url.path, "/users/12345/items") and request.method == "POST":
            payload = request.read().decode("utf-8")
            if "10.1000/example" in payload:
                existing_items.append({
                    "key": "I1",
                    "data": {
                        "title": "Paper A",
                        "DOI": "10.1000/example",
                        "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
                    },
                })
                return httpx.Response(200, json={"successful": {"0": {"key": "I1"}}})
            return httpx.Response(400, json={"failed": {"0": {"message": "bad payload"}}})
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    first = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper()],
        settings=_settings(),
        client=client,
    )
    second = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper()],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert first.created == 1
    assert first.unchanged == 0
    assert second.created == 0
    assert second.unchanged == 1
    assert second.outcomes[0].duplicate_strategy == "doi"


@pytest.mark.anyio
async def test_idempotent_upsert_uses_title_author_hash_without_doi() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(
                200,
                json=[
                    {
                        "key": "I2",
                        "data": {
                            "title": "Paper Without DOI",
                            "DOI": "",
                            "creators": [{"firstName": "Grace", "lastName": "Hopper"}],
                        },
                    }
                ],
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper(title="Paper Without DOI", doi=None, authors=["Grace Hopper"])],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert result.created == 0
    assert result.unchanged == 1
    assert result.outcomes[0].duplicate_strategy == "title_author_hash"


@pytest.mark.anyio
async def test_create_response_partial_failure_is_reported() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=[])
        if _match(request.url.path, "/users/12345/items") and request.method == "POST":
            return httpx.Response(
                200, json={"successful": {}, "failed": {"0": {"message": "invalid date"}}}
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper()],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert result.created == 0
    assert result.failed == 1
    assert result.outcomes[0].reason == "invalid date"
    assert result.outcomes[0].retry_safe is False


@pytest.mark.anyio
async def test_retry_safe_failures_tracked_for_transient_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if _match(request.url.path, "/users/12345/collections") and request.method == "GET":
            return httpx.Response(200, json=[{"key": "INBOX", "data": {"name": "Inbox"}}])
        if (
            _match(request.url.path, "/users/12345/collections/INBOX/items/top")
            and request.method == "GET"
        ):
            return httpx.Response(200, json=[])
        if _match(request.url.path, "/users/12345/items") and request.method == "POST":
            return httpx.Response(503, text="service unavailable")
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://api.zotero.org", transport=httpx.MockTransport(handler)
    )
    result = await upsert_papers(
        collection_name="Inbox",
        papers=[_paper()],
        settings=_settings(),
        client=client,
    )
    await client.aclose()

    assert result.failed == 1
    assert result.retry_safe_failures == 1
    assert result.outcomes[0].retry_safe is True


# ---------------------------------------------------------------------------
# split_creator_name
# ---------------------------------------------------------------------------


def testsplit_creator_name_first_last() -> None:
    first, last = split_creator_name("Ada Lovelace")
    assert first == "Ada"
    assert last == "Lovelace"


def testsplit_creator_name_comma_format() -> None:
    first, last = split_creator_name("Lovelace, Ada")
    assert first == "Ada"
    assert last == "Lovelace"


def testsplit_creator_name_initials() -> None:
    first, last = split_creator_name("J. R. R. Tolkien")
    assert first == "J. R. R."
    assert last == "Tolkien"


def testsplit_creator_name_single_word() -> None:
    first, last = split_creator_name("Madonna")
    assert first == ""
    assert last == "Madonna"


def testsplit_creator_name_extra_whitespace() -> None:
    first, last = split_creator_name("  Grace   Hopper  ")
    assert first == "Grace"
    assert last == "Hopper"


# ---------------------------------------------------------------------------
# map_item_type
# ---------------------------------------------------------------------------


def testmap_item_type_arxiv_is_preprint() -> None:
    paper = NormalizedPaper(title="T", source="arxiv")
    assert map_item_type(paper) == "preprint"


def testmap_item_type_europe_pmc_preprint() -> None:
    paper = NormalizedPaper(title="T", source="europe_pmc_preprint")
    assert map_item_type(paper) == "preprint"


def testmap_item_type_semantic_scholar_is_journal_article() -> None:
    paper = NormalizedPaper(title="T", source="semantic_scholar")
    assert map_item_type(paper) == "journalArticle"


def testmap_item_type_openalex_is_journal_article() -> None:
    paper = NormalizedPaper(title="T", source="openalex")
    assert map_item_type(paper) == "journalArticle"


# ---------------------------------------------------------------------------
# map_paper_to_item
# ---------------------------------------------------------------------------


def test_map_paper_single_author_creator() -> None:
    paper = NormalizedPaper(
        title="Paper", authors=[NormalizedAuthor(name="Ada Lovelace")], year=2024, source="openalex"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["creators"] == [
        {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"}
    ]


def test_map_paper_multiple_authors() -> None:
    paper = NormalizedPaper(
        title="Paper",
        authors=[
            NormalizedAuthor(name="Alice Smith"),
            NormalizedAuthor(name="Bob Jones"),
            NormalizedAuthor(name="Carol White"),
        ],
        source="openalex",
    )
    item = map_paper_to_item(paper, "CKEY")
    creators = item["creators"]
    assert len(creators) == len(paper.authors)
    assert creators[0]["lastName"] == "Smith"
    assert creators[1]["lastName"] == "Jones"
    assert creators[2]["lastName"] == "White"
    assert all(c["creatorType"] == "author" for c in creators)


def test_map_paper_author_comma_format() -> None:
    paper = NormalizedPaper(
        title="Paper", authors=[NormalizedAuthor(name="Turing, Alan")], source="openalex"
    )
    item = map_paper_to_item(paper, "CKEY")
    creator = item["creators"][0]
    assert creator["firstName"] == "Alan"
    assert creator["lastName"] == "Turing"


def test_map_paper_empty_authors() -> None:
    paper = NormalizedPaper(title="Paper", authors=[], source="openalex")
    item = map_paper_to_item(paper, "CKEY")
    assert item["creators"] == []


def test_map_paper_doi_field() -> None:
    paper = NormalizedPaper(
        title="Paper", doi="10.1000/test", authors=[NormalizedAuthor(name="A B")], source="openalex"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["DOI"] == "10.1000/test"


def test_map_paper_missing_doi_is_empty_string() -> None:
    paper = NormalizedPaper(
        title="Paper", doi=None, authors=[NormalizedAuthor(name="A B")], source="openalex"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["DOI"] == ""


def test_map_paper_abstract_note() -> None:
    paper = NormalizedPaper(
        title="Paper",
        abstract="A great study.",
        authors=[NormalizedAuthor(name="A B")],
        source="openalex",
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["abstractNote"] == "A great study."


def test_map_paper_missing_abstract_is_empty_string() -> None:
    paper = NormalizedPaper(
        title="Paper", abstract=None, authors=[NormalizedAuthor(name="A B")], source="openalex"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["abstractNote"] == ""


def test_map_paper_year_as_date_string() -> None:
    paper = NormalizedPaper(
        title="Paper", year=2023, authors=[NormalizedAuthor(name="A B")], source="openalex"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["date"] == "2023"


def test_map_paper_missing_year_is_empty_string() -> None:
    paper = NormalizedPaper(
        title="Paper", year=None, authors=[NormalizedAuthor(name="A B")], source="openalex"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["date"] == ""


def test_map_paper_item_type_journal_article() -> None:
    paper = NormalizedPaper(
        title="Paper", authors=[NormalizedAuthor(name="A B")], source="semantic_scholar"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["itemType"] == "journalArticle"


def test_map_paper_item_type_preprint_sets_repository() -> None:
    paper = NormalizedPaper(
        title="Paper", authors=[NormalizedAuthor(name="A B")], source="arxiv", arxiv_id="2301.00001"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["itemType"] == "preprint"
    assert item["repository"] == "arxiv"
    assert item["archiveID"] == "2301.00001"


def test_map_paper_collection_key_in_collections() -> None:
    paper = NormalizedPaper(
        title="Paper", authors=[NormalizedAuthor(name="A B")], source="openalex"
    )
    item = map_paper_to_item(paper, "MYKEY")
    assert item["collections"] == ["MYKEY"]


def test_map_paper_title_is_stripped() -> None:
    paper = NormalizedPaper(
        title="  Whitespace Title  ", authors=[NormalizedAuthor(name="A B")], source="openalex"
    )
    item = map_paper_to_item(paper, "CKEY")
    assert item["title"] == "Whitespace Title"


def test_map_paper_source_in_extra() -> None:
    paper = NormalizedPaper(title="Paper", authors=[NormalizedAuthor(name="A B")], source="pubmed")
    item = map_paper_to_item(paper, "CKEY")
    assert "pubmed" in item["extra"]


# ---------------------------------------------------------------------------
# item_type / venue / volume / issue / pages → Zotero field mapping
# ---------------------------------------------------------------------------


def test_map_item_type_prefers_paper_item_type_over_source() -> None:
    paper = NormalizedPaper(title="T", source="openalex", item_type="preprint")
    assert map_item_type(paper) == "preprint"


def test_map_item_type_conference_paper() -> None:
    paper = NormalizedPaper(title="T", source="semantic_scholar", item_type="conference_paper")
    assert map_item_type(paper) == "conferencePaper"


def test_map_item_type_book_chapter() -> None:
    paper = NormalizedPaper(title="T", source="crossref", item_type="book_chapter")
    assert map_item_type(paper) == "bookSection"


def test_map_item_type_other_falls_back_to_journal_article() -> None:
    paper = NormalizedPaper(title="T", source="crossref", item_type="other")
    assert map_item_type(paper) == "journalArticle"


def test_map_item_type_none_uses_source_inference() -> None:
    paper = NormalizedPaper(title="T", source="arxiv", item_type=None)
    assert map_item_type(paper) == "preprint"


def test_map_paper_venue_journal_article_uses_publication_title() -> None:
    paper = NormalizedPaper(
        title="T", authors=[NormalizedAuthor(name="A")], source="openalex", venue="Nature"
    )
    item = map_paper_to_item(paper, "C")
    assert item["publicationTitle"] == "Nature"
    assert "repository" not in item
    assert "conferenceName" not in item


def test_map_paper_venue_preprint_uses_repository() -> None:
    paper = NormalizedPaper(
        title="T",
        authors=[NormalizedAuthor(name="A")],
        source="arxiv",
        item_type="preprint",
        venue="bioRxiv",
    )
    item = map_paper_to_item(paper, "C")
    assert item["repository"] == "bioRxiv"
    assert "publicationTitle" not in item


def test_map_paper_venue_conference_uses_conference_name() -> None:
    paper = NormalizedPaper(
        title="T",
        authors=[NormalizedAuthor(name="A")],
        source="semantic_scholar",
        item_type="conference_paper",
        venue="NeurIPS",
    )
    item = map_paper_to_item(paper, "C")
    assert item["conferenceName"] == "NeurIPS"
    assert "publicationTitle" not in item


def test_map_paper_volume_issue_pages() -> None:
    paper = NormalizedPaper(
        title="T",
        authors=[NormalizedAuthor(name="A")],
        source="crossref",
        volume="12",
        issue="3",
        pages="100-115",
    )
    item = map_paper_to_item(paper, "C")
    assert item["volume"] == "12"
    assert item["issue"] == "3"
    assert item["pages"] == "100-115"


def test_map_paper_none_venue_omits_venue_field() -> None:
    paper = NormalizedPaper(
        title="T", authors=[NormalizedAuthor(name="A")], source="openalex", venue=None
    )
    item = map_paper_to_item(paper, "C")
    assert "publicationTitle" not in item
    assert "repository" not in item
    assert "conferenceName" not in item


def test_map_paper_none_volume_omits_volume_field() -> None:
    paper = NormalizedPaper(
        title="T", authors=[NormalizedAuthor(name="A")], source="openalex", volume=None
    )
    item = map_paper_to_item(paper, "C")
    assert "volume" not in item
