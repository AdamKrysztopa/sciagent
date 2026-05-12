"""Read-only MCP server exposing SciAgent tools via FastMCP.

Exposes four read-only tools:
  search_papers    — run a search and return ranked paper list
  list_watches     — list saved watch queries
  get_session      — retrieve a saved session by ID
  library_doctor   — scan a Zotero collection for issues

Write tools are intentionally omitted to preserve the approval-gate invariant.
Run with: uv run python -m agt.mcp_server
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from agt.config import get_settings
from agt.graph.workflow import run_search_phase
from agt.models import AgentState, DoctorReport
from agt.session_store import SessionStore
from agt.watch_store import WatchStore
from agt.zotero.library_doctor import scan_collection

mcp = FastMCP("SciAgent")


@mcp.tool()
async def search_papers(query: str, collection_name: str | None = None) -> str:
    """Search academic papers and return ranked results as JSON.

    Args:
        query: Natural-language research query (may include year constraints,
               open-access preferences, etc.)
        collection_name: Optional Zotero collection name context for
                         library-status tagging.

    Returns:
        JSON string with keys: papers (list), search_metadata (dict).
        This tool is read-only — it does not write to Zotero.
    """
    settings = get_settings()
    state: AgentState = await run_search_phase(
        query=query,
        collection_name=collection_name or settings.zotero_collection_name,
        settings=settings,
    )
    papers: list[Any] = state.get("papers", [])
    metadata: Any = state.get("search_metadata")
    return json.dumps(
        {
            "papers": [p if isinstance(p, dict) else p.model_dump() for p in papers],
            "search_metadata": metadata,
            "count": len(papers),
        },
        default=str,
    )


@mcp.tool()
def list_watches() -> str:
    """List all saved watch queries.

    Returns:
        JSON string with a list of watch objects (id, name, query,
        collection_name, created_at, last_run_at, seen_count).
    """
    settings = get_settings()
    store = WatchStore(settings.resolved_watch_dir)
    watches = store.list_watches()
    return json.dumps([
        {
            "id": w.id,
            "name": w.name,
            "query": w.query,
            "collection_name": w.collection_name,
            "created_at": w.created_at,
            "last_run_at": w.last_run_at,
            "seen_count": len(w.seen_fingerprints),
        }
        for w in watches
    ])


@mcp.tool()
def get_session(session_id: str) -> str:
    """Retrieve a saved session by ID.

    Args:
        session_id: The session UUID returned by a previous search run.

    Returns:
        JSON string with the full session state including papers and metadata.
        Returns an error object if the session is not found.
    """
    settings = get_settings()
    store = SessionStore(settings.resolved_session_dir)
    try:
        session = store.load(session_id)
    except KeyError:
        return json.dumps({"error": f"session_not_found: {session_id}"})
    return json.dumps(session, default=str)


@mcp.tool()
async def library_doctor(collection_name: str) -> str:
    """Scan a Zotero collection for issues (missing DOI, abstract, PDF, duplicates).

    Args:
        collection_name: Name of the Zotero collection to scan.

    Returns:
        JSON string with the doctor report including missing_doi, missing_abstract,
        missing_pdf, and duplicate_pairs counts and item lists.
    """
    settings = get_settings()
    report: DoctorReport = await scan_collection(collection_name, settings)
    return json.dumps(report.model_dump(), default=str)


if __name__ == "__main__":
    mcp.run()
