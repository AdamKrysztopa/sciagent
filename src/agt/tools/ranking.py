"""Ranking, deduplication, and stable indexing for normalized papers."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date

from agt.models import NormalizedPaper

_TITLE_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class RankingWeights:
    """Normalised ranking weights. Values should sum to ≈1.0."""

    semantic: float = 0.45
    citation: float = 0.30
    influential: float = 0.10
    recency: float = 0.12
    abstract_bonus: float = 0.05
    open_access_bonus: float = 0.03


# Intent-specific weight presets ------------------------------------------

#: Default balanced weights.
WEIGHTS_DEFAULT = RankingWeights()

#: Recency-priority: user asked for "since 2024", "not older than X", "2026".
#: Boost recency, reduce citation dominance.
WEIGHTS_RECENCY = RankingWeights(
    semantic=0.40,
    citation=0.18,
    influential=0.06,
    recency=0.33,
    abstract_bonus=0.05,
    open_access_bonus=0.03,
)

#: Citation-priority: user asked for "most cited", "highly cited", "game changers".
#: Boost citation signals, keep moderate recency.
WEIGHTS_CITATION = RankingWeights(
    semantic=0.38,
    citation=0.42,
    influential=0.12,
    recency=0.05,
    abstract_bonus=0.03,
    open_access_bonus=0.02,
)


def _compute_keyword_relevance(paper: NormalizedPaper, query_terms: list[str]) -> float:
    """Estimate topic relevance for papers with no semantic score (score=0).

    Uses title + abstract keyword overlap as a proxy so that sources
    without a native relevance signal (CrossRef, BASE, Europe PMC, …)
    are not solely ranked by citation count.
    """
    if not query_terms:
        return 0.0
    text = f"{paper.title} {paper.abstract or ''}".lower()
    hits = sum(1 for term in query_terms if term.lower() in text)
    return hits / len(query_terms)


def _normalize_title(value: str) -> str:
    return _TITLE_SPACE_RE.sub(" ", value.strip().lower())


def _normalized_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalized_arxiv_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _title_author_hash(paper: NormalizedPaper) -> str:
    authors = "|".join(author.strip().lower() for author in paper.authors)
    raw = f"{_normalize_title(paper.title)}::{authors}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def deduplicate_papers(papers: list[NormalizedPaper]) -> list[NormalizedPaper]:
    """Collapse duplicates using DOI first, then arXiv ID, then title+author hash fallback."""

    by_key: dict[str, NormalizedPaper] = {}
    for paper in papers:
        doi = _normalized_doi(paper.doi)
        arxiv_id = _normalized_arxiv_id(paper.arxiv_id)
        if doi is not None:
            key = f"doi:{doi}"
        elif arxiv_id is not None:
            key = f"arxiv:{arxiv_id}"
        else:
            key = f"title:{_title_author_hash(paper)}"
        existing = by_key.get(key)
        if existing is None or paper.semantic_score > existing.semantic_score:
            by_key[key] = paper
    return list(by_key.values())


def compute_rank_score(
    paper: NormalizedPaper,
    *,
    current_year: int | None = None,
    query_terms: list[str] | None = None,
    weights: RankingWeights = WEIGHTS_DEFAULT,
) -> float:
    """Compute normalised quality score using relevance, impact, and recency signals.

    When ``query_terms`` is supplied and the paper has no semantic score (0.0),
    a lightweight keyword-overlap score is used as a relevance proxy so that
    sources without native scoring (CrossRef, BASE, Europe PMC …) are not
    dominated purely by citation count.

    ``weights`` lets callers apply intent-specific presets such as
    :data:`WEIGHTS_RECENCY` or :data:`WEIGHTS_CITATION`.
    """

    active_year = current_year if current_year is not None else date.today().year

    raw_semantic = max(0.0, paper.semantic_score)
    if raw_semantic <= 1.0:
        semantic = raw_semantic
    else:
        semantic = min(1.0, math.log1p(raw_semantic) / math.log(101.0))

    citation_signal = min(1.0, math.log1p(max(0, paper.citation_count)) / math.log(1001.0))
    influential_signal = min(
        1.0, math.log1p(max(0, paper.influential_citation_count)) / math.log(251.0)
    )

    recency = 0.0
    if paper.year is not None:
        age = max(0, active_year - paper.year)
        recency = max(0.0, 1.0 - min(age, 20) / 20.0)

    # Keyword-relevance fallback: when the paper has no semantic score (0.0)
    # and query terms are available, use keyword overlap as a relevance proxy.
    # This prevents citation count from dominating results from sources that
    # do not provide a native relevance signal (CrossRef, BASE, Europe PMC, …).
    effective_semantic = semantic
    if effective_semantic == 0.0 and query_terms:
        effective_semantic = _compute_keyword_relevance(paper, query_terms)

    abstract_bonus = weights.abstract_bonus if paper.abstract and paper.abstract.strip() else 0.0
    open_access_bonus = weights.open_access_bonus if paper.open_access else 0.0

    score = (
        effective_semantic * weights.semantic
        + citation_signal * weights.citation
        + influential_signal * weights.influential
        + recency * weights.recency
        + abstract_bonus
        + open_access_bonus
    )
    return score * 100.0


def rank_and_index_papers(
    papers: list[NormalizedPaper],
    *,
    current_year: int | None = None,
    query_terms: list[str] | None = None,
    weights: RankingWeights = WEIGHTS_DEFAULT,
) -> list[NormalizedPaper]:
    """Sort papers deterministically and assign stable 0-based indices.

    Parameters
    ----------
    query_terms:
        Cleaned topic tokens from ``SearchConstraintSpec.keywords.include_keywords``.
        Used as a relevance-proxy for sources that return no semantic score.
    weights:
        Intent-derived weight preset (e.g. :data:`WEIGHTS_RECENCY` when the
        user requested fresh results, :data:`WEIGHTS_CITATION` when they asked
        for highly-cited papers).  Defaults to :data:`WEIGHTS_DEFAULT`.
    """

    deduped = deduplicate_papers(papers)
    scored: list[tuple[int, NormalizedPaper, float]] = []
    for original_idx, paper in enumerate(deduped):
        scored.append((
            original_idx,
            paper,
            compute_rank_score(
                paper,
                current_year=current_year,
                query_terms=query_terms,
                weights=weights,
            ),
        ))

    scored.sort(
        key=lambda item: (
            -item[2],
            -(item[1].year or 0),
            _normalize_title(item[1].title),
            item[0],
        )
    )

    ranked: list[NormalizedPaper] = []
    for index, (_, paper, score) in enumerate(scored):
        ranked.append(
            paper.model_copy(
                update={
                    "index": index,
                    "score": score,
                }
            )
        )
    return ranked
