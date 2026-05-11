"""Ranking, deduplication, and stable indexing for normalized papers."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date

from agt.models import NormalizedPaper

_TITLE_SPACE_RE = re.compile(r"\s+")
_TITLE_TOKEN_RE = re.compile(r"[^\W\d_][\w-]{3,}", re.UNICODE)
_TITLE_DIVERSITY_THRESHOLD = 0.5
_TITLE_DIVERSITY_PENALTY = 12.0
_TITLE_DIVERSITY_MEMORY = 10
_TITLE_DIVERSITY_STOPWORDS: frozenset[str] = frozenset({
    "and",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
})
_MIN_TITLE_SPECIFICITY_QUERY_TERMS = 3
_MIN_TITLE_SPECIFICITY_QUERY_HITS = 2
_MIN_TITLE_SPECIFICITY_COVERAGE = 0.75
_TITLE_SPECIFICITY_BONUS_CAP = 0.045
_TITLE_SPECIFICITY_BONUS_PER_TOKEN = 0.012
_TITLE_SPECIFICITY_STOPWORDS: frozenset[str] = _TITLE_DIVERSITY_STOPWORDS | frozenset({
    "analysis",
    "application",
    "applications",
    "approach",
    "approaches",
    "benchmark",
    "benchmarking",
    "clinical",
    "effective",
    "framework",
    "general",
    "large",
    "language",
    "learning",
    "method",
    "methods",
    "model",
    "models",
    "review",
    "survey",
    "system",
    "systems",
    "using",
})


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


def _compute_title_keyword_relevance(paper: NormalizedPaper, query_terms: list[str]) -> float:
    """Estimate how directly the title matches the query terms."""
    if not query_terms:
        return 0.0
    title = paper.title.lower()
    hits = sum(1 for term in query_terms if term.lower() in title)
    return hits / len(query_terms)


def _normalize_title(value: str) -> str:
    return _TITLE_SPACE_RE.sub(" ", value.strip().lower())


def _title_tokens(value: str) -> frozenset[str]:
    tokens = {
        token
        for token in _TITLE_TOKEN_RE.findall(value.lower())
        if token not in _TITLE_DIVERSITY_STOPWORDS
    }
    return frozenset(tokens)


def _title_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = left & right
    if not overlap:
        return 0.0
    union = left | right
    return len(overlap) / len(union)


def _title_specificity_bonus(paper: NormalizedPaper, query_terms: list[str]) -> float:
    if len(query_terms) < _MIN_TITLE_SPECIFICITY_QUERY_TERMS:
        return 0.0
    title = paper.title.lower()
    query_hits = [term.lower() for term in query_terms if term.lower() in title]
    if len(query_hits) < min(_MIN_TITLE_SPECIFICITY_QUERY_HITS, len(query_terms)):
        return 0.0
    coverage = len(query_hits) / len(query_terms)
    if coverage < _MIN_TITLE_SPECIFICITY_COVERAGE:
        return 0.0

    normalized_query_terms = {term.lower() for term in query_terms}
    extra_tokens = [
        token
        for token in _title_tokens(paper.title)
        if token not in _TITLE_SPECIFICITY_STOPWORDS
        and not any(
            token == term or token in term or term in token for term in normalized_query_terms
        )
    ]
    if not extra_tokens:
        return 0.0
    return min(_TITLE_SPECIFICITY_BONUS_CAP, len(extra_tokens) * _TITLE_SPECIFICITY_BONUS_PER_TOKEN)


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
    lexical_relevance = 0.0
    title_relevance = 0.0
    if query_terms:
        lexical_relevance = _compute_keyword_relevance(paper, query_terms)
        title_relevance = _compute_title_keyword_relevance(paper, query_terms)

    effective_semantic = semantic
    if effective_semantic == 0.0 and lexical_relevance > 0.0:
        effective_semantic = lexical_relevance

    abstract_bonus = weights.abstract_bonus if paper.abstract and paper.abstract.strip() else 0.0
    open_access_bonus = weights.open_access_bonus if paper.open_access else 0.0
    query_match_bonus = min(0.15, lexical_relevance * 0.08 + title_relevance * 0.07)
    title_specificity_bonus = _title_specificity_bonus(paper, query_terms or [])

    score = (
        effective_semantic * weights.semantic
        + citation_signal * weights.citation
        + influential_signal * weights.influential
        + recency * weights.recency
        + abstract_bonus
        + open_access_bonus
        + query_match_bonus
        + title_specificity_bonus
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
    scored: list[tuple[int, NormalizedPaper, float, frozenset[str]]] = []
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
            _title_tokens(paper.title),
        ))

    ranked_with_scores: list[tuple[int, NormalizedPaper, float]]
    if query_terms:
        remaining = list(scored)
        ranked_with_scores = []
        recent_titles: list[frozenset[str]] = []
        while remaining:
            best_idx = 0
            best_key: tuple[float, int, str, int] | None = None
            best_score = 0.0
            for idx, (original_idx, paper, base_score, title_tokens) in enumerate(remaining):
                penalty = 0.0
                for selected_tokens in recent_titles[-_TITLE_DIVERSITY_MEMORY:]:
                    similarity = _title_similarity(title_tokens, selected_tokens)
                    if similarity >= _TITLE_DIVERSITY_THRESHOLD:
                        penalty = max(penalty, _TITLE_DIVERSITY_PENALTY * similarity)
                adjusted_score = base_score - penalty
                candidate_key = (
                    adjusted_score,
                    paper.year or 0,
                    _normalize_title(paper.title),
                    -original_idx,
                )
                if best_key is None or candidate_key > best_key:
                    best_idx = idx
                    best_key = candidate_key
                    best_score = adjusted_score

            original_idx, paper, _, title_tokens = remaining.pop(best_idx)
            ranked_with_scores.append((original_idx, paper, best_score))
            recent_titles.append(title_tokens)
    else:
        ranked_with_scores = [
            (original_idx, paper, score) for original_idx, paper, score, _ in scored
        ]
        ranked_with_scores.sort(
            key=lambda item: (
                -item[2],
                -(item[1].year or 0),
                _normalize_title(item[1].title),
                item[0],
            )
        )

    ranked: list[NormalizedPaper] = []
    for index, (_, paper, score) in enumerate(ranked_with_scores):
        ranked.append(
            paper.model_copy(
                update={
                    "index": index,
                    "score": score,
                }
            )
        )
    return ranked
