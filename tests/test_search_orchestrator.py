"""Tests for _build_retrieval_registry and SearchRunResult (P8.12-E)."""

from __future__ import annotations

import pytest

from agt.config import Settings
from agt.models import NormalizedPaper
from agt.tools.capabilities import ProviderHealth
from agt.tools.query_constraints import SearchConstraintSpec
from agt.tools.search_papers import (
    SearchRunResult,
    _build_retrieval_registry,  # pyright: ignore[reportPrivateUsage]
)

# ---------------------------------------------------------------------------
# Named constants (avoids PLR2004 magic value lint errors)
# ---------------------------------------------------------------------------

_KEYLESS_PROVIDER_NAMES: frozenset[str] = frozenset({
    "semantic_scholar",
    "openalex",
    "crossref",
    "pubmed",
    "europe_pmc",
    "arxiv",
    "doaj",
    "base",
})

_KEY_GATED_PROVIDER_NAMES: frozenset[str] = frozenset({
    "core",
    "dimensions",
    "google_scholar",
})

_QUERY = "climate change mitigation"
_LIMIT = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_key_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure provider key env vars are absent for isolated test runs."""
    for var in (
        "AGT_CORE_API_KEY",
        "CORE_API_KEY",
        "AGT_DIMENSIONS_KEY",
        "DIMENSIONS_KEY",
        "AGT_SERPAPI_KEY",
        "SERPAPI_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


def _base_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Build a Settings instance with no provider API keys set."""
    _clear_key_env_vars(monkeypatch)
    return Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def _constraints() -> SearchConstraintSpec:
    return SearchConstraintSpec(raw_query=_QUERY)


# ---------------------------------------------------------------------------
# Test 1: Keyless providers have no skip_reason
# ---------------------------------------------------------------------------


def test_keyless_providers_have_no_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """All keyless providers must appear in the registry with skip_reason=None."""
    settings = _base_settings(monkeypatch)
    registry = _build_retrieval_registry(_QUERY, _LIMIT, _constraints(), settings, None)
    by_name = {entry.name: entry for entry in registry}
    for name in _KEYLESS_PROVIDER_NAMES:
        assert name in by_name, f"expected keyless provider {name!r} in registry"
        assert by_name[name].skip_reason is None, (
            f"{name}: expected skip_reason=None, got {by_name[name].skip_reason!r}"
        )


# ---------------------------------------------------------------------------
# Test 2: Keyed providers have skip_reason="no_key" when keys are absent
# ---------------------------------------------------------------------------


def test_keyed_providers_have_no_key_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """core, dimensions, google_scholar must have skip_reason='no_key' when keys absent."""
    settings = _base_settings(monkeypatch)
    registry = _build_retrieval_registry(_QUERY, _LIMIT, _constraints(), settings, None)
    by_name = {entry.name: entry for entry in registry}
    for name in _KEY_GATED_PROVIDER_NAMES:
        assert name in by_name, f"expected key-gated provider {name!r} in registry"
        assert by_name[name].skip_reason == "no_key", (
            f"{name}: expected skip_reason='no_key', got {by_name[name].skip_reason!r}"
        )


# ---------------------------------------------------------------------------
# Test 3: core with key set → skip_reason is None
# ---------------------------------------------------------------------------


def test_core_provider_with_key_has_no_skip_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """When core_api_key is provided, core's skip_reason must be None."""
    _clear_key_env_vars(monkeypatch)
    monkeypatch.setenv("AGT_CORE_API_KEY", "fake-core-key")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    registry = _build_retrieval_registry(_QUERY, _LIMIT, _constraints(), settings, None)
    by_name = {entry.name: entry for entry in registry}
    assert "core" in by_name
    assert by_name["core"].skip_reason is None


# ---------------------------------------------------------------------------
# Test 4: SearchRunResult can be constructed with expected fields
# ---------------------------------------------------------------------------


def test_search_run_result_construction() -> None:
    """SearchRunResult must be constructable from per_provider, errors, health."""
    paper = NormalizedPaper(title="Test paper", source="openalex")
    result = SearchRunResult(
        per_provider={"openalex": [paper]},
        errors={"crossref": "timeout"},
        health={"openalex": ProviderHealth()},
    )
    assert "openalex" in result.per_provider
    assert "crossref" in result.errors
    assert result.errors["crossref"] == "timeout"
    assert "openalex" in result.health


# ---------------------------------------------------------------------------
# Test 5: SearchRunResult.per_provider is dict[str, list[NormalizedPaper]]
# ---------------------------------------------------------------------------


def test_search_run_result_per_provider_type() -> None:
    """per_provider must map provider name strings to lists of NormalizedPaper."""
    papers: list[NormalizedPaper] = [
        NormalizedPaper(title="Paper One", source="openalex"),
        NormalizedPaper(title="Paper Two", source="openalex"),
    ]
    result = SearchRunResult(
        per_provider={"openalex": papers},
        errors={},
        health={},
    )
    provider_papers = result.per_provider["openalex"]
    assert isinstance(provider_papers, list)
    assert all(isinstance(p, NormalizedPaper) for p in provider_papers)


# ---------------------------------------------------------------------------
# Test 6: disabled_providers disables a keyless provider
# ---------------------------------------------------------------------------


def test_disabled_providers_disables_keyless_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """A keyless provider listed in disabled_providers must have skip_reason='disabled'."""
    _clear_key_env_vars(monkeypatch)
    monkeypatch.setenv("AGT_DISABLED_PROVIDERS", '["openalex"]')
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    registry = _build_retrieval_registry(_QUERY, _LIMIT, _constraints(), settings, None)
    by_name = {entry.name: entry for entry in registry}
    assert by_name["openalex"].skip_reason == "disabled"
    assert not by_name["openalex"].enabled


# ---------------------------------------------------------------------------
# Test 7: disabled_providers disables a keyed provider even when key is present
# ---------------------------------------------------------------------------


def test_disabled_providers_overrides_keyed_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """disabled_providers must disable a provider even when its API key is set."""
    _clear_key_env_vars(monkeypatch)
    monkeypatch.setenv("AGT_CORE_API_KEY", "fake-core-key")
    monkeypatch.setenv("AGT_DISABLED_PROVIDERS", '["core"]')
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    registry = _build_retrieval_registry(_QUERY, _LIMIT, _constraints(), settings, None)
    by_name = {entry.name: entry for entry in registry}
    assert by_name["core"].skip_reason == "disabled"
    assert not by_name["core"].enabled
