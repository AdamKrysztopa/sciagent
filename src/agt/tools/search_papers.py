"""Paper search tool adapter."""

# ruff: noqa: PLR0913

from __future__ import annotations

import asyncio
import re
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from agt.config import Settings, get_settings
from agt.guardrails import current_thread_id, get_guardrails
from agt.models import (
    FilterEditContract,
    HardFilters,
    NormalizedPaper,
    SearchMetadata,
    SearchPlan,
    SoftPreferences,
    SourceCapability,
)
from agt.providers.protocol import LLMProvider
from agt.tools.arxiv_api import ArxivClient
from agt.tools.base_search import BaseSearchClient
from agt.tools.core_ac import CoreClient
from agt.tools.crossref import CrossrefClient
from agt.tools.dimensions import DimensionsClient
from agt.tools.europe_pmc import EuropePMCClient
from agt.tools.google_scholar import GoogleScholarClient
from agt.tools.keyword_extractor import extract_keywords
from agt.tools.openalex import OpenAlexClient
from agt.tools.opencitations import OpenCitationsClient
from agt.tools.pubmed import PubMedClient
from agt.tools.query_constraints import (
    CitationConstraint,
    KeywordConstraint,
    QualityConstraint,
    SearchConstraintSpec,
    YearConstraint,
    apply_query_constraints,
    parse_query_constraints,
)
from agt.tools.query_rewriter import RewrittenQuery, rewrite_query, validate_results
from agt.tools.ranking import (
    WEIGHTS_CITATION,
    WEIGHTS_DEFAULT,
    WEIGHTS_RECENCY,
    RankingWeights,
    rank_and_index_papers,
)
from agt.tools.reranker import rerank_papers
from agt.tools.semantic_scholar import SemanticScholarClient, SemanticScholarResponseError
from agt.tools.spell_check import correct_query

_MIN_KEYWORD_QUERY_LEN = 3
_OVER_FETCH_MULTIPLIER = 3
_MAX_FETCH_LIMIT = 30
_MAX_RESULT_LIMIT = 50
_WAIT_TOKEN_TIMEOUT_SECONDS = 1.5
_MAX_EXPANSION_KEYWORD_COUNT = 6
_EXPANSION_PREFIX_KEYWORD_COUNT = 4
_SINGLE_KEYWORD_MIN_LEN = 6
_SINGULARIZE_MIN_LEN = 4
_MAX_REFINEMENT_BASE_KEYWORDS = 2
_MIN_REFINEMENT_TOKEN_LEN = 5
_MIN_REFINEMENT_SUPPORT = 2
_TITLE_QUERY_TOKEN_RE = re.compile(r"[^\W\d_][\w-]{3,}", re.UNICODE)
_SINGLE_KEYWORD_STOPWORDS: frozenset[str] = frozenset({
    "analysis",
    "application",
    "applications",
    "effects",
    "learning",
    "mechanism",
    "method",
    "methods",
    "model",
    "models",
    "network",
    "networks",
    "prediction",
    "review",
    "survey",
    "system",
    "systems",
})
_EXPANSION_TRIGGER_KEYWORDS: frozenset[str] = frozenset({
    "analysis",
    "application",
    "applications",
    "effects",
    "learning",
    "mechanism",
    "method",
    "methods",
    "prediction",
    "review",
    "survey",
})
_REFINEMENT_STOPWORDS: frozenset[str] = _SINGLE_KEYWORD_STOPWORDS | frozenset({
    "advances",
    "approach",
    "approaches",
    "benchmark",
    "effective",
    "general",
    "large",
    "paper",
    "papers",
    "pretrained",
    "recent",
    "study",
    "studies",
    "task",
    "tasks",
    "using",
})
_MAX_SINGLE_KEYWORD_VARIANTS = 2
_MAX_REFINEMENT_TOKENS = 2

ProgressReporter = Callable[[str], None]


@dataclass(slots=True)
class _SourceFetchResult:
    name: str
    papers: list[NormalizedPaper]
    failure: str | None
    used: bool
    timing_seconds: float


@dataclass(slots=True)
class _RetrievalProvider:
    name: str
    tier: Literal["primary", "fallback"]
    enabled: bool
    fetcher: Callable[[], Awaitable[list[NormalizedPaper]]]


def _emit_progress(progress: ProgressReporter | None, message: str) -> None:
    if progress is not None:
        progress(message)


