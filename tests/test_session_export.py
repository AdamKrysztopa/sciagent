"""Tests for session_export module (SCI-0206)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from agt.session_export import export_session


def _make_state(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "thread_id": "run-abc",
        "papers": [
            {
                "index": 1,
                "title": "Attention Is All You Need",
                "year": 2017,
                "authors": ["Vaswani", "Shazeer"],
                "doi": "10.1234/attn",
                "source": "semantic_scholar",
                "score": 0.92,
                "open_access": True,
                "url": "https://arxiv.org/abs/1706.03762",
                "explanation": "high semantic match · 3 keyword hits",
            },
        ],
        "selected_indices": [1],
        "search_metadata": {
            "original_query": "transformer attention mechanism",
            "sources_used": ["semantic_scholar", "openalex"],
            "sources_failed": [],
            "total_fetched": 50,
            "total_after_filter": 1,
            "search_plan": {
                "topic_query": "transformer attention mechanism",
                "rewritten_queries": ["attention-based neural architectures"],
                "hard_filters": {
                    "min_year": 2015,
                    "max_year": None,
                    "min_citations": 0,
                    "max_citations": None,
                    "open_access_only": False,
                    "include_keywords": [],
                    "exclude_keywords": [],
                },
                "soft_preferences": {
                    "require_positive_community_perception": False,
                    "min_semantic_score": 0.0,
                },
            },
        },
        "write_result": None,
    }
    base.update(overrides)
    return base


def test_markdown_contains_query() -> None:
    result = export_session(_make_state(), "markdown")
    assert "transformer attention mechanism" in result


def test_markdown_contains_paper_title() -> None:
    result = export_session(_make_state(), "markdown")
    assert "Attention Is All You Need" in result


def test_markdown_marks_selected_with_checkmark() -> None:
    result = export_session(_make_state(), "markdown")
    assert "✓" in result


def test_markdown_includes_search_plan_section() -> None:
    result = export_session(_make_state(), "markdown")
    assert "Search Plan" in result
    assert "transformer attention mechanism" in result


def test_markdown_sources_section() -> None:
    result = export_session(_make_state(), "markdown")
    assert "semantic_scholar" in result
    assert "openalex" in result


def test_markdown_includes_explanation() -> None:
    result = export_session(_make_state(), "markdown")
    assert "high semantic match" in result


def test_markdown_run_id_included_when_provided() -> None:
    result = export_session(_make_state(), "markdown", run_id="my-run-42")
    assert "my-run-42" in result


def test_json_format_is_valid_json() -> None:
    result = export_session(_make_state(), "json")
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
    assert "papers" in parsed


def test_csv_format_has_header_and_row() -> None:
    result = export_session(_make_state(), "csv")
    reader = csv.DictReader(io.StringIO(result))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["title"] == "Attention Is All You Need"
    assert rows[0]["selected"] == "yes"
    assert rows[0]["open_access"] == "yes"


def test_csv_unselected_paper_shows_no() -> None:
    state = _make_state(selected_indices=[])
    result = export_session(state, "csv")
    reader = csv.DictReader(io.StringIO(result))
    rows = list(reader)
    assert rows[0]["selected"] == "no"


def test_empty_papers_produces_valid_csv() -> None:
    state = _make_state(papers=[], selected_indices=[])
    result = export_session(state, "csv")
    reader = csv.DictReader(io.StringIO(result))
    rows = list(reader)
    assert rows == []


def test_markdown_write_outcome_section() -> None:
    state = _make_state(
        write_result={
            "created": 1,
            "unchanged": 0,
            "failed": 0,
            "collection": {"name": "My Papers", "key": "ABC123"},
        }
    )
    result = export_session(state, "markdown")
    assert "Write Outcome" in result
    assert "My Papers" in result
