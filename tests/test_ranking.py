import pytest

# ruff: noqa: I001, PLR2004

from agt.models import NormalizedAuthor, NormalizedPaper
from agt.tools import ranking as ranking_module
from agt.tools.ranking import (
    WEIGHTS_CITATION,
    WEIGHTS_DEFAULT,
    WEIGHTS_RECENCY,
    compute_rank_score,
    explain_paper,
    rank_and_index_papers,
)

EXPECTED_DEDUP_COUNT = 2
EXPECTED_ARXIV_DEDUP_COUNT = 1
EXPECTED_WINNING_ARXIV_SCORE = 0.8


def test_rank_formula_and_missing_fields() -> None:
    paper_with_year = NormalizedPaper(
        title="A",
        year=2024,
        semantic_score=0.8,
        citation_count=120,
        influential_citation_count=15,
        abstract="Detailed abstract",
        open_access=True,
    )
    paper_missing = NormalizedPaper(title="B", semantic_score=0.8, year=2024)

    score_with_year = compute_rank_score(paper_with_year, current_year=2026)
    score_missing = compute_rank_score(paper_missing, current_year=2026)

    assert score_with_year > score_missing
    assert score_with_year > 0.0


def test_dedup_and_stable_indices() -> None:
    papers = [
        NormalizedPaper(
            title="Same DOI low",
            doi="10.1000/ABC",
            semantic_score=0.2,
            year=2020,
        ),
        NormalizedPaper(
            title="Same DOI high",
            doi="10.1000/abc",
            semantic_score=0.9,
            year=2025,
        ),
        NormalizedPaper(
            title="Unique",
            semantic_score=0.4,
            year=2026,
        ),
    ]

    ranked = rank_and_index_papers(papers)

    assert len(ranked) == EXPECTED_DEDUP_COUNT
    assert [paper.index for paper in ranked] == [0, 1]
    assert ranked[0].doi == "10.1000/abc"
    assert ranked[0].score >= ranked[1].score


def test_dedup_uses_arxiv_id_when_doi_missing() -> None:
    papers = [
        NormalizedPaper(
            title="First",
            arxiv_id="2401.00001",
            semantic_score=0.2,
            year=2023,
        ),
        NormalizedPaper(
            title="Second",
            arxiv_id="2401.00001",
            semantic_score=0.8,
            year=2024,
        ),
    ]

    ranked = rank_and_index_papers(papers)

    assert len(ranked) == EXPECTED_ARXIV_DEDUP_COUNT
    assert ranked[0].arxiv_id == "2401.00001"
    assert ranked[0].semantic_score == EXPECTED_WINNING_ARXIV_SCORE


def test_compute_rank_score_uses_dynamic_current_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeDate:
        @staticmethod
        def today():
            return _FakeDate()

        @property
        def year(self) -> int:
            return 2030

    monkeypatch.setattr(ranking_module, "date", _FakeDate)
    paper_recent = NormalizedPaper(title="Recent", year=2029, semantic_score=0.5, open_access=False)
    paper_older = NormalizedPaper(title="Older", year=2020, semantic_score=0.5, open_access=False)

    score_recent = compute_rank_score(paper_recent)
    score_older = compute_rank_score(paper_older)
    assert score_recent > score_older


def test_ranking_handles_cjk_and_rtl_titles() -> None:
    papers = [
        NormalizedPaper(title="机器学习方法", year=2025, semantic_score=0.4),
        NormalizedPaper(title="تحليل السلاسل الزمنية", year=2025, semantic_score=0.5),
    ]
    ranked = rank_and_index_papers(papers)
    assert len(ranked) == 2
    assert ranked[0].title == "تحليل السلاسل الزمنية"


def test_dedup_handles_zero_width_characters_in_titles() -> None:
    papers = [
        NormalizedPaper(
            title="Transformer\u200bSurvey",
            authors=[NormalizedAuthor(name="A")],
            semantic_score=0.2,
        ),
        NormalizedPaper(
            title="Transformer\u200bSurvey",
            authors=[NormalizedAuthor(name="A")],
            semantic_score=0.7,
        ),
    ]
    ranked = rank_and_index_papers(papers)
    assert len(ranked) == 1
    assert ranked[0].semantic_score == 0.7


def test_ranking_preserves_diacritics_in_authors() -> None:
    papers = [
        NormalizedPaper(
            title="Paper A",
            authors=[NormalizedAuthor(name="Jos\u00e9 Ni\u00f1o")],
            semantic_score=0.3,
        ),
        NormalizedPaper(
            title="Paper B",
            authors=[NormalizedAuthor(name="Zo\u00eb Kr\u00e1l")],
            semantic_score=0.4,
        ),
    ]
    ranked = rank_and_index_papers(papers)
    assert len(ranked) == 2


