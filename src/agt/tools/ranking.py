"""Ranking, deduplication, and stable indexing for normalized papers."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import date

from agt.models import NormalizedPaper

_TITLE_SPACE_RE = re.compile(r"\s+")


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


def compute_rank_score(paper: NormalizedPaper, *, current_year: int | None = None) -> float:
    """Compute normalized quality score using relevance, impact, and recency signals."""

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

    abstract_bonus = 0.05 if paper.abstract and paper.abstract.strip() else 0.0
    open_access_bonus = 0.03 if paper.open_access else 0.0

    score = (
        semantic * 0.45
        + citation_signal * 0.30
        + influential_signal * 0.10
        + recency * 0.12
        + abstract_bonus
        + open_access_bonus
    )
    return score * 100.0


def rank_and_index_papers(
    papers: list[NormalizedPaper], *, current_year: int | None = None
) -> list[NormalizedPaper]:
    """Sort papers deterministically and assign stable 0-based indices."""

    deduped = deduplicate_papers(papers)
    scored: list[tuple[int, NormalizedPaper, float]] = []
    for original_idx, paper in enumerate(deduped):
        scored.append((original_idx, paper, compute_rank_score(paper, current_year=current_year)))

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