async def _fetch_one_source(
    service_name: str,
    source_name: str,
    thread_id: str,
    fetcher: Awaitable[list[NormalizedPaper]],
) -> _SourceFetchResult:
    guardrails = get_guardrails()
    start = time.monotonic()
    has_token = await guardrails.wait_for_token(
        service=service_name,
        thread_id=thread_id,
        timeout_seconds=_WAIT_TOKEN_TIMEOUT_SECONDS,
    )
    if not has_token:
        return _SourceFetchResult(
            name=source_name,
            papers=[],
            failure=f"{source_name}: rate limit wait timeout",
            used=True,
            timing_seconds=time.monotonic() - start,
        )

    try:
        papers = await fetcher
        labeled = [paper.model_copy(update={"source": source_name}) for paper in papers]
        return _SourceFetchResult(
            name=source_name,
            papers=labeled,
            failure=None,
            used=True,
            timing_seconds=time.monotonic() - start,
        )
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        return _SourceFetchResult(
            name=source_name,
            papers=[],
            failure=f"{source_name}: {exc}",
            used=True,
            timing_seconds=time.monotonic() - start,
        )


def _build_retrieval_registry(
    query: str,
    limit: int,
    constraints: SearchConstraintSpec,
    settings: Settings,
    rewritten: RewrittenQuery | None,
) -> list[_RetrievalProvider]:
    semantic_api_key = None
    if settings.semantic_scholar_api_key is not None:
        semantic_api_key = settings.semantic_scholar_api_key.get_secret_value()

    ncbi_api_key = None
    if settings.ncbi_api_key is not None:
        ncbi_api_key = settings.ncbi_api_key.get_secret_value()

    pubmed_query = rewritten.pubmed_query if rewritten and rewritten.pubmed_query else query
    arxiv_categories = rewritten.arxiv_categories if rewritten else []

    semantic_client = SemanticScholarClient(
        api_key=semantic_api_key,
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    openalex_client = OpenAlexClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    crossref_client = CrossrefClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    pubmed_client = PubMedClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
        api_key=ncbi_api_key,
    )
    europe_pmc_client = EuropePMCClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    arxiv_client = ArxivClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    base_client = BaseSearchClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )

    registry: list[_RetrievalProvider] = [
        _RetrievalProvider(
            name="semantic_scholar",
            tier="primary",
            enabled=True,
            fetcher=lambda: semantic_client.search(
                query=query,
                limit=limit,
                year_min=constraints.year.min_year,
                year_max=constraints.year.max_year,
                max_pages=settings.search_max_pages,
            ),
        ),
        _RetrievalProvider(
            name="openalex",
            tier="primary",
            enabled=True,
            fetcher=lambda: openalex_client.search(
                query=query,
                limit=limit,
                year_min=constraints.year.min_year,
                max_pages=settings.search_max_pages,
            ),
        ),
        _RetrievalProvider(
            name="crossref",
            tier="primary",
            enabled=True,
            fetcher=lambda: crossref_client.search(
                query=query,
                limit=limit,
                max_pages=settings.search_max_pages,
            ),
        ),
        _RetrievalProvider(
            name="pubmed",
            tier="primary",
            enabled=True,
            fetcher=lambda: pubmed_client.search(query=pubmed_query, limit=limit),
        ),
        _RetrievalProvider(
            name="europe_pmc",
            tier="primary",
            enabled=True,
            fetcher=lambda: europe_pmc_client.search(query=query, limit=limit),
        ),
        _RetrievalProvider(
            name="arxiv",
            tier="primary",
            enabled=True,
            fetcher=lambda: arxiv_client.search(
                query=query,
                limit=limit,
                categories=arxiv_categories,
            ),
        ),
        _RetrievalProvider(
            name="base",
            tier="primary",
            enabled=True,
            fetcher=lambda: base_client.search(query=query, limit=limit),
        ),
    ]

    if settings.core_api_key is not None:
        core_client = CoreClient(
            api_key=settings.core_api_key.get_secret_value(),
            timeout_seconds=settings.semantic_scholar_timeout_seconds,
            retries=settings.semantic_scholar_retries,
        )
        registry.append(
            _RetrievalProvider(
                name="core",
                tier="fallback",
                enabled=True,
                fetcher=lambda: core_client.search(query=query, limit=limit),
            )
        )

    if settings.dimensions_key is not None:
        dimensions_client = DimensionsClient(
            api_key=settings.dimensions_key.get_secret_value(),
            timeout_seconds=settings.semantic_scholar_timeout_seconds,
            retries=settings.semantic_scholar_retries,
        )
        registry.append(
            _RetrievalProvider(
                name="dimensions",
                tier="fallback",
                enabled=True,
                fetcher=lambda: dimensions_client.search(query=query, limit=limit),
            )
        )

    if settings.serpapi_key is not None:
        google_client = GoogleScholarClient(
            api_key=settings.serpapi_key.get_secret_value(),
            timeout_seconds=settings.semantic_scholar_timeout_seconds,
            retries=settings.semantic_scholar_retries,
        )
        registry.append(
            _RetrievalProvider(
                name="google_scholar",
                tier="fallback",
                enabled=True,
                fetcher=lambda: google_client.search(query=query, limit=limit),
            )
        )

    return registry


