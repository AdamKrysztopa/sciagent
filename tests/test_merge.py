"""Tests for field-level merge with provenance (P8.4)."""

from __future__ import annotations

from typing import cast

from agt.models import FieldConflict, FieldConflictValue, NormalizedAuthor, NormalizedPaper
from agt.tools.merge import (
    _jaccard,  # pyright: ignore[reportPrivateUsage]
    cluster,
    merge,
    merge_cluster,
)

# ---------------------------------------------------------------------------
# Named constants (avoids PLR2004 magic value lint errors)
# ---------------------------------------------------------------------------

_TWO_SOURCES = 2
_THREE_CLUSTERS = 3
_MAX_CITATION = 250
_YEAR_2022 = 2022
_ALPHA_MAX_CITATION = 20
_TWO_PAPERS = 2
_TWO_CLUSTERS = 2
_TWO_CONFLICT_VALUES = 2

# ---------------------------------------------------------------------------
# Test 1: DOI dedup — two papers with the same DOI from different providers
# ---------------------------------------------------------------------------


def test_doi_dedup_merges_two_providers() -> None:
    papers = [
        NormalizedPaper(
            title="Attention Is All You Need",
            doi="10.48550/arXiv.1706.03762",
            year=2017,
            source="semantic_scholar",
            citation_count=10000,
        ),
        NormalizedPaper(
            title="Attention Is All You Need",
            doi="10.48550/arXiv.1706.03762",
            year=2017,
            source="crossref",
            citation_count=9000,
        ),
    ]

    result = merge(papers)

    assert len(result) == 1
    merged = result[0]
    assert "crossref" in merged.sources
    assert "semantic_scholar" in merged.sources
    assert len(merged.sources) == _TWO_SOURCES


# ---------------------------------------------------------------------------
# Test 2: Year conflict — same DOI, different years
# ---------------------------------------------------------------------------


def test_year_conflict_recorded() -> None:
    papers = [
        NormalizedPaper(
            title="Some Paper",
            doi="10.1000/xyz",
            year=2020,
            source="crossref",
        ),
        NormalizedPaper(
            title="Some Paper",
            doi="10.1000/xyz",
            year=2021,
            source="semantic_scholar",
        ),
    ]

    result = merge(papers)

    assert len(result) == 1
    merged = result[0]
    year_conflicts = [c for c in merged.conflicts if c.field == "year"]
    assert len(year_conflicts) == 1
    conflict = year_conflicts[0]
    providers = [v.provider for v in conflict.values]
    assert "crossref" in providers
    assert "semantic_scholar" in providers


# ---------------------------------------------------------------------------
# Test 3: Title Jaccard < 0.8 — title conflict recorded
# ---------------------------------------------------------------------------


def test_title_conflict_when_jaccard_below_threshold() -> None:
    # Same DOI but very different titles → title conflict
    papers = [
        NormalizedPaper(
            title="Deep Learning for Natural Language Processing",
            doi="10.1000/abc",
            source="crossref",
        ),
        NormalizedPaper(
            title="Quantum Mechanics Introduction",
            doi="10.1000/abc",
            source="semantic_scholar",
        ),
    ]

    result = merge(papers)

    assert len(result) == 1
    title_conflicts = [c for c in result[0].conflicts if c.field == "title"]
    assert len(title_conflicts) == 1


# ---------------------------------------------------------------------------
# Test 4: Author union by ORCID — fills missing IDs from second provider
# ---------------------------------------------------------------------------


def test_author_union_by_orcid_enriches_ids() -> None:
    author_s2 = NormalizedAuthor(
        name="Jane Doe",
        family="Doe",
        given="Jane",
        orcid="0000-0001-2345-6789",
        s2_author_id="s2-123",
    )
    author_openalex = NormalizedAuthor(
        name="Jane Doe",
        family="Doe",
        given="Jane",
        orcid="0000-0001-2345-6789",
        openalex_id="OA-456",
        affiliation="MIT",
    )
    papers = [
        NormalizedPaper(
            title="Paper A",
            doi="10.1000/p",
            source="semantic_scholar",
            authors=[author_s2],
        ),
        NormalizedPaper(
            title="Paper A",
            doi="10.1000/p",
            source="openalex",
            authors=[author_openalex],
        ),
    ]

    result = merge(papers)

    assert len(result) == 1
    merged = result[0]
    assert len(merged.authors) == 1
    author = merged.authors[0]
    assert author.orcid == "0000-0001-2345-6789"
    assert author.s2_author_id == "s2-123"
    assert author.openalex_id == "OA-456"
    assert author.affiliation == "MIT"


