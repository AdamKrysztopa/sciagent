"""Ranking, deduplication, and stable indexing for normalized papers."""

from __future__ import annotations

import hashlib
import re

from agt.models import NormalizedPaper

_TITLE_SPACE_RE = re.compile(r"\s+")


def _normalize_title(value: str) -> str:
    return _TITLE_SPACE_RE.sub(" ", value.strip().lower())


def _normalized_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _title_author_hash(paper: NormalizedPaper) -> str:
    authors = "|".join(author.strip().lower() for author in paper.authors)
    raw = f"{_normalize_title(paper.title)}::{authors}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def deduplicate_papers(papers: list[NormalizedPaper]) -> list[NormalizedPaper]:
    """Collapse duplicates using DOI first, then title+author hash fallback."""

    by_key: dict[str, NormalizedPaper] = {}
    for paper in papers:
        doi = _normalized_doi(paper.doi)
        key = f"doi:{doi}" if doi is not None else f"title:{_title_author_hash(paper)}"
        existing = by_key.get(key)
        if existing is None or paper.semantic_score > existing.semantic_score:
            by_key[key] = paper
    return list(by_key.values())


def compute_rank_score(paper: NormalizedPaper, *, current_year: int = 2026) -> float:
    """Apply the AGT-6 scoring formula with safe handling for missing fields."""

    semantic = paper.semantic_score
    year_term = 0.0
    if paper.year is not None:
        year_term = (current_year - paper.year) * -0.3
    open_access_bonus = 0.2 if paper.open_access else 0.0
    return semantic * 0.7 + year_term + open_access_bonus


def rank_and_index_papers(
    papers: list[NormalizedPaper], *, current_year: int = 2026
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
