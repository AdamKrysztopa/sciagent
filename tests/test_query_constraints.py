from __future__ import annotations

from agt.models import NormalizedPaper
from agt.tools.query_constraints import (
    apply_query_constraints,
    parse_query_constraints,
    strip_constraints,
)

EXPECTED_MIN_YEAR = 2022
EXPECTED_MIN_CITATIONS = 10


_EXPECTED_MIN_YEAR_2020 = 2020
_EXPECTED_MIN_YEAR_2024 = 2024
_EXPECTED_MIN_CITATIONS_MOST_CITED = 10
_EXPECTED_FILTER_COUNT = 2


def test_parse_query_constraints_extracts_year_citation_and_flags() -> None:
    constraints = parse_query_constraints(
        "open access papers after 2022 with at least 25 citations and positive community perception",
        default_limit=10,
    )

    assert constraints.year.min_year == EXPECTED_MIN_YEAR
    assert constraints.citations.min_citations >= EXPECTED_MIN_CITATIONS
    assert constraints.quality.open_access_only is True
    assert constraints.quality.require_positive_community_perception is True


def test_parse_year_and_newer_pattern() -> None:
    constraints = parse_query_constraints(
        "the most cited 2020 and newer timeseries papers",
        default_limit=5,
    )
    assert constraints.year.min_year == _EXPECTED_MIN_YEAR_2020
    assert constraints.citations.min_citations >= _EXPECTED_MIN_CITATIONS_MOST_CITED  # "most cited"
    assert "timeseries" in constraints.keywords.include_keywords
    # constraint words must not leak into keywords
    assert "cited" not in constraints.keywords.include_keywords
    assert "newer" not in constraints.keywords.include_keywords


def test_most_cited_sets_min_citations() -> None:
    constraints = parse_query_constraints(
        "most cited machine learning papers",
        default_limit=10,
    )
    assert constraints.citations.min_citations >= _EXPECTED_MIN_CITATIONS_MOST_CITED


def test_strip_constraints_removes_year_and_limit_phrases() -> None:
    cleaned = strip_constraints("the most cited 2020 and newer timeseries papers - list 5")
    assert "2020" not in cleaned
    assert "list" not in cleaned.lower().split()
    assert "timeseries" in cleaned.lower()


def test_not_older_than_sets_min_year() -> None:
    constraints = parse_query_constraints(
        "papers in nutrition in sport. not older than 2024",
        default_limit=5,
    )
    assert constraints.year.min_year == _EXPECTED_MIN_YEAR_2024
    assert constraints.year.max_year is None


def test_highest_quoted_sets_min_citations() -> None:
    constraints = parse_query_constraints(
        "highest quoted papers in nutrition in sport",
        default_limit=5,
    )
    assert constraints.citations.min_citations >= _EXPECTED_MIN_CITATIONS_MOST_CITED


def test_keywords_exclude_constraint_words() -> None:
    constraints = parse_query_constraints(
        "the most advanced RAG techniques in 2026 - game changers",
        default_limit=5,
    )
    kw = constraints.keywords.include_keywords
    assert "rag" in kw or "RAG" in kw or any("rag" in k for k in kw)
    assert "techniques" in kw
    assert "advanced" not in kw
    assert "changers" not in kw
    assert "game" not in kw


def test_apply_query_constraints_filters_by_year_citations_open_access_and_keywords() -> None:
    constraints = parse_query_constraints(
        "graph learning after 2023 at least 10 citations open access",
        default_limit=10,
    )

    papers = [
        NormalizedPaper(
            title="Graph learning advances",
            abstract="New benchmarks",
            year=2024,
            citation_count=15,
            open_access=True,
            semantic_score=0.3,
        ),
        NormalizedPaper(
            title="Graph learning classic",
            abstract="Foundational article",
            year=2020,
            citation_count=200,
            open_access=True,
            semantic_score=0.9,
        ),
        NormalizedPaper(
            title="Vision transformers",
            abstract="Image model survey",
            year=2024,
            citation_count=30,
            open_access=True,
            semantic_score=0.8,
        ),
        NormalizedPaper(
            title="Graph learning review",
            abstract="Non OA source",
            year=2025,
            citation_count=30,
            open_access=False,
            semantic_score=0.8,
        ),
    ]

    filtered = apply_query_constraints(papers, constraints)

    # Keyword matching is delegated to API-level search; post-filtering
    # only applies year, citation, and open-access constraints.
    assert len(filtered) == _EXPECTED_FILTER_COUNT
    assert filtered[0].title == "Graph learning advances"
    assert filtered[1].title == "Vision transformers"
