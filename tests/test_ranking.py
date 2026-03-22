from agt.models import NormalizedPaper
from agt.tools.ranking import compute_rank_score, rank_and_index_papers

EXPECTED_DEDUP_COUNT = 2


def test_rank_formula_and_missing_fields() -> None:
    paper_with_year = NormalizedPaper(
        title="A",
        year=2024,
        semantic_score=0.8,
        open_access=True,
    )
    paper_missing = NormalizedPaper(title="B", semantic_score=0.8)

    score_with_year = compute_rank_score(paper_with_year, current_year=2026)
    score_missing = compute_rank_score(paper_missing, current_year=2026)

    assert round(score_with_year, 4) == round(0.8 * 0.7 + (2026 - 2024) * -0.3 + 0.2, 4)
    assert round(score_missing, 4) == round(0.8 * 0.7, 4)


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
