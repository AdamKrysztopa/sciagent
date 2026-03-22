"""Paper search tool adapter."""

from __future__ import annotations

from agt.config import Settings, get_settings
from agt.guardrails import current_thread_id, get_guardrails
from agt.models import NormalizedPaper
from agt.providers.protocol import LLMProvider
from agt.tools.crossref import CrossrefClient
from agt.tools.europe_pmc import EuropePMCClient
from agt.tools.openalex import OpenAlexClient
from agt.tools.pubmed import PubMedClient
from agt.tools.query_constraints import (
    SearchConstraintSpec,
    apply_query_constraints,
    parse_query_constraints,
)
from agt.tools.query_rewriter import rewrite_query, validate_results
from agt.tools.ranking import rank_and_index_papers
from agt.tools.semantic_scholar import SemanticScholarClient, SemanticScholarResponseError

_MIN_KEYWORD_QUERY_LEN = 3
_OVER_FETCH_MULTIPLIER = 3
_MAX_FETCH_LIMIT = 30


async def _fetch_from_sources(
    query: str,
    limit: int,
    constraints: SearchConstraintSpec,
    settings: Settings,
    thread_id: str,
) -> tuple[list[NormalizedPaper], list[str]]:
    """Fetch papers from all configured academic sources."""
    guardrails = get_guardrails()
    results: list[NormalizedPaper] = []
    failures: list[str] = []

    guardrails.acquire("semantic_scholar", thread_id)
    semantic_api_key = None
    if settings.semantic_scholar_api_key is not None:
        semantic_api_key = settings.semantic_scholar_api_key.get_secret_value()
    semantic_client = SemanticScholarClient(
        api_key=semantic_api_key,
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    try:
        results.extend(await semantic_client.search(query=query, limit=limit))
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        failures.append(f"semantic_scholar: {exc}")

    guardrails.acquire("openalex", thread_id)
    openalex_client = OpenAlexClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    try:
        results.extend(
            await openalex_client.search(
                query=query,
                limit=limit,
                year_min=constraints.year.min_year,
            )
        )
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        failures.append(f"openalex: {exc}")

    guardrails.acquire("crossref", thread_id)
    crossref_client = CrossrefClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    try:
        results.extend(await crossref_client.search(query=query, limit=limit))
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        failures.append(f"crossref: {exc}")

    guardrails.acquire("pubmed", thread_id)
    ncbi_api_key = None
    if settings.ncbi_api_key is not None:
        ncbi_api_key = settings.ncbi_api_key.get_secret_value()
    pubmed_client = PubMedClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
        api_key=ncbi_api_key,
    )
    try:
        results.extend(await pubmed_client.search(query=query, limit=limit))
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        failures.append(f"pubmed: {exc}")

    guardrails.acquire("europe_pmc", thread_id)
    europe_pmc_client = EuropePMCClient(
        timeout_seconds=settings.semantic_scholar_timeout_seconds,
        retries=settings.semantic_scholar_retries,
    )
    try:
        results.extend(await europe_pmc_client.search(query=query, limit=limit))
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        failures.append(f"europe_pmc: {exc}")

    return results, failures


def _rank_and_filter(
    results: list[NormalizedPaper],
    constraints: SearchConstraintSpec,
    capped_limit: int,
) -> list[NormalizedPaper]:
    """Rank, apply constraints, and index a result set."""
    ranked = rank_and_index_papers(results)
    filtered = apply_query_constraints(ranked, constraints)
    for index, paper in enumerate(filtered):
        paper.index = index
    return filtered[:capped_limit]


def _build_regex_query(constraints: SearchConstraintSpec, raw_query: str) -> str:
    """Build a retrieval query from regex-extracted keywords (fallback)."""
    keyword_query = " ".join(constraints.keywords.include_keywords)
    return keyword_query if len(keyword_query) >= _MIN_KEYWORD_QUERY_LEN else raw_query


async def search_papers(  # noqa: PLR0912
    query: str,
    limit: int = 10,
    *,
    settings: Settings | None = None,
    thread_id: str | None = None,
    provider: LLMProvider | None = None,
) -> list[NormalizedPaper]:
    """Search multiple academic sources and return ranked normalized papers.

    When *provider* is supplied the pipeline uses LLM-based query rewriting
    and post-retrieval relevance validation with one automatic retry.
    """

    if not query.strip():
        return []

    active_settings = settings or get_settings()
    active_thread = thread_id or current_thread_id()
    capped_limit = min(limit, active_settings.semantic_scholar_limit)
    constraints = parse_query_constraints(query, default_limit=capped_limit)
    fetch_limit = min(capped_limit * _OVER_FETCH_MULTIPLIER, _MAX_FETCH_LIMIT)

    regex_query = _build_regex_query(constraints, query)
    retrieval_query = regex_query
    topic = ""

    # --- LLM query rewriting ---
    if provider is not None:
        try:
            rewritten = await rewrite_query(query, provider)
            retrieval_query = rewritten.search_query
            topic = rewritten.topic
        except Exception:
            pass  # fall back to regex query

    # --- Primary search ---
    results, failures = await _fetch_from_sources(
        retrieval_query,
        fetch_limit,
        constraints,
        active_settings,
        active_thread,
    )

    if results:
        filtered = _rank_and_filter(results, constraints, capped_limit)

        # --- LLM relevance validation with one retry ---
        if provider is not None and filtered and topic:
            try:
                validation = await validate_results(query, topic, filtered, provider)
                if not validation.is_relevant and validation.suggested_query:
                    retry_results, retry_failures = await _fetch_from_sources(
                        validation.suggested_query,
                        fetch_limit,
                        constraints,
                        active_settings,
                        active_thread,
                    )
                    failures.extend(retry_failures)
                    if retry_results:
                        retry_filtered = _rank_and_filter(
                            retry_results,
                            constraints,
                            capped_limit,
                        )
                        if retry_filtered:
                            filtered = retry_filtered
            except Exception:
                pass  # validation failure is non-fatal

        if filtered:
            return filtered

    # --- Regex fallback when LLM query produced nothing useful ---
    if retrieval_query != regex_query:
        fallback_results, fallback_failures = await _fetch_from_sources(
            regex_query,
            fetch_limit,
            constraints,
            active_settings,
            active_thread,
        )
        failures.extend(fallback_failures)
        if fallback_results:
            filtered = _rank_and_filter(fallback_results, constraints, capped_limit)
            if filtered:
                return filtered
        if not results:
            results = fallback_results

    if not results:
        failure_text = "; ".join(failures) if failures else "no sources returned any papers"
        raise SemanticScholarResponseError(f"all retrieval providers failed: {failure_text}")

    return []
