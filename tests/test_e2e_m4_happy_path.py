from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agt.graph import workflow
from agt.models import CollectionResult, NormalizedPaper, SearchMetadata, WriteResult
from agt.zotero.preflight import PreflightResult

_EXPECTED_PAPER_COUNT = 2


@dataclass(slots=True)
class _FakeRuntime:
    provider: str = "xai"
    model_name: str = "grok-4"
    timeout_seconds: int = 30
    retries: int = 2
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


def _fake_preflight_ok(settings: object) -> PreflightResult:
    _ = settings
    return PreflightResult(
        ok=True,
        message="ok",
        can_read=True,
        can_write=True,
        key_valid=True,
    )


def _fake_build_provider(settings: object) -> object:
    _ = settings
    return object()


def _fake_configure_logging(level: str) -> None:
    _ = level


@pytest.mark.anyio
async def test_m4_end_to_end_happy_path_with_mocked_externals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            [
                NormalizedPaper(title=f"{query}-A", doi="10.1000/a", authors=["Ada Lovelace"]),
                NormalizedPaper(title=f"{query}-B", doi="10.1000/b", authors=["Grace Hopper"]),
            ],
            SearchMetadata(original_query=query, regex_query=query),
        )

    async def fake_upsert(
        collection_name: str,
        papers: list[NormalizedPaper],
        *,
        settings: object | None = None,
    ) -> WriteResult:
        _ = settings
        return WriteResult(
            created=len(papers),
            unchanged=0,
            failed=0,
            collection=CollectionResult(key="C777", name=collection_name, reused=True),
            retry_safe_failures=0,
        )

    monkeypatch.setattr(workflow, "get_settings", _fake_get_settings)
    monkeypatch.setattr(workflow, "configure_logging", _fake_configure_logging)
    monkeypatch.setattr(workflow, "build_provider", _fake_build_provider)
    monkeypatch.setattr(workflow, "run_zotero_preflight", _fake_preflight_ok)
    monkeypatch.setattr(workflow, "search_papers", fake_search)
    monkeypatch.setattr(workflow, "upsert_papers", fake_upsert)

    checkpoint = await workflow.run_search_phase(
        query="rag systems",
        collection_name="Inbox",
        thread_id="m4-thread-1",
    )
    assert checkpoint["phase"] == "awaiting_approval"
    assert checkpoint["decision"] == "pending"
    assert checkpoint["approved"] is False
    assert len(checkpoint["papers"]) == _EXPECTED_PAPER_COUNT

    final = await workflow.finalize_approval(
        checkpoint,
        approved=True,
        collection_name="AGT MVP",
        selected_indices=[0],
    )

    assert final["phase"] == "completed"
    assert final["decision"] == "approved"
    assert final["approved"] is True
    assert final["collection_name"] == "AGT MVP"
    assert final["selected_indices"] == [0]

    write_result = final["write_result"]
    assert isinstance(write_result, dict)
    assert write_result["created"] == 1
    assert write_result["unchanged"] == 0
    assert write_result["failed"] == 0
    collection = write_result["collection"]
    assert isinstance(collection, dict)
    assert collection["key"] == "C777"
    assert collection["name"] == "AGT MVP"

    span_names = [span["name"] for span in final["trace_spans"]]
    assert "search" in span_names
    assert "approval_checkpoint" in span_names
    assert "approval_decision" in span_names
    assert "zotero_write" in span_names
