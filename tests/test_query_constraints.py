from __future__ import annotations

# ruff: noqa: I001, PLR2004

from agt.config import Settings
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
_EXPECTED_MIN_YEAR_2021 = 2021
_EXPECTED_MAX_YEAR_2023 = 2023
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


def test_parse_between_year_range_sets_both_bounds() -> None:
    constraints = parse_query_constraints(
        "graph learning papers between 2020 and 2024",
        default_limit=5,
    )
    assert constraints.year.min_year == _EXPECTED_MIN_YEAR_2020
    assert constraints.year.max_year == _EXPECTED_MIN_YEAR_2024


def test_parse_from_to_year_range_sets_both_bounds() -> None:
    constraints = parse_query_constraints(
        "transformer papers from 2021 to 2023",
        default_limit=5,
    )
    assert constraints.year.min_year == _EXPECTED_MIN_YEAR_2021
    assert constraints.year.max_year == _EXPECTED_MAX_YEAR_2023


def test_parse_exclude_keywords_from_query() -> None:
    constraints = parse_query_constraints(
        "nutrition in sport excluding supplements but not marketing",
        default_limit=5,
    )
    assert "supplements" in constraints.keywords.exclude_keywords
    assert "marketing" in constraints.keywords.exclude_keywords


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


def test_apply_query_constraints_filters_excluded_keywords_in_title_and_abstract() -> None:
    constraints = parse_query_constraints(
        "nutrition papers not about supplements",
        default_limit=10,
    )

    papers = [
        NormalizedPaper(
            title="Sports nutrition overview",
            abstract="General recommendations for athletes",
            year=2024,
            citation_count=20,
            open_access=True,
            semantic_score=0.7,
        ),
        NormalizedPaper(
            title="Supplements and performance",
            abstract="Dosing and efficacy",
            year=2024,
            citation_count=20,
            open_access=True,
            semantic_score=0.8,
        ),
        NormalizedPaper(
            title="Hydration strategies",
            abstract="supplements are discussed in this review",
            year=2024,
            citation_count=20,
            open_access=True,
            semantic_score=0.8,
        ),
    ]

    filtered = apply_query_constraints(papers, constraints)
    assert len(filtered) == 1
    assert filtered[0].title == "Sports nutrition overview"


def test_exclude_keywords_matches_diacritics_and_unicode_text() -> None:
    constraints = parse_query_constraints("energy metabolism excluding naïve", default_limit=10)
    papers = [
        NormalizedPaper(title="A naïve approach", abstract=None),
        NormalizedPaper(title="Robust approach", abstract="no exclusion keyword"),
    ]
    filtered = apply_query_constraints(papers, constraints)
    assert len(filtered) == 1
    assert filtered[0].title == "Robust approach"


def test_exclude_keywords_handles_emoji_and_cjk_query() -> None:
    constraints = parse_query_constraints("机器学习 papers but not baseline 😊", default_limit=10)
    papers = [
        NormalizedPaper(title="机器学习 baseline methods", abstract=None),
        NormalizedPaper(title="机器学习 advanced methods", abstract=None),
    ]
    filtered = apply_query_constraints(papers, constraints)
    assert len(filtered) == 1
    assert "advanced" in filtered[0].title


def test_configurable_most_cited_threshold() -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "x",
        "AGT_ZOTERO_API_KEY": "z",
        "AGT_ZOTERO_LIBRARY_ID": "1",
        "AGT_CITATION_THRESHOLD_MOST_CITED": 33,
    })
    constraints = parse_query_constraints(
        "most cited graph learning papers",
        default_limit=5,
        settings=settings,
    )
    assert constraints.citations.min_citations == 33


def test_configurable_trending_threshold() -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "x",
        "AGT_ZOTERO_API_KEY": "z",
        "AGT_ZOTERO_LIBRARY_ID": "1",
        "AGT_CITATION_THRESHOLD_TRENDING": 9,
    })
    constraints = parse_query_constraints(
        "trending transformer papers",
        default_limit=5,
        settings=settings,
    )
    assert constraints.citations.min_citations == 9
