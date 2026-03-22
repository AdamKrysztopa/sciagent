"""Query constraint extraction and validation for retrieval filtering."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, model_validator

from agt.config import Settings
from agt.models import NormalizedPaper

_TOKEN_RE = re.compile(r"[^\W\d_][\w-]{2,}", re.UNICODE)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_BETWEEN_YEAR_RE = re.compile(r"between\s+((?:19|20)\d{2})\s+and\s+((?:19|20)\d{2})")
_FROM_TO_YEAR_RE = re.compile(r"from\s+((?:19|20)\d{2})\s+to\s+((?:19|20)\d{2})")

# Phrases stripped from the query before keyword extraction so that
# constraint language ("after 2020", "at least 10 citations", etc.)
# never pollutes the retrieval query sent to external APIs.
_CONSTRAINT_STRIP_PATTERNS: list[re.Pattern[str]] = [
    # negated year expressions ("not older than 2024")
    re.compile(r"not\s+older\s+than\s+(?:19|20)\d{2}", re.IGNORECASE),
    # year expressions
    re.compile(
        r"(?:after|since|newer\s+than|from|before|older\s+than|until|in|for)"
        r"\s+(?:19|20)\d{2}",
        re.IGNORECASE,
    ),
    re.compile(r"(?:19|20)\d{2}\s+and\s+(?:newer|older|later|earlier)", re.IGNORECASE),
    # standalone years
    re.compile(r"\b(?:19|20)\d{2}\b"),
    # citation expressions
    re.compile(
        r"(?:at\s+least|min(?:imum)?|more\s+than|over|at\s+most|max(?:imum)?|under|less\s+than)"
        r"\s+\d+\s+citations?",
        re.IGNORECASE,
    ),
    # open access
    re.compile(r"open\s+access|oa\s+only", re.IGNORECASE),
    # community perception
    re.compile(r"community\s+perception", re.IGNORECASE),
    # limit instructions ("list 5", "top 10", "show 3")
    re.compile(r"(?:list|show|top|give|return|find|get)\s+\d+", re.IGNORECASE),
    # trailing dashes / separators left after stripping
    re.compile(r"\s*-+\s*"),
]

_STOPWORDS = {
    # generic
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "are",
    "was",
    "were",
    "been",
    "has",
    "have",
    "had",
    "does",
    "but",
    "not",
    "all",
    "any",
    "can",
    "will",
    "just",
    "about",
    # query-framing words
    "list",
    "papers",
    "paper",
    "articles",
    "article",
    "studies",
    "show",
    "find",
    "give",
    "return",
    "get",
    "search",
    "make",
    "sure",
    "please",
    # constraint / intensity words
    "most",
    "more",
    "than",
    "least",
    "less",
    "over",
    "under",
    "cited",
    "newer",
    "older",
    "latest",
    "recent",
    "recently",
    "highly",
    "well",
    "top",
    "best",
    "good",
    "great",
    "changers",
    "advanced",
    "trending",
    "trandign",
    "community",
    "perception",
    "popular",
    "influential",
    "after",
    "since",
    "before",
    "until",
    "between",
    "open",
    "access",
    "only",
    "minimum",
    "maximum",
    "min",
    "max",
    "citations",
    "citation",
    "game",
    # quotation synonyms
    "quoted",
    "highest",
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
            self.citations.min_citations = max(self.citations.min_citations, 10)
            self.quality.min_semantic_score = max(self.quality.min_semantic_score, 0.2)
        return self


def strip_constraints(query: str) -> str:
    """Remove constraint phrases so only content terms remain."""
    text = query
    for pattern in _CONSTRAINT_STRIP_PATTERNS:
        text = pattern.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _extract_keywords(query: str) -> list[str]:
    cleaned = strip_constraints(query)
    keywords: list[str] = []
    for token in _TOKEN_RE.findall(cleaned.lower()):
        if token in _STOPWORDS:
            continue
        if token.isdigit():
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:10]


def _extract_exclude_keywords(query: str) -> list[str]:
    patterns = [
        re.compile(r"not\s+about\s+([^.,;:]+)", re.IGNORECASE),
        re.compile(r"excluding\s+([^.,;:]+)", re.IGNORECASE),
        re.compile(r"but\s+not\s+([^.,;:]+)", re.IGNORECASE),
    ]
    exclude: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(query):
            phrase = match.group(1).strip().lower()
            for token in _TOKEN_RE.findall(phrase):
                if token in _STOPWORDS:
                    continue
                if token not in exclude:
                    exclude.append(token)
    return exclude[:10]


def parse_query_constraints(  # noqa: PLR0912, PLR0915
    query: str,
    *,
    default_limit: int,
    settings: Settings | None = None,
) -> SearchConstraintSpec:
    lowered = query.lower()

    min_year: int | None = None
    max_year: int | None = None

    between_match = _BETWEEN_YEAR_RE.search(lowered)
    if between_match:
        min_year = int(between_match.group(1))
        max_year = int(between_match.group(2))

    from_to_match = _FROM_TO_YEAR_RE.search(lowered)
    if from_to_match:
        min_year = int(from_to_match.group(1))
        max_year = int(from_to_match.group(2))

    newer_match = re.search(r"(?:after|since|newer\s+than|from)\s+((?:19|20)\d{2})", lowered)
    if newer_match and min_year is None:
        min_year = int(newer_match.group(1))

    # "2020 and newer" / "2020 and later"
    year_and_newer = re.search(r"((?:19|20)\d{2})\s+and\s+(?:newer|later)", lowered)
    if year_and_newer and min_year is None:
        min_year = int(year_and_newer.group(1))

    # "not older than 2024" → min_year = 2024 (negation flips the direction)
    negated_older = re.search(r"not\s+older\s+than\s+((?:19|20)\d{2})", lowered)
    if negated_older and min_year is None:
        min_year = int(negated_older.group(1))

    if not negated_older:
        older_match = re.search(r"(?:before|older\s+than|until)\s+((?:19|20)\d{2})", lowered)
        if older_match and max_year is None:
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

    most_cited_threshold = 10
    game_changers_threshold = 20
    trending_threshold = 5
    if settings is not None:
        most_cited_threshold = settings.citation_threshold_most_cited
        game_changers_threshold = settings.citation_threshold_game_changers
        trending_threshold = settings.citation_threshold_trending

    if "most cited" in lowered or "highly cited" in lowered:
        min_citations = max(min_citations, most_cited_threshold)

    if "highest quoted" in lowered or "most quoted" in lowered:
        min_citations = max(min_citations, most_cited_threshold)

    if "game changers" in lowered and min_citations == 0:
        min_citations = game_changers_threshold

    if "trending" in lowered or "trandign" in lowered:
        min_citations = max(min_citations, trending_threshold)

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
        keywords=KeywordConstraint(
            include_keywords=_extract_keywords(query),
            exclude_keywords=_extract_exclude_keywords(query),
        ),
    )


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

        if constraints.keywords.exclude_keywords:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            if any(keyword in text for keyword in constraints.keywords.exclude_keywords):
                continue

        filtered.append(paper)

    return filtered
