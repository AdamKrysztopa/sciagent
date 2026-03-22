from agt.models import NormalizedPaper


def test_normalized_paper_defaults() -> None:
    paper = NormalizedPaper(title="A paper")
    assert paper.source == "semantic_scholar"
    assert paper.authors == []
