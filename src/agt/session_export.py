"""Export search session reports in Markdown, JSON, and CSV formats (SCI-0206)."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any, Literal

ExportFormat = Literal["markdown", "json", "csv"]

_MAX_AUTHORS = 3


def export_session(
    state: dict[str, Any],
    fmt: ExportFormat = "markdown",
    *,
    run_id: str | None = None,
) -> str:
    """Render a session report in the requested format."""
    if fmt == "json":
        return json.dumps(state, indent=2, default=str)
    if fmt == "csv":
        return _to_csv(state)
    return _to_markdown(state, run_id=run_id)


def _format_authors(authors: list[str]) -> str:
    if len(authors) <= _MAX_AUTHORS:
        return ", ".join(authors)
    return ", ".join(authors[:_MAX_AUTHORS]) + " et al."


def _append_search_plan(lines: list[str], search_plan: dict[str, Any]) -> None:
    lines.append("\n## Search Plan")
    topic = search_plan.get("topic_query", "")
    if topic:
        lines.append(f"\n**Topic query:** {topic}")
    rewrites: list[str] = search_plan.get("rewritten_queries") or []
    if rewrites:
        lines.append("\n**Rewritten queries:**\n")
        for q in rewrites:
            lines.append(f"- {q}")
    hard: dict[str, Any] = search_plan.get("hard_filters") or {}
    active = {k: v for k, v in hard.items() if v not in (None, False, 0, [], {})}
    if active:
        lines.append("\n**Active hard filters:**\n")
        for k, v in active.items():
            lines.append(f"- `{k}`: {v}")


def _append_sources(lines: list[str], search_metadata: dict[str, Any]) -> None:
    sources_used: list[str] = search_metadata.get("sources_used") or []
    sources_failed: list[str] = search_metadata.get("sources_failed") or []
    if not sources_used and not sources_failed:
        return
    lines.append("\n## Identification")
    lines.append(f"\n- Databases searched: {', '.join(sources_used) or 'none'}")
    if sources_failed:
        lines.append(f"- Databases failed: {', '.join(sources_failed)}")
    lines.append(f"- Records identified: {search_metadata.get('total_fetched', 0)}")
    lines.append(f"- Records after filter: {search_metadata.get('total_after_filter', 0)}")


def _append_papers(lines: list[str], papers: list[dict[str, Any]], selected_set: set[int]) -> None:
    for i, paper in enumerate(papers):
        idx = paper.get("index") if paper.get("index") is not None else i + 1
        tick = "✓" if idx in selected_set else " "
        title = paper.get("title", "Untitled")
        year = paper.get("year")
        authors: list[str] = paper.get("authors") or []
        first_authors = _format_authors(authors)
        doi = paper.get("doi", "")
        source = paper.get("source", "")
        score: float = paper.get("score") or 0.0
        explanation = paper.get("explanation", "")

        lines.append(f"\n### [{tick}] {idx}. {title}")
        if first_authors:
            year_str = f" ({year})" if year else ""
            lines.append(f"\n*{first_authors}{year_str}*")
        meta: list[str] = []
        if doi:
            meta.append(f"DOI: [{doi}](https://doi.org/{doi})")
        if source:
            meta.append(f"Source: {source}")
        if score:
            meta.append(f"Score: {score:.2f}")
        if meta:
            lines.append("\n" + " · ".join(meta))
        if explanation:
            lines.append(f"\n> {explanation}")


def _to_markdown(state: dict[str, Any], *, run_id: str | None = None) -> str:
    lines: list[str] = []
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")

    lines.append("# SciAgent Session Report")
    if run_id:
        lines.append(f"\n**Run ID:** `{run_id}`")
    lines.append(f"\n**Generated:** {now}")

    search_metadata: dict[str, Any] = state.get("search_metadata") or {}
    query = search_metadata.get("original_query") or ""
    if not query:
        msgs: list[str] = state.get("messages") or []
        query = msgs[0] if msgs else "unknown"
    lines.append(f"\n## Query\n\n> {query}")

    search_plan: dict[str, Any] = search_metadata.get("search_plan") or {}
    if search_plan:
        _append_search_plan(lines, search_plan)

    _append_sources(lines, search_metadata)

    papers: list[dict[str, Any]] = state.get("papers") or []
    selected: list[int] = state.get("selected_indices") or []
    selected_set = set(selected)
    lines.append(f"\n## Results\n\n**{len(papers)} papers retrieved** · {len(selected)} selected")
    _append_papers(lines, papers, selected_set)

    write_result: dict[str, Any] | None = state.get("write_result")
    if write_result and not write_result.get("native_write"):
        lines.append("\n## Write Outcome")
        collection: dict[str, Any] = write_result.get("collection") or {}
        col_name = collection.get("name", "")
        if col_name:
            lines.append(f"\n**Collection:** {col_name}")
        lines.append(f"\n- Created: {write_result.get('created', 0)}")
        lines.append(f"- Unchanged: {write_result.get('unchanged', 0)}")
        lines.append(f"- Failed: {write_result.get('failed', 0)}")

    lines.append(f"\n---\n\n*Generated by SciAgent — {now}*")
    return "\n".join(lines)


def _to_csv(state: dict[str, Any]) -> str:
    papers: list[dict[str, Any]] = state.get("papers") or []
    selected_set = set(state.get("selected_indices") or [])
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "index",
            "selected",
            "title",
            "year",
            "authors",
            "doi",
            "source",
            "score",
            "open_access",
            "url",
            "explanation",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for i, paper in enumerate(papers):
        idx = paper.get("index") if paper.get("index") is not None else i + 1
        authors: list[str] = paper.get("authors") or []
        writer.writerow({
            "index": idx,
            "selected": "yes" if idx in selected_set else "no",
            "title": paper.get("title", ""),
            "year": paper.get("year", ""),
            "authors": "; ".join(authors),
            "doi": paper.get("doi", ""),
            "source": paper.get("source", ""),
            "score": f"{paper.get('score') or 0.0:.3f}",
            "open_access": "yes" if paper.get("open_access") else "no",
            "url": paper.get("url", ""),
            "explanation": paper.get("explanation", ""),
        })
    return buf.getvalue()
