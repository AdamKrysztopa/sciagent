"""Optional local embedding reranker using sentence-transformers."""

# ruff: noqa: PLC0415
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import math
from functools import lru_cache

from agt.models import NormalizedPaper


@lru_cache(maxsize=1)
def _load_model() -> object:
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    return SentenceTransformer("all-MiniLM-L6-v2")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rerank_papers(query: str, papers: list[NormalizedPaper], top_k: int) -> list[NormalizedPaper]:
    """Replace semantic_score with local embedding relevance for papers with abstracts."""

    if not query.strip() or not papers:
        return papers

    candidates = [paper for paper in papers if paper.abstract and paper.abstract.strip()]
    if not candidates:
        return papers

    try:
        model = _load_model()
        query_vec = model.encode([query], normalize_embeddings=False)[0]  # type: ignore[attr-defined]
        abstract_texts = [paper.abstract or "" for paper in candidates]
        abstract_vecs = model.encode(abstract_texts, normalize_embeddings=False)  # type: ignore[attr-defined]
    except Exception:
        return papers

    score_by_id: dict[int, float] = {}
    for paper, vec in zip(candidates, abstract_vecs, strict=False):
        score_by_id[id(paper)] = max(0.0, _cosine_similarity(list(query_vec), list(vec)))

    reranked: list[NormalizedPaper] = []
    for paper in papers:
        new_score = score_by_id.get(id(paper), paper.semantic_score)
        reranked.append(paper.model_copy(update={"semantic_score": float(new_score)}))

    reranked.sort(key=lambda p: p.semantic_score, reverse=True)
    return reranked[:top_k] + [p for p in reranked[top_k:] if p not in reranked[:top_k]]
