"""Core domain models for papers and workflow state."""

from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

from pydantic import BaseModel, Field


class HardFilters(BaseModel):
    """Filters that cannot be relaxed or overridden by LLM rewriting."""

    min_year: int | None = None
    max_year: int | None = None
    min_citations: int = 0
    max_citations: int | None = None
    open_access_only: bool = False
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class SoftPreferences(BaseModel):
    """Preferences that influence ranking but do not hard-filter results."""

    require_positive_community_perception: bool = False
    min_semantic_score: float = 0.0


class SourceCapability(BaseModel):
    """Per-source retrieval policy and push-down capabilities."""

    name: str
    tier: Literal["primary", "fallback"]
    enabled: bool
    supports_year_filter: bool = False
    supports_open_access_filter: bool = False


class SearchPlan(BaseModel):
    """Typed search plan produced before retrieval begins (AGT-28)."""

    original_query: str
    topic_query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    soft_preferences: SoftPreferences = Field(default_factory=SoftPreferences)
    source_policy: list[SourceCapability] = Field(
        default_factory=lambda: cast(list[SourceCapability], [])
    )
    filters_pushed_down: dict[str, list[str]] = Field(default_factory=dict)
    filters_enforced_post_merge: list[str] = Field(default_factory=list)


class FilterEditContract(BaseModel):
    """Shared filter review/edit contract for Streamlit, REST API, and Zotero add-on (ZAP-4A)."""

    original_query: str
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    soft_preferences: SoftPreferences = Field(default_factory=SoftPreferences)
    result_limit: int = 10


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
    search_plan: SearchPlan | None = None


class CollectionResult(BaseModel):
    """Resolved collection metadata used for write auditing."""

    key: str
    name: str
    parent_key: str | None = None
    reused: bool


class ItemWriteOutcome(BaseModel):
    """Per-item write result for partial-success reporting."""

    index: int
    title: str
    status: Literal["created", "unchanged", "failed"]
    item_key: str | None = None
    reason: str | None = None
    duplicate_strategy: Literal["doi", "title_author_hash"] | None = None
    retry_safe: bool = True


class WriteResult(BaseModel):
    """Typed outcome for Zotero upsert operations."""

    created: int
    unchanged: int
    failed: int
    collection: CollectionResult
    outcomes: list[ItemWriteOutcome] = Field(
        default_factory=lambda: cast(list[ItemWriteOutcome], [])
    )
    retry_safe_failures: int = 0


class AgentState(TypedDict):
    """Serializable state used by the workflow engine."""

    request_id: str
    thread_id: str
    messages: list[str]
    papers: list[dict[str, Any]]
    collection_name: str | None
    approved: bool
    decision: Literal["approved", "rejected", "pending"]
    phase: Literal["search_complete", "awaiting_approval", "completed", "rejected", "failed"]
    selected_indices: list[int]
    preflight: dict[str, Any]
    trace_spans: list[dict[str, Any]]
    write_result: dict[str, Any] | None
    search_metadata: dict[str, Any] | None
