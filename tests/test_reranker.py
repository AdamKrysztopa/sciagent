from __future__ import annotations

# ruff: noqa: I001, PLW0108

import pytest

from agt.models import NormalizedPaper
from agt.tools import reranker


class _FakeModel:
    def encode(self, texts: list[str], normalize_embeddings: bool = False) -> list[list[float]]:
        _ = normalize_embeddings
        if len(texts) == 1:
            return [[1.0, 0.0]]
        vectors: list[list[float]] = []
        for text in texts:
            if "relevant" in text:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors


def test_rerank_updates_semantic_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reranker, "_load_model", lambda: _FakeModel())
    papers = [
        NormalizedPaper(title="A", abstract="highly relevant", semantic_score=0.1),
        NormalizedPaper(title="B", abstract="off topic", semantic_score=0.9),
    ]
    out = reranker.rerank_papers("query", papers, top_k=2)
    assert out[0].title == "A"
    assert out[0].semantic_score >= out[1].semantic_score


def test_rerank_returns_original_without_abstracts() -> None:
    papers = [NormalizedPaper(title="A", semantic_score=0.1)]
    out = reranker.rerank_papers("query", papers, top_k=1)
    assert out == papers


def test_rerank_handles_model_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise() -> object:
        raise RuntimeError()

    monkeypatch.setattr(reranker, "_load_model", _raise)
    papers = [NormalizedPaper(title="A", abstract="text", semantic_score=0.1)]
    out = reranker.rerank_papers("query", papers, top_k=1)
    assert out == papers
