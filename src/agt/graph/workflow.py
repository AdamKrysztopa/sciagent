"""Minimal workflow orchestration layer."""

from __future__ import annotations

from agt.models import AgentState
from agt.tools.search_papers import search_papers
from agt.tools.zotero_upsert import upsert_papers


async def run_workflow(query: str, collection_name: str, approved: bool) -> AgentState:
    """Execute a lightweight search -> optional write workflow."""

    papers = await search_papers(query=query)
    write_result: dict[str, int] | None = None
    if approved and papers:
        result = await upsert_papers(collection_name=collection_name, papers=papers)
        write_result = {
            "created": result.created,
            "unchanged": result.unchanged,
            "failed": result.failed,
        }

    return {
        "messages": [f"Processed query: {query}"],
        "papers": papers,
        "collection_name": collection_name,
        "approved": approved,
        "write_result": write_result,
    }
