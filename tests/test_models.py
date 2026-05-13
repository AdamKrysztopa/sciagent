import pytest

from agt.models import (
    AgentState,
    FilterEditContract,
    HardFilters,
    NormalizedPaper,
    ResolvedAuthor,
    SearchPlan,
)


def test_normalized_paper_defaults() -> None:
    paper = NormalizedPaper(title="A paper")
    assert paper.source == "semantic_scholar"
    assert paper.authors == []
    assert paper.arxiv_id is None


def test_normalized_paper_citation_relation_defaults_to_none() -> None:
    paper = NormalizedPaper(title="T", source="openalex", sources=["openalex"])
    assert paper.citation_relation is None


def test_search_plan_seed_dois_defaults_empty() -> None:
    plan = SearchPlan(original_query="x", topic_query="x")
    assert plan.seed_dois == []


def test_search_plan_seed_dois_parses_correctly() -> None:
    plan = SearchPlan(original_query="x", topic_query="x", seed_dois=["10.1000/test"])
    assert plan.seed_dois == ["10.1000/test"]


def test_agent_state_allows_checkpoint_safe_serialized_payloads() -> None:
    state: AgentState = {
        "request_id": "req-1",
        "thread_id": "thread-1",
        "messages": ["Processed query: q"],
        "papers": [{"title": "Paper A", "source": "semantic_scholar"}],
        "collection_name": "Inbox",
        "approved": False,
        "decision": "pending",
        "phase": "awaiting_approval",
        "selected_indices": [0],
        "preflight": {"ok": True},
        "trace_spans": [],
        "write_result": None,
        "search_metadata": {"original_query": "q", "regex_query": "q"},
    }

    assert state["papers"][0]["title"] == "Paper A"


# ── P9.6: ResolvedAuthor + FilterEditContract.authors ───────────────────────


def test_resolved_author_minimal() -> None:
    author = ResolvedAuthor(name="Yoshua Bengio")
    assert author.name == "Yoshua Bengio"
    assert author.openalex_id is None
    assert author.orcid is None
    assert author.s2_author_id is None


def test_resolved_author_with_all_ids() -> None:
    author = ResolvedAuthor(
        name="Geoffrey Hinton",
        openalex_id="A5023888391",
        orcid="0000-0001-8103-7730",
        s2_author_id="1695689",
    )
    assert author.openalex_id == "A5023888391"
    assert author.orcid == "0000-0001-8103-7730"
    assert author.s2_author_id == "1695689"


def test_filter_edit_contract_authors_defaults_empty() -> None:
    contract = FilterEditContract(original_query="attention")
    assert contract.authors == []


def test_filter_edit_contract_authors_roundtrips_via_model() -> None:
    contract = FilterEditContract(
        original_query="attention",
        authors=[ResolvedAuthor(name="Yoshua Bengio", openalex_id="A5023888391")],
    )
    dumped = contract.model_dump()
    restored = FilterEditContract.model_validate(dumped)
    assert len(restored.authors) == 1
    assert restored.authors[0].name == "Yoshua Bengio"
    assert restored.authors[0].openalex_id == "A5023888391"


def test_hard_filters_author_names_defaults_empty() -> None:
    hf = HardFilters()
    assert hf.author_names == []


def test_hard_filters_author_names_stored() -> None:
    hf = HardFilters(author_names=["Yoshua Bengio"])
    assert hf.author_names == ["Yoshua Bengio"]


@pytest.mark.parametrize(
    "author_ids,author_names",
    [
        (["A1", "A2"], []),
        ([], ["Bengio"]),
        (["A1"], ["Bengio"]),
    ],
)
def test_hard_filters_author_combinations_valid(
    author_ids: list[str], author_names: list[str]
) -> None:
    hf = HardFilters(author_ids=author_ids, author_names=author_names)
    assert hf.author_ids == author_ids
    assert hf.author_names == author_names
