"""Core domain models for papers and workflow state."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class NormalizedPaper(BaseModel):
    """Canonical paper representation used across providers and UI."""

    title: str
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    url: str | None = None
    source: str = "semantic_scholar"
    index: int | None = None
    semantic_score: float = 0.0
    citation_count: int = 0
    influential_citation_count: int = 0
    open_access: bool = False
    summary: str | None = None
    score: float = 0.0


class SearchMetadata(BaseModel):
    """Execution metadata captured for each search request."""

    original_query: str
    rewritten_query: str | None = None
    regex_query: str
    sources_used: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    mode: Literal["llm_rewrite", "regex"] = "regex"
    retry_count: int = 0
    total_fetched: int = 0
    total_after_filter: int = 0
    source_timings: dict[str, float] = Field(default_factory=dict)


class AgentState(TypedDict):
    """Serializable state used by the workflow engine."""

    request_id: str
    thread_id: str
    messages: list[str]
    papers: list[NormalizedPaper]
    collection_name: str | None
    approved: bool
    preflight: dict[str, Any]
    trace_spans: list[dict[str, Any]]
    write_result: dict[str, Any] | None
    search_metadata: dict[str, Any] | None
