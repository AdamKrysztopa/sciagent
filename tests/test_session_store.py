"""Tests for session_store module (SCI-0203)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agt.session_store import SessionStore


@pytest.fixture()
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "sessions")


def _make_state(query: str = "attention mechanism") -> dict[str, Any]:
    return {
        "thread_id": "run-001",
        "papers": [{"title": "Attention Is All You Need", "index": 1}],
        "selected_indices": [],
        "collection_name": "Inbox",
        "phase": "search_complete",
        "search_metadata": {
            "original_query": query,
            "sources_used": ["semantic_scholar"],
            "sources_failed": [],
            "total_fetched": 1,
            "total_after_filter": 1,
            "search_plan": {
                "topic_query": query,
                "hard_filters": {"min_year": None, "open_access_only": False},
                "soft_preferences": {},
            },
        },
    }


def test_save_creates_json_file(store: SessionStore, tmp_path: Path) -> None:
    store.save("session-1", _make_state())
    assert (tmp_path / "sessions" / "session-1.json").exists()


def test_load_returns_saved_state(store: SessionStore) -> None:
    state = _make_state("transformer self-attention")
    store.save("session-1", state)
    loaded = store.load("session-1")
    assert loaded["session_id"] == "session-1"
    assert loaded["state"]["search_metadata"]["original_query"] == "transformer self-attention"


def test_load_missing_raises_key_error(store: SessionStore) -> None:
    with pytest.raises(KeyError):
        store.load("nonexistent")


def test_list_sessions_empty_dir(store: SessionStore) -> None:
    assert store.list_sessions() == []


def test_list_sessions_returns_summary(store: SessionStore) -> None:
    store.save("s1", _make_state("query one"))
    store.save("s2", _make_state("query two"))
    sessions = store.list_sessions()
    queries = {s["query"] for s in sessions}
    assert "query one" in queries
    assert "query two" in queries


def test_list_sessions_includes_paper_count(store: SessionStore) -> None:
    state = _make_state()
    state["papers"] = [{"title": "A"}, {"title": "B"}]
    store.save("s1", state)
    sessions = store.list_sessions()
    assert sessions[0]["paper_count"] == 2  # noqa: PLR2004


def test_extract_rerun_payload_contains_query(store: SessionStore) -> None:
    store.save("s1", _make_state("CRISPR gene editing"))
    payload = store.extract_rerun_payload("s1")
    assert payload["query"] == "CRISPR gene editing"


def test_extract_rerun_payload_contains_filter_edit(store: SessionStore) -> None:
    store.save("s1", _make_state())
    payload = store.extract_rerun_payload("s1")
    assert "filter_edit" in payload
    assert isinstance(payload["filter_edit"], dict)


def test_overwrite_existing_session(store: SessionStore) -> None:
    store.save("s1", _make_state("first"))
    store.save("s1", _make_state("second"))
    loaded = store.load("s1")
    assert loaded["state"]["search_metadata"]["original_query"] == "second"
