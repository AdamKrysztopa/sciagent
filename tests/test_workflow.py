from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agt.graph import workflow
from agt.models import CollectionResult, NormalizedPaper, SearchMetadata, WriteResult
from agt.zotero.preflight import PreflightResult

_SELECTED_COUNT = 2


@dataclass(slots=True)
class _FakeRuntime:
    provider: str = "xai"
    model_name: str = "grok-4"
    timeout_seconds: int = 30
    retries: int = 3
    temperature: float = 0.2


@dataclass(slots=True)
class _FakeSettings:
    log_level: str = "INFO"
    runtime: _FakeRuntime = field(default_factory=_FakeRuntime)
    semantic_scholar_rate_limit_per_minute: int = 100
    openalex_rate_limit_per_minute: int = 100
    crossref_rate_limit_per_minute: int = 80
    pubmed_rate_limit_per_minute: int = 100
    europe_pmc_rate_limit_per_minute: int = 100
    core_rate_limit_per_minute: int = 60
    arxiv_rate_limit_per_minute: int = 20
    opencitations_rate_limit_per_minute: int = 60
    base_rate_limit_per_minute: int = 40
    dimensions_rate_limit_per_minute: int = 40
    google_scholar_rate_limit_per_minute: int = 20
    zotero_rate_limit_per_minute: int = 60
    llm_rate_limit_per_minute: int = 120
    workflow_max_cost_usd: float = 0.5
    summarization_use_llm: bool = False
    summarization_max_sentences: int = 4


def _fake_get_settings() -> _FakeSettings:
    return _FakeSettings()


def _fake_configure_logging(level: str) -> None:
    _ = level


def _fake_build_provider(settings: object) -> object:
    _ = settings
    return object()


def _fake_preflight_ok(settings: object) -> PreflightResult:
    _ = settings
    return PreflightResult(
        ok=True,
        message="ok",
        can_read=True,
        can_write=True,
        key_valid=True,
    )


def _fake_preflight_fail(settings: object) -> PreflightResult:
    _ = settings
    return PreflightResult(
        ok=False,
        message="missing write scope",
        can_read=True,
        can_write=False,
        key_valid=True,
    )


@pytest.mark.anyio
async def test_workflow_contains_ids_preflight_and_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(
        query: str,
        limit: int = 10,
        *,
        settings: object | None = None,
        thread_id: str | None = None,
    ) -> tuple[list[NormalizedPaper], SearchMetadata]:
        _ = limit
        _ = settings
        _ = thread_id
        return (
            [NormalizedPaper(title=f"result:{query}")],
            SearchMetadata(original_query=query, regex_query=query),
        )

    async def fake_upsert(
        collection_name: str,
        papers: list[NormalizedPaper],
        *,
        settings: object | None = None,
    ):
        _ = collection_name
        _ = papers
        _ = settings
        return WriteResult(
            created=1,
            unchanged=0,
            failed=0,
            collection=CollectionResult(key="C123", name="Inbox", reused=True),
            retry_safe_failures=0,
        )

    monkeypatch.setattr(workflow, "get_settings", _fake_get_settings)
    monkeypatch.setattr(workflow, "configure_logging", _fake_configure_logging)
    monkeypatch.setattr(workflow, "build_provider", _fake_build_provider)
    monkeypatch.setattr(workflow, "run_zotero_preflight", _fake_preflight_ok)
    monkeypatch.setattr(workflow, "search_papers", fake_search)
    monkeypatch.setattr(workflow, "upsert_papers", fake_upsert)

    state = await workflow.run_workflow(
        query="test query",
        collection_name="Inbox",
        approved=True,
        thread_id="thread-1",
    )

    assert state["thread_id"] == "thread-1"
    assert state["request_id"]
    assert state["phase"] == "completed"
    assert state["decision"] == "approved"
    assert state["preflight"]["ok"] is True
    assert state["selected_indices"] == [0]
    assert len(state["papers"]) == 1
    assert isinstance(state["papers"][0], dict)
    span_names = [span["name"] for span in state["trace_spans"]]
    assert "provider_init" in span_names
    assert "zotero_preflight" in span_names
    assert "search" in span_names
    assert "summarize" in span_names
    assert "approval_checkpoint" in span_names
    assert "approval_decision" in span_names
    assert "zotero_write" in span_names
    write_result = state["write_result"]
    assert isinstance(write_result, dict)
    assert write_result["created"] == 1
    assert write_result["unchanged"] == 0
    assert write_result["failed"] == 0
    assert isinstance(write_result["collection"], dict)
    assert write_result["collection"]["key"] == "C123"
    assert state["search_metadata"] is not None


