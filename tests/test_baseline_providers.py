"""Baseline provider regression: confirms keyless providers enabled with no API keys."""

from __future__ import annotations

import pytest

from agt.config import Settings
from agt.models import SearchMetadata
from agt.tools.query_constraints import SearchConstraintSpec
from agt.tools.search_papers import _build_retrieval_registry  # pyright: ignore[reportPrivateUsage]

_KEYLESS_PROVIDERS: frozenset[str] = frozenset({
    "openalex",
    "crossref",
    "arxiv",
    "europe_pmc",
    "pubmed",
    "semantic_scholar",
    "doaj",
})

_KEY_GATED_PROVIDERS: frozenset[str] = frozenset({"core", "dimensions", "google_scholar"})


def _no_key_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Return Settings with all key-gated provider keys absent."""
    for name in (
        "AGT_CORE_API_KEY",
        "CORE_API_KEY",
        "AGT_DIMENSIONS_KEY",
        "DIMENSIONS_KEY",
        "AGT_SERPAPI_KEY",
        "SERPAPI_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    return Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def test_keyless_providers_have_no_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """openalex, crossref, arxiv, europe_pmc, pubmed, semantic_scholar, doaj are always enabled."""
    settings = _no_key_settings(monkeypatch)
    constraints = SearchConstraintSpec(raw_query="test")
    registry = _build_retrieval_registry("test", 10, constraints, settings, None)
    by_name = {p.name: p for p in registry}
    for name in _KEYLESS_PROVIDERS:
        assert by_name[name].skip_reason is None, (
            f"Provider '{name}' unexpectedly skipped: skip_reason={by_name[name].skip_reason!r}"
        )


def test_key_gated_providers_have_no_key_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """core, dimensions, google_scholar are disabled when their API keys are absent."""
    settings = _no_key_settings(monkeypatch)
    constraints = SearchConstraintSpec(raw_query="test")
    registry = _build_retrieval_registry("test", 10, constraints, settings, None)
    by_name = {p.name: p for p in registry}
    for name in _KEY_GATED_PROVIDERS:
        assert by_name[name].skip_reason == "no_key", (
            f"Provider '{name}' should have skip_reason='no_key' without a key; "
            f"got skip_reason={by_name[name].skip_reason!r}"
        )


def test_search_metadata_baseline_mode_false_validates() -> None:
    """SearchMetadata(source_states={}, baseline_mode=False) can be constructed."""
    meta = SearchMetadata(
        original_query="test",
        regex_query="test",
        source_states={},
        baseline_mode=False,
    )
    assert meta.baseline_mode is False


def test_search_metadata_baseline_mode_defaults_false() -> None:
    """baseline_mode defaults to False when not provided."""
    meta = SearchMetadata(
        original_query="test",
        regex_query="test",
    )
    assert meta.baseline_mode is False