# ---------------------------------------------------------------------------
# Keyword-relevance fallback and dynamic-weights tests
# ---------------------------------------------------------------------------


def test_keyword_relevance_beats_high_citation_irrelevant_paper() -> None:
    """A highly-cited off-topic paper must not outrank an on-topic paper when
    query_terms are supplied and neither paper has a semantic score.

    Reproduces the 'Inorganic Chemistry textbook' bug where citation count
    dominated results from sources without native relevance scoring.
    """
    on_topic = NormalizedPaper(
        title="Time series forecasting methods",
        abstract="We survey forecasting methods for time series selection.",
        year=2024,
        semantic_score=0.0,
        citation_count=5,
        open_access=True,
    )
    off_topic = NormalizedPaper(
        title="Inorganic Chemistry: Principles of Structure",
        abstract="A comprehensive textbook on inorganic chemistry.",
        year=2024,
        semantic_score=0.0,
        citation_count=2395,
        open_access=True,
    )

    ranked = rank_and_index_papers(
        [off_topic, on_topic],
        query_terms=["time", "series", "forecasting"],
    )

    assert ranked[0].title == "Time series forecasting methods", (
        "On-topic paper should rank first when query_terms are used as relevance fallback"
    )


def test_keyword_relevance_zero_when_no_terms() -> None:
    """Without query_terms the fallback is inactive; citation count may dominate."""
    on_topic = NormalizedPaper(
        title="Time series forecasting",
        year=2024,
        semantic_score=0.0,
        citation_count=5,
    )
    off_topic = NormalizedPaper(
        title="Unrelated high-citation paper",
        year=2024,
        semantic_score=0.0,
        citation_count=2000,
    )

    ranked = rank_and_index_papers([off_topic, on_topic])
    # Without query_terms the fallback is off; citation wins here.
    assert ranked[0].title == "Unrelated high-citation paper"


def test_recency_weights_boost_fresh_papers_over_old_high_citation() -> None:
    """WEIGHTS_RECENCY should surface a fresh low-citation paper over an old classic."""
    fresh = NormalizedPaper(
        title="New method 2025",
        year=2025,
        semantic_score=0.0,
        citation_count=2,
    )
    classic = NormalizedPaper(
        title="Classic method 2010",
        year=2010,
        semantic_score=0.0,
        citation_count=500,
    )

    ranked_default = rank_and_index_papers([classic, fresh], current_year=2026)
    ranked_recency = rank_and_index_papers(
        [classic, fresh], current_year=2026, weights=WEIGHTS_RECENCY
    )

    # Default weights: classic wins on citation signal.
    assert ranked_default[0].title == "Classic method 2010"
    # Recency weights: fresh paper wins.
    assert ranked_recency[0].title == "New method 2025"


def test_citation_weights_prefer_highly_cited_over_recent() -> None:
    """WEIGHTS_CITATION should surface a highly-cited older paper over a brand-new one."""
    fresh = NormalizedPaper(
        title="Brand new 2026",
        year=2026,
        semantic_score=0.5,
        citation_count=1,
    )
    classic = NormalizedPaper(
        title="Seminal work 2015",
        year=2015,
        semantic_score=0.5,
        citation_count=800,
    )

    ranked = rank_and_index_papers([fresh, classic], current_year=2026, weights=WEIGHTS_CITATION)
    assert ranked[0].title == "Seminal work 2015"


def test_compute_rank_score_uses_keyword_fallback_when_semantic_zero() -> None:
    """compute_rank_score with query_terms uses keyword overlap when semantic_score=0."""
    paper = NormalizedPaper(
        title="Time series forecasting survey",
        abstract="We review time series prediction methods.",
        year=2024,
        semantic_score=0.0,
        citation_count=10,
    )
    score_with_terms = compute_rank_score(
        paper,
        current_year=2026,
        query_terms=["time", "series", "forecasting"],
    )
    score_without_terms = compute_rank_score(paper, current_year=2026)

    assert score_with_terms > score_without_terms, (
        "Keyword relevance fallback should increase score over pure citation ranking"
    )


def test_compute_rank_score_adds_query_bonus_when_semantic_nonzero() -> None:
    """Strong lexical matches should still receive a small query bonus even with provider scores."""
    paper = NormalizedPaper(
        title="Time series forecasting overview",
        abstract="Forecasting methods for time series applications.",
        year=2024,
        semantic_score=0.9,
        citation_count=0,
    )
    score_with_terms = compute_rank_score(
        paper,
        current_year=2026,
        query_terms=["time", "series", "forecasting"],
    )
    score_without_terms = compute_rank_score(paper, current_year=2026)

    assert score_with_terms > score_without_terms


