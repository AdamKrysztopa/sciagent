"""Minimal workflow orchestration layer."""

from __future__ import annotations

from typing import Any, Literal

import httpx
import structlog

from agt.config import Settings, configure_logging, get_settings
from agt.guardrails import configure_guardrails, thread_context
from agt.models import AgentState, CollectionResult, ItemWriteOutcome, NormalizedPaper, WriteResult
from agt.observability import TraceContext, serialize_spans, trace_step
from agt.providers.router import build_provider
from agt.tools.search_papers import search_papers
from agt.tools.summarize import summarize_papers
from agt.tools.zotero_upsert import ZoteroWriteError, upsert_papers
from agt.zotero.preflight import run_zotero_preflight


def _serialize_papers(papers: list[NormalizedPaper]) -> list[dict[str, Any]]:
    return [paper.model_dump() for paper in papers]


def _deserialize_papers(serialized: list[dict[str, Any]]) -> list[NormalizedPaper]:
    return [NormalizedPaper.model_validate(paper) for paper in serialized]


def _select_papers(
    papers: list[NormalizedPaper],
    selected_indices: list[int] | None,
) -> tuple[list[NormalizedPaper], list[int]]:
    if selected_indices is None:
        all_indices = [index for index, _paper in enumerate(papers)]
        return papers, all_indices

    selected_set = set(selected_indices)
    normalized_selected = [index for index, _paper in enumerate(papers) if index in selected_set]
    selected_papers = [papers[index] for index in normalized_selected]
    return selected_papers, normalized_selected


def _logger(trace: TraceContext) -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger("agt.workflow").bind(
        request_id=trace.request_id,
        thread_id=trace.thread_id,
    )


def _build_write_failure_result(
    *,
    selected_papers: list[NormalizedPaper],
    selected_indices: list[int],
    collection_name: str,
    reason: str,
    retry_safe: bool,
) -> WriteResult:
    failed_outcomes = [
        ItemWriteOutcome(
            index=idx,
            title=paper.title,
            status="failed",
            reason=reason,
            retry_safe=retry_safe,
        )
        for idx, paper in zip(selected_indices, selected_papers, strict=False)
    ]
    retry_safe_failures = len(failed_outcomes) if retry_safe else 0
    return WriteResult(
        created=0,
        unchanged=0,
        failed=len(failed_outcomes),
        collection=CollectionResult(
            key="unresolved",
            name=collection_name,
            reused=False,
        ),
        outcomes=failed_outcomes,
        retry_safe_failures=retry_safe_failures,
    )


async def run_search_phase(
    query: str,
    collection_name: str,
    thread_id: str | None = None,
    settings: Settings | None = None,
) -> AgentState:
    """Run startup, retrieval, and summarization up to the approval checkpoint."""

    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    configure_guardrails(active_settings)
    trace = TraceContext.create(thread_id=thread_id)
    logger = _logger(trace)

    with thread_context(trace.thread_id):
        with trace_step(trace, "provider_init", provider=active_settings.runtime.provider):
            provider = build_provider(active_settings)
            logger.info(
                "provider_selected",
                provider=active_settings.runtime.provider,
                model_name=active_settings.runtime.model_name,
                timeout_seconds=active_settings.runtime.timeout_seconds,
                retries=active_settings.runtime.retries,
                temperature=active_settings.runtime.temperature,
            )

        with trace_step(trace, "zotero_preflight"):
            preflight = run_zotero_preflight(active_settings)

        if not preflight.ok:
            logger.error("startup_preflight_failed", preflight=preflight.to_dict())
            raise RuntimeError(preflight.message)

        with trace_step(trace, "search", query=query):
            papers, search_metadata = await search_papers(
                query=query,
                settings=active_settings,
                thread_id=trace.thread_id,
            )

        with trace_step(trace, "summarize", paper_count=len(papers)):
            papers = await summarize_papers(
                papers,
                provider=provider,
                use_llm=active_settings.summarization_use_llm,
                max_sentences=active_settings.summarization_max_sentences,
            )

        with trace_step(trace, "approval_checkpoint", approved=False):
            logger.info("approval_checkpoint", approved=False)

    return {
        "request_id": trace.request_id,
        "thread_id": trace.thread_id,
        "messages": [f"Processed query: {query}"],
        "papers": _serialize_papers(papers),
        "collection_name": collection_name,
        "approved": False,
        "decision": "pending",
        "phase": "awaiting_approval",
        "selected_indices": [index for index, _paper in enumerate(papers)],
        "preflight": preflight.to_dict(),
        "trace_spans": serialize_spans(trace.spans),
        "write_result": None,
        "search_metadata": search_metadata.model_dump(),
    }


