"""Minimal workflow orchestration layer."""

from __future__ import annotations

import structlog

from agt.config import configure_logging, get_settings
from agt.guardrails import configure_guardrails, thread_context
from agt.models import AgentState
from agt.observability import TraceContext, serialize_spans, trace_step
from agt.providers.router import build_provider
from agt.tools.search_papers import search_papers
from agt.tools.summarize import summarize_papers
from agt.tools.zotero_upsert import upsert_papers
from agt.zotero.preflight import run_zotero_preflight


async def run_workflow(
    query: str, collection_name: str, approved: bool, thread_id: str | None = None
) -> AgentState:
    """Execute startup checks and then run search -> approval checkpoint -> optional write."""

    settings = get_settings()
    configure_logging(settings.log_level)
    configure_guardrails(settings)
    trace = TraceContext.create(thread_id=thread_id)
    logger = structlog.get_logger("agt.workflow").bind(
        request_id=trace.request_id,
        thread_id=trace.thread_id,
    )

    with thread_context(trace.thread_id):
        with trace_step(trace, "provider_init", provider=settings.runtime.provider):
            provider = build_provider(settings)
            logger.info(
                "provider_selected",
                provider=settings.runtime.provider,
                model_name=settings.runtime.model_name,
                timeout_seconds=settings.runtime.timeout_seconds,
                retries=settings.runtime.retries,
                temperature=settings.runtime.temperature,
            )

        with trace_step(trace, "zotero_preflight"):
            preflight = run_zotero_preflight(settings)

        if not preflight.ok:
            logger.error("startup_preflight_failed", preflight=preflight.to_dict())
            raise RuntimeError(preflight.message)

        with trace_step(trace, "search", query=query):
            papers, search_metadata = await search_papers(
                query=query,
                settings=settings,
                thread_id=trace.thread_id,
            )

        with trace_step(trace, "summarize", paper_count=len(papers)):
            papers = await summarize_papers(
                papers,
                provider=provider,
                use_llm=settings.summarization_use_llm,
                max_sentences=settings.summarization_max_sentences,
            )

        with trace_step(trace, "approval_checkpoint", approved=approved):
            logger.info("approval_checkpoint", approved=approved)

        write_result: dict[str, object] | None = None
        if approved and papers:
            with trace_step(trace, "zotero_write", collection_name=collection_name):
                result = await upsert_papers(
                    collection_name=collection_name,
                    papers=papers,
                    settings=settings,
                )
                write_result = result.model_dump()

        logger.info("workflow_complete", approved=approved, paper_count=len(papers))

    return {
        "request_id": trace.request_id,
        "thread_id": trace.thread_id,
        "messages": [f"Processed query: {query}"],
        "papers": papers,
        "collection_name": collection_name,
        "approved": approved,
        "preflight": preflight.to_dict(),
        "trace_spans": serialize_spans(trace.spans),
        "write_result": write_result,
        "search_metadata": search_metadata.model_dump(),
    }
