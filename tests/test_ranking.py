import pytest

# ruff: noqa: I001, PLR2004

from agt.models import NormalizedPaper
from agt.tools import ranking as ranking_module
from agt.tools.ranking import compute_rank_score, rank_and_index_papers

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
        NormalizedPaper(title="Transformer\u200bSurvey", authors=["A"], semantic_score=0.2),
        NormalizedPaper(title="Transformer\u200bSurvey", authors=["A"], semantic_score=0.7),
    ]
    ranked = rank_and_index_papers(papers)
    assert len(ranked) == 1
    assert ranked[0].semantic_score == 0.7


def test_ranking_preserves_diacritics_in_authors() -> None:
    papers = [
        NormalizedPaper(
            title="Paper A",
            authors=["Jos\u00e9 Ni\u00f1o"],
            semantic_score=0.3,
        ),
        NormalizedPaper(
            title="Paper B",
            authors=["Zo\u00eb Kr\u00e1l"],
            semantic_score=0.4,
        ),
    ]
    ranked = rank_and_index_papers(papers)
    assert len(ranked) == 2
