"""Paper search tool adapter."""

from __future__ import annotations

from agt.config import Settings, get_settings
from agt.guardrails import current_thread_id, get_guardrails
from agt.models import NormalizedPaper
from agt.tools.crossref import CrossrefClient
from agt.tools.openalex import OpenAlexClient
from agt.tools.query_constraints import apply_query_constraints, parse_query_constraints
from agt.tools.ranking import rank_and_index_papers
from agt.tools.semantic_scholar import SemanticScholarClient, SemanticScholarResponseError


async def search_papers(
    query: str,
    limit: int = 10,
    *,
    settings: Settings | None = None,
    thread_id: str | None = None,
) -> list[NormalizedPaper]:
    """Search multiple academic sources and return ranked normalized papers."""

    if not query.strip():
        return []

    active_settings = settings or get_settings()
    guardrails = get_guardrails()
    active_thread = thread_id or current_thread_id()
    capped_limit = min(limit, active_settings.semantic_scholar_limit)
    constraints = parse_query_constraints(query, default_limit=capped_limit)
    retrieval_query = " ".join(constraints.keywords.include_keywords) or query
    results: list[NormalizedPaper] = []
    failures: list[str] = []

    guardrails.acquire("semantic_scholar", active_thread)
    semantic_api_key = None
    if active_settings.semantic_scholar_api_key is not None:
        semantic_api_key = active_settings.semantic_scholar_api_key.get_secret_value()
    semantic_client = SemanticScholarClient(
        api_key=semantic_api_key,
        timeout_seconds=active_settings.semantic_scholar_timeout_seconds,
        retries=active_settings.semantic_scholar_retries,
    )
    try:
        results.extend(await semantic_client.search(query=retrieval_query, limit=capped_limit))
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        failures.append(f"semantic_scholar: {exc}")

    guardrails.acquire("semantic_scholar", active_thread)
    openalex_client = OpenAlexClient(
        timeout_seconds=active_settings.semantic_scholar_timeout_seconds,
        retries=active_settings.semantic_scholar_retries,
    )
    try:
        results.extend(await openalex_client.search(query=retrieval_query, limit=capped_limit))
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        failures.append(f"openalex: {exc}")

    guardrails.acquire("semantic_scholar", active_thread)
    crossref_client = CrossrefClient(
        timeout_seconds=active_settings.semantic_scholar_timeout_seconds,
        retries=active_settings.semantic_scholar_retries,
    )
    try:
        results.extend(await crossref_client.search(query=retrieval_query, limit=capped_limit))
    except Exception as exc:  # pragma: no cover - handled by integration behavior
        failures.append(f"crossref: {exc}")

    if not results:
        failure_text = "; ".join(failures) if failures else "no sources returned any papers"
        raise SemanticScholarResponseError(f"all retrieval providers failed: {failure_text}")

    ranked = rank_and_index_papers(results)
    filtered = apply_query_constraints(ranked, constraints)
    for index, paper in enumerate(filtered):
        paper.index = index

    return filtered