async def _fetch_from_sources(
    query: str,
    limit: int,
    constraints: SearchConstraintSpec,
    settings: Settings,
    thread_id: str,
    rewritten: RewrittenQuery | None,
    *,
    tier: Literal["primary", "fallback", "all"] = "all",
) -> tuple[list[NormalizedPaper], list[str], list[str], dict[str, float]]:
    """Fetch papers from configured academic sources in parallel."""

    results: list[NormalizedPaper] = []
    failures: list[str] = []
    sources_used: list[str] = []
    timings: dict[str, float] = {}

    registry = _build_retrieval_registry(query, limit, constraints, settings, rewritten)

    source_tasks: list[asyncio.Task[_SourceFetchResult]] = []
    for provider in registry:
        if not provider.enabled:
            continue
        if tier not in ("all", provider.tier):
            continue
        source_name = f"{provider.name}:{provider.tier}"
        source_tasks.append(
            asyncio.create_task(
                _fetch_one_source(provider.name, source_name, thread_id, provider.fetcher())
            )
        )

    fetched = await asyncio.gather(*source_tasks)
    for item in fetched:
        if item.used:
            sources_used.append(item.name)
        timings[item.name] = timings.get(item.name, 0.0) + item.timing_seconds
        if item.failure is not None:
            failures.append(item.failure)
        results.extend(item.papers)

    return results, failures, sources_used, timings


async def _fetch_query_with_optional_fallback(
    query: str,
    fetch_limit: int,
    constraints: SearchConstraintSpec,
    settings: Settings,
    thread_id: str,
    rewritten: RewrittenQuery | None,
    fallback_mode: Literal["auto", "force", "off"],
    capped_limit: int,
    corrected_query: str,
    progress: ProgressReporter | None = None,
) -> tuple[list[NormalizedPaper], list[str], list[str], dict[str, float]]:
    results: list[NormalizedPaper] = []
    failures: list[str] = []
    sources_used: list[str] = []
    timings: dict[str, float] = {}

    _emit_progress(progress, "retrieving primary sources")
    primary_results, primary_failures, primary_sources, primary_timings = await _fetch_from_sources(
        query,
        fetch_limit,
        constraints,
        settings,
        thread_id,
        rewritten,
        tier="primary",
    )
    results.extend(primary_results)
    failures.extend(primary_failures)
    sources_used.extend(primary_sources)
    timings.update(primary_timings)

    should_fetch_fallback = fallback_mode == "force"
    if fallback_mode == "auto":
        if not primary_results:
            should_fetch_fallback = True
        else:
            primary_enriched = await _enrich_citations(
                primary_results,
                settings=settings,
                thread_id=thread_id,
            )
            primary_filtered = _rank_and_filter(
                primary_enriched,
                constraints,
                capped_limit,
                settings=settings,
                query=corrected_query,
            )
            should_fetch_fallback = len(primary_filtered) < capped_limit

    if should_fetch_fallback:
        _emit_progress(progress, "retrieving fallback sources")
        (
            fallback_results,
            fallback_failures,
            fallback_sources,
            fallback_timings,
        ) = await _fetch_from_sources(
            query,
            fetch_limit,
            constraints,
            settings,
            thread_id,
            rewritten,
            tier="fallback",
        )
        results.extend(fallback_results)
        failures.extend(fallback_failures)
        for source in fallback_sources:
            if source not in sources_used:
                sources_used.append(source)
        for source, value in fallback_timings.items():
            timings[source] = timings.get(source, 0.0) + value

    return results, failures, sources_used, timings