# ---------------------------------------------------------------------------
# Test 5: Author union by normalized last name (no ORCID)
# ---------------------------------------------------------------------------


def test_author_union_by_normalized_last() -> None:
    author_a = NormalizedAuthor(
        name="Alice Smith",
        family="Smith",
        given="Alice",
        s2_author_id="s2-abc",
    )
    author_b = NormalizedAuthor(
        name="A. Smith",
        family="Smith",
        given="A.",
        openalex_id="OA-abc",
    )
    papers = [
        NormalizedPaper(
            title="Same Paper",
            doi="10.1000/q",
            source="semantic_scholar",
            authors=[author_a],
        ),
        NormalizedPaper(
            title="Same Paper",
            doi="10.1000/q",
            source="openalex",
            authors=[author_b],
        ),
    ]

    result = merge(papers)

    assert len(result) == 1
    # Same last name + same given initial → one author entry
    assert len(result[0].authors) == 1
    author = result[0].authors[0]
    assert author.s2_author_id == "s2-abc"
    assert author.openalex_id == "OA-abc"


# ---------------------------------------------------------------------------
# Test 6: Abstract — longest wins
# ---------------------------------------------------------------------------


def test_abstract_longest_wins() -> None:
    papers = [
        NormalizedPaper(
            title="Paper",
            doi="10.1000/r",
            source="crossref",
            abstract="Short.",
        ),
        NormalizedPaper(
            title="Paper",
            doi="10.1000/r",
            source="semantic_scholar",
            abstract="A much longer and more detailed abstract that says a lot more.",
        ),
        NormalizedPaper(
            title="Paper",
            doi="10.1000/r",
            source="openalex",
            abstract="Medium length abstract here.",
        ),
    ]

    result = merge(papers)

    assert len(result) == 1
    assert result[0].abstract == "A much longer and more detailed abstract that says a lot more."


# ---------------------------------------------------------------------------
# Test 7: Citation count — max wins
# ---------------------------------------------------------------------------


def test_citation_count_max_wins() -> None:
    papers = [
        NormalizedPaper(title="P", doi="10.1/x", source="crossref", citation_count=100),
        NormalizedPaper(title="P", doi="10.1/x", source="openalex", citation_count=250),
        NormalizedPaper(title="P", doi="10.1/x", source="semantic_scholar", citation_count=180),
    ]

    result = merge(papers)

    assert len(result) == 1
    assert result[0].citation_count == _MAX_CITATION


# ---------------------------------------------------------------------------
# Test 8: Single-paper cluster returns it unchanged (modulo sources)
# ---------------------------------------------------------------------------


def test_single_paper_cluster_no_conflicts() -> None:
    paper = NormalizedPaper(
        title="Lone Paper",
        doi="10.1/lone",
        year=2022,
        source="openalex",
        citation_count=42,
    )

    result = merge_cluster([paper])

    assert result.title == "Lone Paper"
    assert result.doi == "10.1/lone"
    assert result.year == _YEAR_2022
    assert result.source == "openalex"
    assert result.sources == ["openalex"]
    assert result.conflicts == []


# ---------------------------------------------------------------------------
# Test 9: merge() end-to-end — 5 papers, 3 clusters → 3 merged papers
# ---------------------------------------------------------------------------


def test_merge_end_to_end_three_clusters() -> None:
    cluster_1 = [
        NormalizedPaper(title="Alpha Paper", doi="10.1/a", source="crossref", citation_count=10),
        NormalizedPaper(title="Alpha Paper", doi="10.1/a", source="openalex", citation_count=20),
    ]
    cluster_2 = [
        NormalizedPaper(title="Beta Study", doi="10.1/b", source="pubmed"),
        NormalizedPaper(title="Beta Study", doi="10.1/b", source="europe_pmc"),
    ]
    singleton = [
        NormalizedPaper(title="Gamma Work", doi="10.1/c", source="semantic_scholar"),
    ]

    result = merge(cluster_1 + cluster_2 + singleton)

    assert len(result) == _THREE_CLUSTERS
    dois = {r.doi for r in result}
    assert "10.1/a" in dois
    assert "10.1/b" in dois
    assert "10.1/c" in dois

    alpha = next(r for r in result if r.doi == "10.1/a")
    assert alpha.citation_count == _ALPHA_MAX_CITATION
    assert set(alpha.sources) == {"crossref", "openalex"}