async def finalize_approval(
    checkpoint: AgentState,
    approved: bool,
    *,
    collection_name: str | None = None,
    selected_indices: list[int] | None = None,
    settings: Settings | None = None,
) -> AgentState:
    """Finalize workflow from approval checkpoint state with explicit approve/reject branch."""

    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    configure_guardrails(active_settings)
    trace = TraceContext.create(thread_id=checkpoint["thread_id"])
    trace.request_id = checkpoint["request_id"]
    logger = _logger(trace)

    effective_collection = collection_name or checkpoint["collection_name"] or "Inbox"
    papers = _deserialize_papers(checkpoint["papers"])
    selected_papers, normalized_selected = _select_papers(papers, selected_indices)

    write_result: dict[str, Any] | None = None
    final_phase: Literal[
        "search_complete", "awaiting_approval", "completed", "rejected", "failed"
    ] = "rejected"
    final_decision: Literal["approved", "rejected", "pending"] = "rejected"
    if approved:
        final_phase = "completed"
        final_decision = "approved"

    with thread_context(trace.thread_id):
        with trace_step(trace, "approval_decision", approved=approved):
            logger.info(
                "approval_decision",
                approved=approved,
                selected_count=len(selected_papers),
                collection_name=effective_collection,
            )

        if (
            approved
            and checkpoint["phase"] == "completed"
            and checkpoint["write_result"] is not None
        ):
            logger.info("write_retry_skipped", reason="already_completed")
            write_result = checkpoint["write_result"]
        elif approved and selected_papers:
            with trace_step(
                trace,
                "zotero_write",
                collection_name=effective_collection,
                selected_count=len(selected_papers),
            ):
                try:
                    result = await upsert_papers(
                        collection_name=effective_collection,
                        papers=selected_papers,
                        settings=active_settings,
                    )
                    write_result = result.model_dump()
                    write_attempted = result.created + result.unchanged + result.failed
                    if write_attempted > 0 and result.failed == write_attempted:
                        final_phase = "failed"
                        logger.warning(
                            "zotero_write_all_failed",
                            failed=result.failed,
                            created=result.created,
                            unchanged=result.unchanged,
                            retry_safe_failures=result.retry_safe_failures,
                        )
                    elif result.failed > 0:
                        logger.warning(
                            "zotero_write_partial_failure",
                            failed=result.failed,
                            created=result.created,
                            unchanged=result.unchanged,
                            retry_safe_failures=result.retry_safe_failures,
                        )
                except (ZoteroWriteError, httpx.HTTPError) as exc:
                    logger.error(
                        "zotero_write_failed",
                        error=str(exc),
                        error_type=type(exc).__name__,
                        selected_count=len(selected_papers),
                    )
                    write_result = _build_write_failure_result(
                        selected_papers=selected_papers,
                        selected_indices=normalized_selected,
                        collection_name=effective_collection,
                        reason=f"write_error:{type(exc).__name__}",
                        retry_safe=True,
                    ).model_dump()
                    final_phase = "failed"
                except Exception as exc:
                    logger.error(
                        "zotero_write_unexpected_failure",
                        error=str(exc),
                        error_type=type(exc).__name__,
                        selected_count=len(selected_papers),
                    )
                    write_result = _build_write_failure_result(
                        selected_papers=selected_papers,
                        selected_indices=normalized_selected,
                        collection_name=effective_collection,
                        reason=f"write_unexpected_error:{type(exc).__name__}",
                        retry_safe=False,
                    ).model_dump()
                    final_phase = "failed"

        logger.info(
            "workflow_complete",
            approved=approved,
            paper_count=len(selected_papers),
        )

    combined_spans = checkpoint["trace_spans"] + serialize_spans(trace.spans)
    summary_message = "Approval rejected; write skipped."
    if approved and final_phase == "failed":
        summary_message = "Approval accepted; write failed."
    elif approved:
        summary_message = "Approval accepted; write executed."
    merged_messages = checkpoint["messages"] + [summary_message]
    return {
        "request_id": checkpoint["request_id"],
        "thread_id": checkpoint["thread_id"],
        "messages": merged_messages,
        "papers": checkpoint["papers"],
        "collection_name": effective_collection,
        "approved": approved,
        "decision": final_decision,
        "phase": final_phase,
        "selected_indices": normalized_selected,
        "preflight": checkpoint["preflight"],
        "trace_spans": combined_spans,
        "write_result": write_result,
        "search_metadata": checkpoint["search_metadata"],
    }


async def resume_workflow(
    checkpoint: AgentState,
    *,
    approved: bool,
    collection_name: str | None = None,
    selected_indices: list[int] | None = None,
    settings: Settings | None = None,
) -> AgentState:
    """Resume from a checkpoint with deterministic retry semantics."""

    if checkpoint["phase"] == "completed" and checkpoint["write_result"] is not None:
        return {
            **checkpoint,
            "messages": checkpoint["messages"]
            + ["Resume requested after completion; state reused."],
        }

    if checkpoint["phase"] == "rejected":
        return {
            **checkpoint,
            "messages": checkpoint["messages"]
            + ["Resume requested after rejection; state reused."],
        }

    return await finalize_approval(
        checkpoint,
        approved=approved,
        collection_name=collection_name,
        selected_indices=selected_indices,
        settings=settings,
    )


async def run_workflow(
    query: str,
    collection_name: str,
    approved: bool,
    thread_id: str | None = None,
    settings: Settings | None = None,
) -> AgentState:
    """Backward-compatible wrapper for one-shot execution."""

    checkpoint = await run_search_phase(
        query=query,
        collection_name=collection_name,
        thread_id=thread_id,
        settings=settings,
    )
    return await finalize_approval(
        checkpoint,
        approved=approved,
        collection_name=collection_name,
        settings=settings,
    )