async def _enrich_citations(
    papers: list[NormalizedPaper],
    *,
    settings: Settings,
    thread_id: str,
) -> list[NormalizedPaper]:
    """Enrich citation_count using OpenCitations COCI for DOI-bearing papers."""

    dois = sorted({paper.doi.strip() for paper in papers if paper.doi and paper.doi.strip()})
    if not dois:
        return papers

    client = OpenCitationsClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    guardrails = get_guardrails()

    async def _fetch_count(doi: str) -> tuple[str, int | None]:
        has_token = await guardrails.wait_for_token(
            service="opencitations",
            thread_id=thread_id,
            timeout_seconds=_WAIT_TOKEN_TIMEOUT_SECONDS,
        )
        if not has_token:
            return doi, None
        try:
            return doi, await client.citation_count(doi)
        except Exception:
            return doi, None

    doi_counts = await asyncio.gather(*[_fetch_count(doi) for doi in dois])
    count_by_doi = {doi.lower(): count for doi, count in doi_counts if count is not None}

    enriched: list[NormalizedPaper] = []
    for paper in papers:
        doi = paper.doi.strip().lower() if paper.doi else None
        if doi is None or doi not in count_by_doi:
            enriched.append(paper)
            continue
        count = count_by_doi[doi]
        if count <= paper.citation_count:
            enriched.append(paper)
            continue
        enriched.append(paper.model_copy(update={"citation_count": int(count)}))

    return enriched


def _intent_weights(constraints: SearchConstraintSpec) -> RankingWeights:
    """Derive ranking weights from parsed query intent.

    - Year constraint active → recency-priority preset (reduces citation dominance
      so a 2024 Chemistry textbook does not beat a fresh time-series paper).
    - Citation constraint active → citation-priority preset.
    - Both active or neither → default balanced weights.
    """
    has_year = constraints.year.min_year is not None or constraints.year.max_year is not None
    has_citation = constraints.citations.min_citations > 0
    if has_year and not has_citation:
        return WEIGHTS_RECENCY
    if has_citation and not has_year:
        return WEIGHTS_CITATION
    return WEIGHTS_DEFAULT


def _rank_and_filter(
    results: list[NormalizedPaper],
    constraints: SearchConstraintSpec,
    capped_limit: int,
    *,
    settings: Settings,
    query: str,
    query_terms: list[str] | None = None,
) -> list[NormalizedPaper]:
    """Rank, apply constraints, and index a result set."""

    rerank_input = results
    if settings.use_reranker:
        rerank_input = rerank_papers(query=query, papers=results, top_k=len(results))

    ranked = rank_and_index_papers(
        rerank_input,
        query_terms=query_terms
        if query_terms is not None
        else constraints.keywords.include_keywords,
        weights=_intent_weights(constraints),
    )
    filtered = apply_query_constraints(ranked, constraints)
    for index, paper in enumerate(filtered):
        paper.index = index
    return filtered[:capped_limit]


def _build_regex_query(
    constraints: SearchConstraintSpec,
    raw_query: str,
    settings: Settings,
) -> str:
    """Build a retrieval query from extracted keywords (fallback path)."""

    if settings.use_keybert:
        keywords = extract_keywords(raw_query)
        if keywords:
            keyword_query = " ".join(keywords)
            if len(keyword_query) >= _MIN_KEYWORD_QUERY_LEN:
                return keyword_query

    keyword_query = " ".join(constraints.keywords.include_keywords)
    return keyword_query if len(keyword_query) >= _MIN_KEYWORD_QUERY_LEN else raw_query


def _append_unique_query(queries: list[str], query: str) -> None:
    normalized = " ".join(query.split()).strip()
    if not normalized or normalized in queries:
        return
    queries.append(normalized)


def _build_deterministic_query_variants(
    constraints: SearchConstraintSpec,
    primary_query: str,
) -> list[str]:
    queries: list[str] = []
    _append_unique_query(queries, primary_query)

    keywords = constraints.keywords.include_keywords
    should_expand = len(keywords) <= _MAX_EXPANSION_KEYWORD_COUNT and any(
        keyword in _EXPANSION_TRIGGER_KEYWORDS for keyword in keywords
    )
    if should_expand and len(keywords) >= _EXPANSION_PREFIX_KEYWORD_COUNT:
        for prefix_size in (2, 3):
            _append_unique_query(queries, " ".join(keywords[:prefix_size]))

    if should_expand and len(keywords) == _EXPANSION_PREFIX_KEYWORD_COUNT:
        single_keyword_candidates = [
            keyword
            for keyword in keywords[1:-1]
            if len(keyword) >= _SINGLE_KEYWORD_MIN_LEN and keyword not in _SINGLE_KEYWORD_STOPWORDS
        ]
        for keyword in single_keyword_candidates[:_MAX_SINGLE_KEYWORD_VARIANTS]:
            _append_unique_query(queries, keyword)

    return queries


def _normalize_query_token(token: str) -> str:
    lowered = token.lower()
    if lowered.endswith("s") and len(lowered) > _SINGULARIZE_MIN_LEN:
        lowered = lowered[:-1]
    return lowered


