"""Core domain models for papers and workflow state."""

from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

LibraryStatus = Literal["new", "in_library", "possible_duplicate"]
WatchStatus = Literal["new", "seen"]
ItemType = Literal["journal_article", "preprint", "conference_paper", "book_chapter", "other"]
SourceTerminalState = Literal[
    "queried", "skipped_no_key", "skipped_disabled", "rate_limited", "zero_results", "failed"
]


class HardFilters(BaseModel):
    """Filters that cannot be relaxed or overridden by LLM rewriting."""

    min_year: int | None = Field(default=None, ge=1900, le=2100)
    max_year: int | None = Field(default=None, ge=1900, le=2100)
    min_citations: int = Field(default=0, ge=0)
    max_citations: int | None = Field(default=None, ge=0)
    open_access_only: bool = False
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    author_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ranges(self) -> HardFilters:
        if (
            self.min_year is not None
            and self.max_year is not None
            and self.min_year > self.max_year
        ):
            raise ValueError("min_year must be <= max_year")
        if self.max_citations is not None and self.min_citations > self.max_citations:
            raise ValueError("min_citations must be <= max_citations")
        return self


class SoftPreferences(BaseModel):
    """Preferences that influence ranking but do not hard-filter results."""

    require_positive_community_perception: bool = False
    min_semantic_score: float = Field(default=0.0, ge=0.0)


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
    seed_dois: list[str] = Field(default_factory=list)


class FilterEditContract(BaseModel):
    """Shared filter review/edit contract for Streamlit, REST API, and Zotero add-on (ZAP-4A)."""

    original_query: str
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    soft_preferences: SoftPreferences = Field(default_factory=SoftPreferences)
    result_limit: int = Field(default=10, ge=1, le=50)
    seed_dois: list[str] = Field(default_factory=list)


class NormalizedAuthor(BaseModel):
    """Structured author record with optional cross-provider identifiers."""

    name: str
    family: str | None = None
    given: str | None = None
    orcid: str | None = None
    openalex_id: str | None = None
    s2_author_id: str | None = None
    affiliation: str | None = None
    source: str = ""

    def normalized_last(self) -> str:
        last = self.family or (self.name.split()[-1] if self.name else "")
        return last.lower().strip()


class ProvenanceField(BaseModel):
    """Records which provider supplied a value and what the raw form was."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: str
    raw: object = None
    note: str | None = None

    @field_serializer("raw")
    def _serialize_raw(
        self, value: object
    ) -> str | int | float | bool | dict[str, object] | list[object] | None:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value  # type: ignore[return-value]  # narrowed by isinstance
        if isinstance(value, dict):
            return cast(dict[str, object], value)
        if isinstance(value, list):
            return cast(list[object], value)
        return str(value)


class FieldConflictValue(BaseModel):
    """One side of a field conflict: which provider supplied it and what value."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: str
    value: object = None

    @field_serializer("value")
    def _serialize_value(
        self, v: object
    ) -> str | int | float | bool | list[object] | dict[str, object] | None:
        if v is None or isinstance(v, (str, int, float, bool)):
            return v  # type: ignore[return-value]  # narrowed by isinstance
        if isinstance(v, list):
            return cast(list[object], v)
        if isinstance(v, dict):
            return cast(dict[str, object], v)
        return str(v)


class FieldConflict(BaseModel):
    """Records a disagreement between providers on a specific field."""

    field: str
    values: list[FieldConflictValue]


class NormalizedPaper(BaseModel):
    """Canonical paper representation used across providers and UI."""

    title: str
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    authors: list[NormalizedAuthor] = Field(
        default_factory=lambda: cast(list[NormalizedAuthor], [])
    )
    url: str | None = None
    pdf_url: str | None = None
    source: str = "semantic_scholar"
    index: int | None = None
    semantic_score: float = 0.0
    citation_count: int = 0
    influential_citation_count: int = 0
    open_access: bool = False
    summary: str | None = None
    score: float = 0.0
    explanation: str | None = None
    library_status: LibraryStatus | None = None
    watch_status: WatchStatus | None = None
    venue: str | None = None
    item_type: ItemType | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    oa_url: str | None = None
    references: list[str] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)
    missing_reasons: dict[str, str] = Field(default_factory=dict)
    citation_relation: Literal["references", "cited_by"] | None = None
    sources: list[str] = Field(default_factory=list)
    provenance: dict[str, ProvenanceField] = Field(default_factory=dict)
    conflicts: list[FieldConflict] = Field(default_factory=lambda: cast(list[FieldConflict], []))

    @field_validator("authors", mode="before")
    @classmethod
    def _coerce_authors(cls, v: object) -> list[NormalizedAuthor]:
        if not isinstance(v, list):
            return []
        items = cast(list[object], v)
        result: list[NormalizedAuthor] = []
        for item in items:
            if isinstance(item, str):
                result.append(NormalizedAuthor(name=item))
            elif isinstance(item, NormalizedAuthor):
                result.append(item)
            elif isinstance(item, dict):
                result.append(NormalizedAuthor.model_validate(cast(dict[str, object], item)))
        return result


class SearchMetadata(BaseModel):
    """Execution metadata captured for each search request."""

    original_query: str
    rewritten_query: str | None = None
    regex_query: str
    sources_used: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    source_states: dict[str, SourceTerminalState] = Field(default_factory=dict)
    mode: Literal["llm_rewrite", "regex"] = "regex"
    retry_count: int = 0
    total_fetched: int = 0
    total_after_filter: int = 0
    source_timings: dict[str, float] = Field(default_factory=dict)
    search_plan: SearchPlan | None = None
    baseline_mode: bool = False


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


class DoctorIssue(BaseModel):
    """A single item-level issue found by the Library Doctor."""

    item_key: str
    title: str
    issue_types: list[Literal["missing_doi", "missing_abstract", "missing_pdf", "duplicate"]]
    duplicate_of: str | None = None  # item_key of the duplicate


class DoctorReport(BaseModel):
    """Aggregate health report for a Zotero collection (SCI-0303)."""

    collection_name: str
    total_items: int
    issues: list[DoctorIssue]
    duplicate_pairs: list[tuple[str, str]]  # pairs of (key, key)


class GapSuggestion(BaseModel):
    """LLM-suggested papers missing from a collection (SCI-0304)."""

    reasoning: str
    papers: list[NormalizedPaper]


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
