"""Paper search tool adapter."""

# ruff: noqa: PLR0913

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from agt.config import Settings, get_settings
from agt.guardrails import current_thread_id, get_guardrails
from agt.models import NormalizedPaper, SearchMetadata
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
    SearchConstraintSpec,
    apply_query_constraints,
    parse_query_constraints,
)
from agt.tools.query_rewriter import RewrittenQuery, rewrite_query, validate_results
from agt.tools.ranking import rank_and_index_papers
from agt.tools.reranker import rerank_papers
from agt.tools.semantic_scholar import SemanticScholarClient, SemanticScholarResponseError
from agt.tools.spell_check import correct_query

_MIN_KEYWORD_QUERY_LEN = 3
_OVER_FETCH_MULTIPLIER = 3
_MAX_FETCH_LIMIT = 30
_WAIT_TOKEN_TIMEOUT_SECONDS = 1.5


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
) -> tuple[list[NormalizedPaper], list[str], list[str], dict[str, float]]:
    results: list[NormalizedPaper] = []
    failures: list[str] = []
    sources_used: list[str] = []
    timings: dict[str, float] = {}

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


def _rank_and_filter(
    results: list[NormalizedPaper],
    constraints: SearchConstraintSpec,
    capped_limit: int,
    *,
    settings: Settings,
    query: str,
) -> list[NormalizedPaper]:
    """Rank, apply constraints, and index a result set."""

    rerank_input = results
    if settings.use_reranker:
        rerank_input = rerank_papers(query=query, papers=results, top_k=len(results))

    ranked = rank_and_index_papers(rerank_input)
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


async def search_papers(  # noqa: PLR0912, PLR0915
    query: str,
    limit: int = 10,
    *,
    settings: Settings | None = None,
    thread_id: str | None = None,
    provider: LLMProvider | None = None,
    fallback_mode: Literal["auto", "force", "off"] | None = None,
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

    capped_limit = min(limit, active_settings.semantic_scholar_limit)
    constraints = parse_query_constraints(
        corrected_query,
        default_limit=capped_limit,
        settings=active_settings,
    )
    fetch_limit = min(capped_limit * _OVER_FETCH_MULTIPLIER, _MAX_FETCH_LIMIT)

    regex_query = _build_regex_query(constraints, corrected_query, active_settings)
    retrieval_query = corrected_query
    topic = ""
    mode: str = "regex"
    rewritten: RewrittenQuery | None = None

    if provider is not None:
        try:
            rewritten = await rewrite_query(corrected_query, provider)
            retrieval_query = rewritten.search_query
            topic = rewritten.topic
            mode = "llm_rewrite"
        except Exception:
            retrieval_query = corrected_query
            topic = ""

    all_failures: list[str] = []
    all_sources_used: list[str] = []
    all_timings: dict[str, float] = {}
    retry_count = 0

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

    results, failures, sources_used, timings = await _fetch_query_with_optional_fallback(
        retrieval_query,
        fetch_limit,
        constraints,
        active_settings,
        active_thread,
        rewritten,
        effective_fallback_mode,
        capped_limit,
        corrected_query,
    )
    _merge_telemetry(failures, sources_used, timings)

    if rewritten and rewritten.synonyms:
        synonym_query = rewritten.synonyms[0]
        if synonym_query and synonym_query != retrieval_query:
            (
                synonym_results,
                synonym_failures,
                synonym_sources,
                synonym_timings,
            ) = await _fetch_query_with_optional_fallback(
                synonym_query,
                fetch_limit,
                constraints,
                active_settings,
                active_thread,
                rewritten,
                effective_fallback_mode,
                capped_limit,
                corrected_query,
            )
            results.extend(synonym_results)
            _merge_telemetry(synonym_failures, synonym_sources, synonym_timings)

    if results:
        results = await _enrich_citations(
            results, settings=active_settings, thread_id=active_thread
        )
        filtered = _rank_and_filter(
            results,
            constraints,
            capped_limit,
            settings=active_settings,
            query=corrected_query,
        )

        if provider is not None and filtered and topic:
            try:
                validation = await validate_results(corrected_query, topic, filtered, provider)
                if not validation.is_relevant and validation.suggested_query:
                    retry_count += 1
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
                    )
                    _merge_telemetry(retry_failures, retry_sources, retry_timings)
                    if retry_results:
                        retry_results = await _enrich_citations(
                            retry_results,
                            settings=active_settings,
                            thread_id=active_thread,
                        )
                        retry_filtered = _rank_and_filter(
                            retry_results,
                            constraints,
                            capped_limit,
                            settings=active_settings,
                            query=corrected_query,
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
            )
            return filtered, metadata

    if retrieval_query != regex_query:
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
        )
        _merge_telemetry(fallback_failures, fallback_sources, fallback_timings)
        if fallback_results:
            fallback_results = await _enrich_citations(
                fallback_results,
                settings=active_settings,
                thread_id=active_thread,
            )
            filtered = _rank_and_filter(
                fallback_results,
                constraints,
                capped_limit,
                settings=active_settings,
                query=corrected_query,
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
    )
    return [], metadata