def _merge_ranking_terms(existing_terms: list[str], query: str) -> list[str]:
    merged = list(existing_terms)
    for raw_token in _TITLE_QUERY_TOKEN_RE.findall(query.lower()):
        token = _normalize_query_token(raw_token)
        if token not in merged:
            merged.append(token)
    return merged


def _build_refinement_query(
    papers: list[NormalizedPaper],
    constraints: SearchConstraintSpec,
) -> str | None:
    keywords = [
        _normalize_query_token(keyword) for keyword in constraints.keywords.include_keywords
    ]
    if len(keywords) > _MAX_REFINEMENT_BASE_KEYWORDS:
        return None

    token_counts: Counter[str] = Counter()
    for paper in papers[:10]:
        seen_tokens: set[str] = set()
        text = f"{paper.title} {paper.abstract or ''}"
        for raw_token in _TITLE_QUERY_TOKEN_RE.findall(text.lower()):
            token = _normalize_query_token(raw_token)
            if len(token) < _MIN_REFINEMENT_TOKEN_LEN:
                continue
            if token in keywords or token in _REFINEMENT_STOPWORDS:
                continue
            if token in seen_tokens:
                continue
            seen_tokens.add(token)
            token_counts[token] += 1

    refinement_terms = [
        token
        for token, count in sorted(
            token_counts.items(),
            key=lambda item: (-item[1], -len(item[0]), item[0]),
        )
        if count >= _MIN_REFINEMENT_SUPPORT
    ][:_MAX_REFINEMENT_TOKENS]
    if not refinement_terms:
        return None

    refinement_query = " ".join([*constraints.keywords.include_keywords, *refinement_terms])
    normalized = " ".join(refinement_query.split()).strip()
    return normalized or None


def _apply_filter_edit(
    constraints: SearchConstraintSpec,
    filter_edit: FilterEditContract,
) -> SearchConstraintSpec:
    hard_filter_fields = filter_edit.hard_filters.model_fields_set
    soft_preference_fields = filter_edit.soft_preferences.model_fields_set

    include_keywords = (
        list(filter_edit.hard_filters.include_keywords)
        if "include_keywords" in hard_filter_fields
        else list(constraints.keywords.include_keywords)
    )
    exclude_keywords = (
        list(filter_edit.hard_filters.exclude_keywords)
        if "exclude_keywords" in hard_filter_fields
        else list(constraints.keywords.exclude_keywords)
    )

    raw_query = constraints.raw_query
    if "include_keywords" in hard_filter_fields:
        raw_query = " ".join(include_keywords) if include_keywords else filter_edit.original_query

    return SearchConstraintSpec(
        raw_query=raw_query,
        result_limit=(
            filter_edit.result_limit
            if "result_limit" in filter_edit.model_fields_set
            else constraints.result_limit
        ),
        year=YearConstraint(
            min_year=(
                filter_edit.hard_filters.min_year
                if "min_year" in hard_filter_fields
                else constraints.year.min_year
            ),
            max_year=(
                filter_edit.hard_filters.max_year
                if "max_year" in hard_filter_fields
                else constraints.year.max_year
            ),
        ),
        citations=CitationConstraint(
            min_citations=(
                filter_edit.hard_filters.min_citations
                if "min_citations" in hard_filter_fields
                else constraints.citations.min_citations
            ),
            max_citations=(
                filter_edit.hard_filters.max_citations
                if "max_citations" in hard_filter_fields
                else constraints.citations.max_citations
            ),
        ),
        quality=QualityConstraint(
            min_semantic_score=(
                filter_edit.soft_preferences.min_semantic_score
                if "min_semantic_score" in soft_preference_fields
                else constraints.quality.min_semantic_score
            ),
            open_access_only=(
                filter_edit.hard_filters.open_access_only
                if "open_access_only" in hard_filter_fields
                else constraints.quality.open_access_only
            ),
            require_positive_community_perception=(
                filter_edit.soft_preferences.require_positive_community_perception
                if "require_positive_community_perception" in soft_preference_fields
                else constraints.quality.require_positive_community_perception
            ),
        ),
        keywords=KeywordConstraint(
            include_keywords=include_keywords,
            exclude_keywords=exclude_keywords,
        ),
    )


# Static capability table: which filters each source pushes down to its API.
_SOURCE_PUSH_DOWN: dict[str, list[str]] = {
    "semantic_scholar": ["year_min", "year_max"],
    "openalex": ["year_min"],
    "crossref": [],
    "pubmed": [],
    "europe_pmc": [],
    "arxiv": [],
    "base": [],
    "core": [],
    "dimensions": [],
    "google_scholar": [],
}

_SOURCE_SUPPORTS_YEAR: frozenset[str] = frozenset({"semantic_scholar", "openalex"})
_SOURCE_SUPPORTS_OA: frozenset[str] = frozenset()

