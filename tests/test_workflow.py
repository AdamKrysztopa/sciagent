from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agt.graph import workflow
from agt.models import NormalizedPaper
from agt.zotero.preflight import PreflightResult


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
    ) -> list[NormalizedPaper]:
        _ = limit
        _ = settings
        _ = thread_id
        return [NormalizedPaper(title=f"result:{query}")]

    async def fake_upsert(collection_name: str, papers: list[NormalizedPaper]):
        @dataclass(slots=True)
        class _Result:
            created: int
            unchanged: int
            failed: int

        return _Result(created=1, unchanged=0, failed=0)

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
    assert state["preflight"]["ok"] is True
    span_names = [span["name"] for span in state["trace_spans"]]
    assert "provider_init" in span_names
    assert "zotero_preflight" in span_names
    assert "search" in span_names
    assert "summarize" in span_names
    assert "approval_checkpoint" in span_names
    assert "zotero_write" in span_names
    assert state["write_result"] == {"created": 1, "unchanged": 0, "failed": 0}


@pytest.mark.anyio
async def test_workflow_fails_fast_when_preflight_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflow, "get_settings", _fake_get_settings)
    monkeypatch.setattr(workflow, "configure_logging", _fake_configure_logging)
    monkeypatch.setattr(workflow, "build_provider", _fake_build_provider)
    monkeypatch.setattr(workflow, "run_zotero_preflight", _fake_preflight_fail)

    with pytest.raises(RuntimeError, match="missing write scope"):
        await workflow.run_workflow(query="q", collection_name="Inbox", approved=False)
