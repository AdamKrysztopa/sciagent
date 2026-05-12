"""Tests for watch_store module (SCI-0401)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agt.watch_store import Watch, WatchStore, create_watch


@pytest.fixture()
def store(tmp_path: Path) -> WatchStore:
    return WatchStore(tmp_path / "watches")


def _make_watch(name: str = "Test Watch", query: str = "CRISPR") -> Watch:
    return create_watch(name, query, collection_name="BioMed")


def test_create_watch_has_uuid_id() -> None:
    watch = _make_watch()
    assert len(watch.id) == 36  # UUID4 format  # noqa: PLR2004
    assert watch.seen_fingerprints == []
    assert watch.last_run_at is None


def test_save_creates_json_file(store: WatchStore, tmp_path: Path) -> None:
    watch = _make_watch()
    store.save(watch)
    assert (tmp_path / "watches" / f"{watch.id}.json").exists()


def test_load_returns_saved_watch(store: WatchStore) -> None:
    watch = _make_watch("My Watch", "transformer attention")
    store.save(watch)
    loaded = store.load(watch.id)
    assert loaded.name == "My Watch"
    assert loaded.query == "transformer attention"
    assert loaded.collection_name == "BioMed"


def test_load_missing_raises_key_error(store: WatchStore) -> None:
    with pytest.raises(KeyError):
        store.load("nonexistent-id")


def test_delete_removes_file(store: WatchStore) -> None:
    watch = _make_watch()
    store.save(watch)
    store.delete(watch.id)
    with pytest.raises(KeyError):
        store.load(watch.id)


def test_delete_missing_raises_key_error(store: WatchStore) -> None:
    with pytest.raises(KeyError):
        store.delete("nonexistent-id")


def test_list_watches_empty_dir(store: WatchStore) -> None:
    assert store.list_watches() == []


def test_list_watches_returns_all(store: WatchStore) -> None:
    w1 = create_watch("Watch A", "quantum computing")
    w2 = create_watch("Watch B", "protein folding")
    store.save(w1)
    store.save(w2)
    watches = store.list_watches()
    names = {w.name for w in watches}
    assert "Watch A" in names
    assert "Watch B" in names


def test_overwrite_updates_watch(store: WatchStore) -> None:
    watch = _make_watch()
    store.save(watch)
    watch.last_run_at = "2026-05-12T12:00:00+00:00"
    watch.seen_fingerprints = ["fp1", "fp2"]
    store.save(watch)
    loaded = store.load(watch.id)
    assert loaded.last_run_at == "2026-05-12T12:00:00+00:00"
    assert loaded.seen_fingerprints == ["fp1", "fp2"]


def test_watch_with_filter_edit_round_trips(store: WatchStore) -> None:
    fe: dict[str, object] = {
        "original_query": "CRISPR",
        "hard_filters": {"min_year": 2022, "open_access_only": True},
        "soft_preferences": {},
        "result_limit": 5,
    }
    watch = create_watch("Filtered Watch", "CRISPR", filter_edit=fe)
    store.save(watch)
    loaded = store.load(watch.id)
    assert loaded.filter_edit is not None
    assert loaded.filter_edit["hard_filters"]["min_year"] == 2022  # noqa: PLR2004