_PRIMARY_SOURCE_NAMES: list[str] = [
    "semantic_scholar",
    "openalex",
    "crossref",
    "pubmed",
    "europe_pmc",
    "arxiv",
    "base",
]


def build_source_policy(settings: Settings) -> list[SourceCapability]:
    """Build the full source capability list from current settings.

    This is the same logic used internally by _build_search_plan, exposed here
    so the /capabilities API endpoint can serve it without running a search.
    """
    fallback_names: list[str] = []
    if settings.core_api_key is not None:
        fallback_names.append("core")
    if settings.dimensions_key is not None:
        fallback_names.append("dimensions")
    if settings.serpapi_key is not None:
        fallback_names.append("google_scholar")

    result: list[SourceCapability] = []
    for name in _PRIMARY_SOURCE_NAMES:
        result.append(
            SourceCapability(
                name=name,
                tier="primary",
                enabled=True,
                supports_year_filter=name in _SOURCE_SUPPORTS_YEAR,
                supports_open_access_filter=name in _SOURCE_SUPPORTS_OA,
            )
        )
    for name in fallback_names:
        result.append(
            SourceCapability(
                name=name,
                tier="fallback",
                enabled=True,
                supports_year_filter=name in _SOURCE_SUPPORTS_YEAR,
                supports_open_access_filter=name in _SOURCE_SUPPORTS_OA,
            )
        )
    return result


def _build_search_plan(
    original_query: str,
    topic_query: str,
    rewritten_queries: list[str],
    constraints: SearchConstraintSpec,
    settings: Settings,
    rewritten: RewrittenQuery | None,
) -> SearchPlan:
    """Build a typed SearchPlan before retrieval begins (AGT-28)."""

    hard_filters = HardFilters(
        min_year=constraints.year.min_year,
        max_year=constraints.year.max_year,
        min_citations=constraints.citations.min_citations,
        max_citations=constraints.citations.max_citations,
        open_access_only=constraints.quality.open_access_only,
        include_keywords=list(constraints.keywords.include_keywords),
        exclude_keywords=list(constraints.keywords.exclude_keywords),
    )
    soft_preferences = SoftPreferences(
        require_positive_community_perception=constraints.quality.require_positive_community_perception,
        min_semantic_score=constraints.quality.min_semantic_score,
    )

    source_policy = build_source_policy(settings)
    all_source_names = [s.name for s in source_policy]

    # Determine which filters were pushed down per source.
    active_push_down: dict[str, list[str]] = {}
    for name in all_source_names:
        pushed: list[str] = []
        for filter_name in _SOURCE_PUSH_DOWN.get(name, []):
            if (filter_name == "year_min" and constraints.year.min_year is not None) or (
                filter_name == "year_max" and constraints.year.max_year is not None
            ):
                pushed.append(filter_name)
        if pushed:
            active_push_down[name] = pushed

    # Post-merge filters are all hard filters not pushed down at the source level.
    enforced_post_merge: list[str] = []
    if constraints.year.min_year is not None:
        enforced_post_merge.append("year_min")
    if constraints.year.max_year is not None:
        enforced_post_merge.append("year_max")
    if constraints.citations.min_citations > 0:
        enforced_post_merge.append("min_citations")
    if constraints.citations.max_citations is not None:
        enforced_post_merge.append("max_citations")
    if constraints.quality.open_access_only:
        enforced_post_merge.append("open_access_only")
    if constraints.quality.min_semantic_score > 0.0:
        enforced_post_merge.append("min_semantic_score")
    if constraints.keywords.exclude_keywords:
        enforced_post_merge.append("exclude_keywords")
    if constraints.keywords.include_keywords:
        enforced_post_merge.append("topic_relevance")

    return SearchPlan(
        original_query=original_query,
        topic_query=topic_query,
        rewritten_queries=rewritten_queries,
        hard_filters=hard_filters,
        soft_preferences=soft_preferences,
        source_policy=source_policy,
        filters_pushed_down=active_push_down,
        filters_enforced_post_merge=enforced_post_merge,
    )