def test_compute_rank_score_no_query_bonus_for_unmatched_semantic_paper() -> None:
    paper = NormalizedPaper(
        title="Completely unrelated paper",
        abstract="Nothing about chemistry or materials here.",
        year=2024,
        semantic_score=0.9,
        citation_count=0,
    )

    score_with_terms = compute_rank_score(
        paper,
        current_year=2026,
        query_terms=["time", "series", "forecasting"],
    )
    score_without_terms = compute_rank_score(paper, current_year=2026)

    assert abs(score_with_terms - score_without_terms) < 1e-9


def test_rank_and_index_papers_promotes_distinct_anchor_over_near_duplicate_titles() -> None:
    papers = [
        NormalizedPaper(
            title="Retrieval-Augmented Generation for Large Language Models: A Survey",
            year=2025,
            semantic_score=0.95,
            citation_count=260,
        ),
        NormalizedPaper(
            title="Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG",
            year=2025,
            semantic_score=0.94,
            citation_count=240,
        ),
        NormalizedPaper(
            title="REALM: Retrieval-Augmented Language Model Pre-Training",
            year=2020,
            semantic_score=0.94,
            citation_count=515,
        ),
    ]

    ranked = rank_and_index_papers(
        papers,
        current_year=2026,
        query_terms=["retrieval", "augmented"],
    )

    assert ranked[1].title == "REALM: Retrieval-Augmented Language Model Pre-Training"
    assert ranked[2].title == "Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG"


def test_rank_and_index_papers_boosts_specific_anchor_with_full_query_coverage() -> None:
    papers = [
        NormalizedPaper(
            title="Time series forecasting with transformers",
            year=2023,
            semantic_score=0.95,
            citation_count=220,
        ),
        NormalizedPaper(
            title="Temporal Fusion Transformers for interpretable multi-horizon time series forecasting",
            year=2021,
            semantic_score=0.94,
            citation_count=153,
        ),
    ]

    ranked = rank_and_index_papers(
        papers,
        current_year=2026,
        query_terms=["time", "series", "forecasting", "transformer"],
    )

    assert ranked[0].title == (
        "Temporal Fusion Transformers for interpretable multi-horizon time series forecasting"
    )


def test_weights_presets_sum_to_approximately_one() -> None:
    """All weight fields (excl. bonuses) of the presets should sum ≤ 1.0."""
    for preset in (WEIGHTS_DEFAULT, WEIGHTS_RECENCY, WEIGHTS_CITATION):
        core_sum = preset.semantic + preset.citation + preset.influential + preset.recency
        assert core_sum <= 1.0 + 1e-9, f"Core weights sum > 1.0 for {preset}"


# ---------------------------------------------------------------------------
# explain_paper
# ---------------------------------------------------------------------------


def test_explain_paper_high_semantic_score() -> None:
    paper = NormalizedPaper(
        title="Attention is All You Need",
        year=2017,
        semantic_score=0.92,
        citation_count=50_000,
        influential_citation_count=300,
        source="semantic_scholar",
        open_access=False,
    )
    explanation = explain_paper(paper, query_terms=["attention", "transformer"])
    assert "high relevance" in explanation
    assert "50,000 citations" in explanation
    assert "300 influential" in explanation
    assert "semantic scholar" in explanation
    assert "2017" in explanation


def test_explain_paper_no_semantic_score_uses_keyword_match() -> None:
    paper = NormalizedPaper(
        title="Temporal fusion transformer forecasting",
        year=2021,
        semantic_score=0.0,
        citation_count=5,
        source="crossref",
        open_access=True,
    )
    explanation = explain_paper(
        paper,
        query_terms=["temporal", "fusion", "transformer", "forecasting"],
    )
    assert "query terms in title" in explanation or "query terms matched" in explanation
    assert "open access" in explanation
    assert "crossref" in explanation
    assert "2021" in explanation


def test_explain_paper_low_citations_omitted() -> None:
    paper = NormalizedPaper(
        title="A small study",
        year=2023,
        semantic_score=0.5,
        citation_count=3,
        source="pubmed",
    )
    explanation = explain_paper(paper)
    assert "citations" not in explanation
    assert "pubmed" in explanation


def test_explain_paper_no_signals_returns_fallback() -> None:
    paper = NormalizedPaper(title="Unknown paper", source="base")
    explanation = explain_paper(paper)
    assert explanation
    assert "base" in explanation


def test_explain_paper_format_is_dot_separated() -> None:
    paper = NormalizedPaper(
        title="CRISPR genome editing",
        year=2022,
        semantic_score=0.8,
        citation_count=200,
        source="europe_pmc",
        open_access=True,
    )
    explanation = explain_paper(paper, query_terms=["crispr", "genome", "editing"])
    parts = explanation.split(" · ")
    assert len(parts) >= 3
