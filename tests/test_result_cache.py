"""Tests for result_cache module (SCI-0204)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from agt.result_cache import ResultCache

_FILTERS: dict[str, object] = {"min_year": None, "open_access_only": False}
_DATA: dict[str, object] = {
    "papers": [{"title": "Test Paper"}],
    "search_metadata": {"original_query": "test"},
}


@pytest.fixture()
def cache(tmp_path: Path) -> ResultCache:
    return ResultCache(tmp_path / "cache", ttl_seconds=3600)


def test_get_returns_none_on_miss(cache: ResultCache) -> None:
    assert cache.get("missing query", _FILTERS, 10) is None


def test_set_and_get_roundtrip(cache: ResultCache) -> None:
    cache.set("attention", _FILTERS, 10, _DATA)
    result = cache.get("attention", _FILTERS, 10)
    assert result is not None
    assert result["papers"][0]["title"] == "Test Paper"  # type: ignore[index]


def test_get_case_insensitive_query(cache: ResultCache) -> None:
    cache.set("Attention Mechanism", _FILTERS, 10, _DATA)
    result = cache.get("attention mechanism", _FILTERS, 10)
    assert result is not None


def test_different_limit_is_cache_miss(cache: ResultCache) -> None:
    cache.set("attention", _FILTERS, 10, _DATA)
    assert cache.get("attention", _FILTERS, 20) is None


def test_different_filter_is_cache_miss(cache: ResultCache) -> None:
    cache.set("attention", _FILTERS, 10, _DATA)
    other_filters: dict[str, object] = {"min_year": 2020, "open_access_only": False}
    assert cache.get("attention", other_filters, 10) is None


def test_stats_shows_counts(cache: ResultCache) -> None:
    cache.set("q1", _FILTERS, 10, _DATA)
    cache.set("q2", _FILTERS, 5, _DATA)
    stats = cache.stats()
    assert stats["total_entries"] == 2  # noqa: PLR2004
    assert stats["active_entries"] == 2  # noqa: PLR2004
    assert stats["expired_entries"] == 0


def test_clear_removes_all(cache: ResultCache) -> None:
    cache.set("q1", _FILTERS, 10, _DATA)
    cache.set("q2", _FILTERS, 10, _DATA)
    deleted = cache.clear()
    assert deleted == 2  # noqa: PLR2004
    assert cache.stats()["total_entries"] == 0


def test_clear_expired_only(tmp_path: Path) -> None:
    short_cache = ResultCache(tmp_path / "cache2", ttl_seconds=1)
    short_cache.set("old", _FILTERS, 10, _DATA)
    time.sleep(1.1)
    short_cache.set("new", _FILTERS, 5, _DATA)
    deleted = short_cache.clear(expired_only=True)
    assert deleted == 1
    assert short_cache.get("new", _FILTERS, 5) is not None


def test_expired_entry_returns_none(tmp_path: Path) -> None:
    tiny_cache = ResultCache(tmp_path / "cache3", ttl_seconds=1)
    tiny_cache.set("attention", _FILTERS, 10, _DATA)
    time.sleep(1.1)
    assert tiny_cache.get("attention", _FILTERS, 10) is None


def test_set_overwrites_existing(cache: ResultCache) -> None:
    cache.set("q", _FILTERS, 10, _DATA)
    new_data: dict[str, object] = {"papers": [{"title": "Updated"}], "search_metadata": {}}
    cache.set("q", _FILTERS, 10, new_data)
    result = cache.get("q", _FILTERS, 10)
    assert result is not None
    assert result["papers"][0]["title"] == "Updated"  # type: ignore[index]