# ---------------------------------------------------------------------------
# Test 10: cluster() — title fuzzy match, same year → one cluster
# ---------------------------------------------------------------------------


def test_cluster_fuzzy_match_high_jaccard() -> None:
    # Identical titles, same year, no DOIs
    p1 = NormalizedPaper(
        title="Transformers in Natural Language Processing", year=2021, source="arxiv"
    )
    p2 = NormalizedPaper(
        title="Transformers in natural language processing",  # different casing
        year=2021,
        source="semantic_scholar",
    )

    clusters = cluster([p1, p2])

    assert len(clusters) == 1
    assert len(clusters[0]) == _TWO_PAPERS


# ---------------------------------------------------------------------------
# Test 11: cluster() — very different titles → two separate clusters
# ---------------------------------------------------------------------------


def test_cluster_no_match_different_titles() -> None:
    p1 = NormalizedPaper(title="Quantum Computing Applications", year=2020, source="arxiv")
    p2 = NormalizedPaper(title="Protein Folding with Neural Networks", year=2020, source="openalex")

    clusters = cluster([p1, p2])

    assert len(clusters) == _TWO_CLUSTERS


# ---------------------------------------------------------------------------
# Bonus: _jaccard smoke test
# ---------------------------------------------------------------------------


def test_jaccard_identical_titles() -> None:
    assert _jaccard("Foo Bar Baz", "foo bar baz") == 1.0


def test_jaccard_empty_vs_empty() -> None:
    assert _jaccard("", "") == 1.0


def test_jaccard_disjoint_titles() -> None:
    assert _jaccard("alpha beta", "gamma delta") == 0.0


# ---------------------------------------------------------------------------
# open_access: True if any provider says True
# ---------------------------------------------------------------------------


def test_open_access_any_provider_true() -> None:
    papers = [
        NormalizedPaper(title="P", doi="10.1/oa", source="crossref", open_access=False),
        NormalizedPaper(title="P", doi="10.1/oa", source="openalex", open_access=True),
    ]

    result = merge(papers)

    assert len(result) == 1
    assert result[0].open_access is True


# ---------------------------------------------------------------------------
# conflicts field serializes cleanly
# ---------------------------------------------------------------------------


def test_conflicts_serialize_to_dict() -> None:
    papers = [
        NormalizedPaper(title="P", doi="10.1/s", year=2019, source="crossref"),
        NormalizedPaper(title="P", doi="10.1/s", year=2020, source="openalex"),
    ]

    result = merge(papers)
    assert len(result) == 1

    dumped = result[0].model_dump()
    conflicts_raw = dumped["conflicts"]
    assert isinstance(conflicts_raw, list)
    conflicts_typed = cast(list[dict[str, object]], conflicts_raw)
    assert len(conflicts_typed) == 1
    c = conflicts_typed[0]
    assert c["field"] == "year"
    assert isinstance(c["values"], list)


# ---------------------------------------------------------------------------
# NormalizedPaper default has empty conflicts list
# ---------------------------------------------------------------------------


def test_normalized_paper_default_conflicts_empty() -> None:
    paper = NormalizedPaper(title="Default paper")
    assert paper.conflicts == []
    assert isinstance(paper.conflicts, list)


# ---------------------------------------------------------------------------
# FieldConflict model validation
# ---------------------------------------------------------------------------


def test_field_conflict_round_trips() -> None:
    fc = FieldConflict(
        field="year",
        values=[
            FieldConflictValue(provider="crossref", value=2020),
            FieldConflictValue(provider="openalex", value=2021),
        ],
    )
    dumped = fc.model_dump()
    assert dumped["field"] == "year"
    restored = FieldConflict.model_validate(dumped)
    assert restored.field == "year"
    assert len(restored.values) == _TWO_CONFLICT_VALUES
