from __future__ import annotations

from agt.models import NormalizedPaper
from agt.tools.query_constraints import apply_query_constraints, parse_query_constraints

EXPECTED_MIN_YEAR = 2022
EXPECTED_MIN_CITATIONS = 50


def test_parse_query_constraints_extracts_year_citation_and_flags() -> None:
    constraints = parse_query_constraints(
        "open access papers after 2022 with at least 25 citations and positive community perception",
        default_limit=10,
    )

    assert constraints.year.min_year == EXPECTED_MIN_YEAR
    assert constraints.citations.min_citations >= EXPECTED_MIN_CITATIONS
    assert constraints.quality.open_access_only is True
    assert constraints.quality.require_positive_community_perception is True


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

    assert len(filtered) == 1
    assert filtered[0].title == "Graph learning advances"
