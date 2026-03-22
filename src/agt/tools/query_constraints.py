"""Query constraint extraction and validation for retrieval filtering."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, model_validator

from agt.models import NormalizedPaper

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "list",
    "papers",
    "paper",
    "most",
    "more",
    "than",
    "that",
    "this",
    "from",
    "into",
    "make",
    "sure",
    "community",
    "perception",
    "good",
}


class YearConstraint(BaseModel):
    min_year: int | None = Field(default=None, ge=1900, le=2100)
    max_year: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def validate_range(self) -> YearConstraint:
        if (
            self.min_year is not None
            and self.max_year is not None
            and self.min_year > self.max_year
        ):
            raise ValueError("min_year must be <= max_year")
        return self


class CitationConstraint(BaseModel):
    min_citations: int = Field(default=0, ge=0)
    max_citations: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> CitationConstraint:
        if self.max_citations is not None and self.min_citations > self.max_citations:
            raise ValueError("min_citations must be <= max_citations")
        return self


class QualityConstraint(BaseModel):
    min_semantic_score: float = Field(default=0.0, ge=0.0)
    open_access_only: bool = False
    require_positive_community_perception: bool = False


class KeywordConstraint(BaseModel):
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class SearchConstraintSpec(BaseModel):
    raw_query: str = Field(min_length=1)
    result_limit: int = Field(default=10, ge=1, le=50)
    year: YearConstraint = Field(default_factory=YearConstraint)
    citations: CitationConstraint = Field(default_factory=CitationConstraint)
    quality: QualityConstraint = Field(default_factory=QualityConstraint)
    keywords: KeywordConstraint = Field(default_factory=KeywordConstraint)

    @model_validator(mode="after")
    def apply_quality_defaults(self) -> SearchConstraintSpec:
        if self.quality.require_positive_community_perception:
            self.citations.min_citations = max(self.citations.min_citations, 50)
            self.quality.min_semantic_score = max(self.quality.min_semantic_score, 0.2)
        return self


def _extract_keywords(query: str) -> list[str]:
    keywords: list[str] = []
    for token in _TOKEN_RE.findall(query.lower()):
        if token in _STOPWORDS:
            continue
        if token.isdigit():
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:10]


def parse_query_constraints(query: str, *, default_limit: int) -> SearchConstraintSpec:
    lowered = query.lower()

    min_year: int | None = None
    max_year: int | None = None

    newer_match = re.search(r"(?:after|since|newer than|from)\s+((?:19|20)\d{2})", lowered)
    if newer_match:
        min_year = int(newer_match.group(1))

    older_match = re.search(r"(?:before|older than|until)\s+((?:19|20)\d{2})", lowered)
    if older_match:
        max_year = int(older_match.group(1))

    in_year_match = re.search(r"(?:in|for)\s+((?:19|20)\d{2})", lowered)
    if in_year_match and min_year is None and max_year is None:
        year_value = int(in_year_match.group(1))
        min_year = year_value

    if "2026" in lowered and min_year is None:
        min_year = 2026

    min_citations = 0
    max_citations: int | None = None

    min_citation_match = re.search(
        r"(?:at least|min(?:imum)?|more than|over)\s+(\d+)\s+citations?",
        lowered,
    )
    if min_citation_match:
        value = int(min_citation_match.group(1))
        if "more than" in min_citation_match.group(0):
            value += 1
        min_citations = value

    max_citation_match = re.search(
        r"(?:at most|max(?:imum)?|under|less than)\s+(\d+)\s+citations?", lowered
    )
    if max_citation_match:
        value = int(max_citation_match.group(1))
        if "less than" in max_citation_match.group(0) or "under" in max_citation_match.group(0):
            value = max(0, value - 1)
        max_citations = value

    open_access_only = "open access" in lowered or "oa only" in lowered
    positive_community = "community perception" in lowered or "well cited" in lowered

    if "game changers" in lowered and min_citations == 0:
        min_citations = 100

    if "trending" in lowered or "trandign" in lowered:
        min_citations = max(min_citations, 20)

    years = [int(token) for token in _YEAR_RE.findall(query)]
    if years and min_year is None:
        min_year = max(years)

    return SearchConstraintSpec(
        raw_query=query,
        result_limit=default_limit,
        year=YearConstraint(min_year=min_year, max_year=max_year),
        citations=CitationConstraint(min_citations=min_citations, max_citations=max_citations),
        quality=QualityConstraint(
            min_semantic_score=0.0,
            open_access_only=open_access_only,
            require_positive_community_perception=positive_community,
        ),
        keywords=KeywordConstraint(include_keywords=_extract_keywords(query), exclude_keywords=[]),
    )


def _keyword_match(title: str, abstract: str | None, include_keywords: list[str]) -> bool:
    if not include_keywords:
        return True
    haystack = f"{title} {abstract or ''}".lower()
    return any(keyword in haystack for keyword in include_keywords)


def apply_query_constraints(
    papers: list[NormalizedPaper],
    constraints: SearchConstraintSpec,
) -> list[NormalizedPaper]:
    """Filter ranked papers using validated query constraints."""

    filtered: list[NormalizedPaper] = []
    for paper in papers:
        if constraints.year.min_year is not None and (
            paper.year is None or paper.year < constraints.year.min_year
        ):
            continue

        if constraints.year.max_year is not None and (
            paper.year is None or paper.year > constraints.year.max_year
        ):
            continue

        citation_count = paper.citation_count
        if citation_count < constraints.citations.min_citations:
            continue

        if (
            constraints.citations.max_citations is not None
            and citation_count > constraints.citations.max_citations
        ):
            continue

        if constraints.quality.open_access_only and not paper.open_access:
            continue

        if paper.semantic_score < constraints.quality.min_semantic_score:
            continue

        if not _keyword_match(paper.title, paper.abstract, constraints.keywords.include_keywords):
            continue

        filtered.append(paper)

    return filtered