async def search_papers(  # noqa: PLR0912, PLR0915
    query: str,
    limit: int = 10,
    *,
    settings: Settings | None = None,
    thread_id: str | None = None,
    provider: LLMProvider | None = None,
    fallback_mode: Literal["auto", "force", "off"] | None = None,
    progress: ProgressReporter | None = None,
    filter_edit: FilterEditContract | None = None,
) -> tuple[list[NormalizedPaper], SearchMetadata]:
    """Search multiple academic sources and return ranked normalized papers + metadata."""

    if not query.strip():
        return [], SearchMetadata(
            original_query=query,
            rewritten_query=None,
            regex_query=query,
            mode="regex",
        )

    active_settings = settings or get_settings()
    active_thread = thread_id or current_thread_id()
    effective_fallback_mode: Literal["auto", "force", "off"]
    if fallback_mode is not None:
        effective_fallback_mode = fallback_mode
    else:
        effective_fallback_mode = "auto" if active_settings.enable_fallback_retrieval else "off"

    corrected_query = query
    if active_settings.use_spell_check:
        corrected_query = correct_query(query)

    capped_limit = min(limit, _MAX_RESULT_LIMIT)
    constraints = parse_query_constraints(
        corrected_query,
        default_limit=capped_limit,
        settings=active_settings,
    )
    if filter_edit is not None:
        constraints = _apply_filter_edit(constraints, filter_edit)
        capped_limit = min(constraints.result_limit, _MAX_RESULT_LIMIT)
    fetch_limit = min(capped_limit * _OVER_FETCH_MULTIPLIER, _MAX_FETCH_LIMIT)

    regex_query = _build_regex_query(constraints, corrected_query, active_settings)
    # In no-LLM mode use the cleaned keyword query for retrieval so that constraint
    # language ("most cited", "list 5", "and newer") never pollutes API requests.
    # When an LLM is available its rewritten query takes precedence.
    retrieval_query = regex_query
    topic = ""
    mode: str = "regex"
    rewritten: RewrittenQuery | None = None

    if provider is not None:
        try:
            _emit_progress(progress, "rewriting query with LLM")
            rewritten = await rewrite_query(corrected_query, provider)
            retrieval_query = rewritten.search_query
            topic = rewritten.topic
            mode = "llm_rewrite"
        except Exception:
            retrieval_query = regex_query
            topic = ""

    retrieval_queries: list[str]
    if rewritten and rewritten.synonyms:
        retrieval_queries = [retrieval_query]
        for synonym in rewritten.synonyms:
            if synonym and synonym != retrieval_query:
                _append_unique_query(retrieval_queries, synonym)
    else:
        retrieval_queries = _build_deterministic_query_variants(constraints, regex_query)

    # Build the typed SearchPlan now that we have all query derivations (AGT-28).
    plan = _build_search_plan(
        original_query=query,
        topic_query=topic or corrected_query,
        rewritten_queries=retrieval_queries,
        constraints=constraints,
        settings=active_settings,
        rewritten=rewritten,
    )

    all_failures: list[str] = []
    all_sources_used: list[str] = []
    all_timings: dict[str, float] = {}
    retry_count = 0
    executed_queries: set[str] = set()
    ranking_terms = list(constraints.keywords.include_keywords)

    def _merge_telemetry(
        failures: list[str],
        sources_used: list[str],
        timings: dict[str, float],
    ) -> None:
        all_failures.extend(failures)
        for source in sources_used:
            if source not in all_sources_used:
                all_sources_used.append(source)
        for source, value in timings.items():
            all_timings[source] = all_timings.get(source, 0.0) + value

    results: list[NormalizedPaper] = []
    for index, active_query in enumerate(retrieval_queries):
        if active_query in executed_queries:
            continue
        if index > 0:
            _emit_progress(progress, "retrieving query expansion")
        executed_queries.add(active_query)
        ranking_terms = _merge_ranking_terms(ranking_terms, active_query)
        query_results, failures, sources_used, timings = await _fetch_query_with_optional_fallback(
            active_query,
            fetch_limit,
            constraints,
            active_settings,
            active_thread,
            rewritten,
            effective_fallback_mode,
            capped_limit,
            corrected_query,
            progress,
        )
        results.extend(query_results)
        _merge_telemetry(failures, sources_used, timings)

    if provider is None and results:
        preliminary = _rank_and_filter(
            results,
            constraints,
            capped_limit,
            settings=active_settings,
            query=corrected_query,
            query_terms=ranking_terms,
        )
        refinement_query = _build_refinement_query(preliminary, constraints)
        if refinement_query is not None and refinement_query not in executed_queries:
            _emit_progress(progress, "retrieving broad-query refinement")
            executed_queries.add(refinement_query)
            ranking_terms = _merge_ranking_terms(ranking_terms, refinement_query)
            (
                refinement_results,
                refinement_failures,
                refinement_sources,
                refinement_timings,
            ) = await _fetch_query_with_optional_fallback(
                refinement_query,
                fetch_limit,
                constraints,
                active_settings,
                active_thread,
                rewritten,
                effective_fallback_mode,
                capped_limit,
                corrected_query,
                progress,
            )
            results.extend(refinement_results)
            _merge_telemetry(refinement_failures, refinement_sources, refinement_timings)

    if results:
        _emit_progress(progress, "enriching citations")
        results = await _enrich_citations(
            results, settings=active_settings, thread_id=active_thread
        )
        _emit_progress(progress, "reranking and filtering merged results")
        filtered = _rank_and_filter(
            results,
            constraints,
            capped_limit,
            settings=active_settings,
            query=corrected_query,
            query_terms=ranking_terms,
        )

        if provider is not None and filtered and topic:
            try:
                validation = await validate_results(corrected_query, topic, filtered, provider)
                if not validation.is_relevant and validation.suggested_query:
                    retry_count += 1
                    _emit_progress(progress, "retrying with relevance-guided query")
                    (
                        retry_results,
                        retry_failures,
                        retry_sources,
                        retry_timings,
                    ) = await _fetch_query_with_optional_fallback(
                        validation.suggested_query,
                        fetch_limit,
                        constraints,
                        active_settings,
                        active_thread,
                        rewritten,
                        effective_fallback_mode,
                        capped_limit,
                        corrected_query,
                        progress,
                    )
                    _merge_telemetry(retry_failures, retry_sources, retry_timings)
                    if retry_results:
                        _emit_progress(progress, "enriching citations")
                        retry_results = await _enrich_citations(
                            retry_results,
                            settings=active_settings,
                            thread_id=active_thread,
                        )
                        _emit_progress(progress, "reranking and filtering merged results")
                        retry_filtered = _rank_and_filter(
                            retry_results,
                            constraints,
                            capped_limit,
                            settings=active_settings,
                            query=corrected_query,
                            query_terms=ranking_terms,
                        )
                        if retry_filtered:
                            filtered = retry_filtered
            except Exception:
                pass

        if filtered:
            metadata = SearchMetadata(
                original_query=query,
                rewritten_query=retrieval_query if retrieval_query != corrected_query else None,
                regex_query=regex_query,
                sources_used=all_sources_used,
                sources_failed=all_failures,
                mode="llm_rewrite" if mode == "llm_rewrite" else "regex",
                retry_count=retry_count,
                total_fetched=len(results),
                total_after_filter=len(filtered),
                source_timings=all_timings,
                search_plan=plan,
            )
            return filtered, metadata

    if retrieval_query != regex_query:
        _emit_progress(progress, "retrying with deterministic keyword query")
        (
            fallback_results,
            fallback_failures,
            fallback_sources,
            fallback_timings,
        ) = await _fetch_query_with_optional_fallback(
            regex_query,
            fetch_limit,
            constraints,
            active_settings,
            active_thread,
            None,
            effective_fallback_mode,
            capped_limit,
            corrected_query,
            progress,
        )
        _merge_telemetry(fallback_failures, fallback_sources, fallback_timings)
        if fallback_results:
            _emit_progress(progress, "enriching citations")
            fallback_results = await _enrich_citations(
                fallback_results,
                settings=active_settings,
                thread_id=active_thread,
            )
            _emit_progress(progress, "reranking and filtering merged results")
            filtered = _rank_and_filter(
                fallback_results,
                constraints,
                capped_limit,
                settings=active_settings,
                query=corrected_query,
                query_terms=ranking_terms,
            )
            if filtered:
                metadata = SearchMetadata(
                    original_query=query,
                    rewritten_query=retrieval_query if retrieval_query != corrected_query else None,
                    regex_query=regex_query,
                    sources_used=all_sources_used,
                    sources_failed=all_failures,
                    mode="llm_rewrite" if mode == "llm_rewrite" else "regex",
                    retry_count=retry_count,
                    total_fetched=len(fallback_results),
                    total_after_filter=len(filtered),
                    source_timings=all_timings,
                    search_plan=plan,
                )
                return filtered, metadata
        if not results:
            results = fallback_results

    if not results:
        failure_text = "; ".join(all_failures) if all_failures else "no sources returned any papers"
        raise SemanticScholarResponseError(f"all retrieval providers failed: {failure_text}")

    metadata = SearchMetadata(
        original_query=query,
        rewritten_query=retrieval_query if retrieval_query != corrected_query else None,
        regex_query=regex_query,
        sources_used=all_sources_used,
        sources_failed=all_failures,
        mode="llm_rewrite" if mode == "llm_rewrite" else "regex",
        retry_count=retry_count,
        total_fetched=len(results),
        total_after_filter=0,
        source_timings=all_timings,
        search_plan=plan,
    )
    return [], metadata
