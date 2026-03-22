"""Paper search tool adapter."""

from __future__ import annotations

from agt.models import NormalizedPaper


async def search_papers(query: str, limit: int = 10) -> list[NormalizedPaper]:
    """Return placeholder search results until provider integration is implemented."""

    if not query.strip():
        return []
    return [
        NormalizedPaper(
            title=f"Placeholder result for: {query}",
            year=2026,
            source="semantic_scholar",
            score=1.0,
        )
    ][:limit]
