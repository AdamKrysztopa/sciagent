from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import examples.search as search_example
from agt.models import NormalizedPaper, SearchMetadata


@pytest.mark.anyio
async def test_run_prints_progress_updates(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _noop_configure_guardrails(settings: object) -> None:
        _ = settings

    async def fake_search_papers(
        query: str,
        limit: int = 10,
        **kwargs: Any,
    ) -> tuple[list[NormalizedPaper], SearchMetadata]:
        _ = limit
        _ = kwargs
        progress = kwargs.get("progress")
        assert callable(progress)
        progress("retrieving primary sources")
        progress("reranking and filtering merged results")
        return (
            [NormalizedPaper(title="Time series forecasting", year=2025, semantic_score=0.6)],
            SearchMetadata(
                original_query=query,
                regex_query=query,
                sources_used=["semantic_scholar:primary"],
                total_fetched=1,
                total_after_filter=1,
            ),
        )

    monkeypatch.setattr(search_example, "configure_guardrails", _noop_configure_guardrails)
    monkeypatch.setattr(search_example, "search_papers", fake_search_papers)

    args = argparse.Namespace(
        search="time series forecasting",
        min_year=None,
        max_year=None,
        min_citations=None,
        open_access=False,
        must_include="",
        exclude="",
        limit=5,
        no_llm=True,
        verbose=False,
        json_output=None,
    )

    exit_code = await search_example.run_with_args(args)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "retrieving primary sources" in captured.out
    assert "reranking and filtering merged results" in captured.out
    assert "Results (1 returned):" in captured.out