@pytest.mark.anyio
async def test_workflow_fails_fast_when_preflight_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflow, "get_settings", _fake_get_settings)
    monkeypatch.setattr(workflow, "configure_logging", _fake_configure_logging)
    monkeypatch.setattr(workflow, "build_provider", _fake_build_provider)
    monkeypatch.setattr(workflow, "run_zotero_preflight", _fake_preflight_fail)

    with pytest.raises(RuntimeError, match="missing write scope"):
        await workflow.run_workflow(query="q", collection_name="Inbox", approved=False)


@pytest.mark.anyio
async def test_finalize_reject_skips_write(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(
        query: str,
        limit: int = 10,
        *,
        settings: object | None = None,
        thread_id: str | None = None,
    ) -> tuple[list[NormalizedPaper], SearchMetadata]:
        _ = query
        _ = limit
        _ = settings
        _ = thread_id
        return (
            [NormalizedPaper(title="paper-1"), NormalizedPaper(title="paper-2")],
            SearchMetadata(original_query="q", regex_query="q"),
        )

    async def fail_upsert(
        collection_name: str,
        papers: list[NormalizedPaper],
        *,
        settings: object | None = None,
    ):
        _ = collection_name
        _ = papers
        _ = settings
        raise AssertionError("upsert must not be called when rejected")

    monkeypatch.setattr(workflow, "get_settings", _fake_get_settings)
    monkeypatch.setattr(workflow, "configure_logging", _fake_configure_logging)
    monkeypatch.setattr(workflow, "build_provider", _fake_build_provider)
    monkeypatch.setattr(workflow, "run_zotero_preflight", _fake_preflight_ok)
    monkeypatch.setattr(workflow, "search_papers", fake_search)
    monkeypatch.setattr(workflow, "upsert_papers", fail_upsert)

    checkpoint = await workflow.run_search_phase(
        query="q",
        collection_name="Inbox",
        thread_id="thread-x",
    )
    rejected = await workflow.finalize_approval(
        checkpoint,
        approved=False,
        selected_indices=[0],
    )

    assert rejected["thread_id"] == "thread-x"
    assert rejected["phase"] == "rejected"
    assert rejected["decision"] == "rejected"
    assert rejected["approved"] is False
    assert rejected["write_result"] is None
    assert rejected["selected_indices"] == [0]


@pytest.mark.anyio
async def test_finalize_approval_supports_selection_and_collection_rename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_search(
        query: str,
        limit: int = 10,
        *,
        settings: object | None = None,
        thread_id: str | None = None,
    ) -> tuple[list[NormalizedPaper], SearchMetadata]:
        _ = query
        _ = limit
        _ = settings
        _ = thread_id
        return (
            [
                NormalizedPaper(title="paper-1"),
                NormalizedPaper(title="paper-2"),
                NormalizedPaper(title="paper-3"),
            ],
            SearchMetadata(original_query="q", regex_query="q"),
        )

    call_args: dict[str, object] = {}

    async def fake_upsert(
        collection_name: str,
        papers: list[NormalizedPaper],
        *,
        settings: object | None = None,
    ) -> WriteResult:
        _ = settings
        call_args["collection_name"] = collection_name
        call_args["paper_titles"] = [paper.title for paper in papers]
        return WriteResult(
            created=len(papers),
            unchanged=0,
            failed=0,
            collection=CollectionResult(key="C55", name=collection_name, reused=False),
            retry_safe_failures=0,
        )

    monkeypatch.setattr(workflow, "get_settings", _fake_get_settings)
    monkeypatch.setattr(workflow, "configure_logging", _fake_configure_logging)
    monkeypatch.setattr(workflow, "build_provider", _fake_build_provider)
    monkeypatch.setattr(workflow, "run_zotero_preflight", _fake_preflight_ok)
    monkeypatch.setattr(workflow, "search_papers", fake_search)
    monkeypatch.setattr(workflow, "upsert_papers", fake_upsert)

    checkpoint = await workflow.run_search_phase(query="q", collection_name="Inbox")
    approved = await workflow.finalize_approval(
        checkpoint,
        approved=True,
        collection_name="Renamed Collection",
        selected_indices=[1, 2],
    )

    assert call_args["collection_name"] == "Renamed Collection"
    assert call_args["paper_titles"] == ["paper-2", "paper-3"]
    assert approved["phase"] == "completed"
    assert approved["decision"] == "approved"
    assert approved["approved"] is True
    assert approved["selected_indices"] == [1, 2]
    assert isinstance(approved["write_result"], dict)
    assert approved["write_result"]["created"] == _SELECTED_COUNT
