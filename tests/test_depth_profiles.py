"""Tests for DEPTH_PROFILES and select_providers_for_depth.

Coverage:
1. DEPTH_PROFILES has exactly the three keys: "quick", "balanced", "deep".
2. "quick" providers list is ["openalex", "arxiv"].
3. "balanced" providers list includes all 6 baseline providers.
4. "deep" providers list is a superset of "balanced".
5. select_providers_for_depth(registry, "quick") with mixed registry returns
   depth-active providers + skipped (no_key) providers.
6. select_providers_for_depth(registry, None) falls back to "balanced" behavior.
7. A provider not in the depth profile is excluded when it has no skip_reason.
"""

from __future__ import annotations

from typing import Literal

from agt.models import NormalizedPaper
from agt.tools.search_papers import (
    DEPTH_PROFILES,
    _RetrievalProvider,  # pyright: ignore[reportPrivateUsage]
    select_providers_for_depth,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _noop() -> list[NormalizedPaper]:
    return []


def _make_provider(
    name: str,
    *,
    skip_reason: Literal["no_key", "disabled"] | None = None,
) -> _RetrievalProvider:
    return _RetrievalProvider(
        name=name,
        tier="primary",
        enabled=skip_reason is None,
        fetcher=_noop,
        skip_reason=skip_reason,
    )


def _names(registry: list[_RetrievalProvider]) -> list[str]:
    return [p.name for p in registry]


# ---------------------------------------------------------------------------
# DEPTH_PROFILES structure
# ---------------------------------------------------------------------------


def test_depth_profiles_has_exactly_three_keys() -> None:
    assert set(DEPTH_PROFILES.keys()) == {"quick", "balanced", "deep"}


def test_quick_providers_list() -> None:
    assert DEPTH_PROFILES["quick"]["providers"] == ["openalex", "arxiv"]


def test_balanced_providers_include_all_six_baseline() -> None:
    baseline = {"openalex", "crossref", "europe_pmc", "doaj", "pubmed", "arxiv"}
    balanced_set = set(DEPTH_PROFILES["balanced"]["providers"])
    assert baseline.issubset(balanced_set)


def test_deep_is_superset_of_balanced() -> None:
    balanced_set = set(DEPTH_PROFILES["balanced"]["providers"])
    deep_set = set(DEPTH_PROFILES["deep"]["providers"])
    assert balanced_set.issubset(deep_set)


def test_depth_profiles_required_keys() -> None:
    for depth, profile in DEPTH_PROFILES.items():
        assert "providers" in profile, f"{depth} missing 'providers'"
        assert "limit_per_provider" in profile, f"{depth} missing 'limit_per_provider'"
        assert "expand_refs" in profile, f"{depth} missing 'expand_refs'"
        assert "timeout" in profile, f"{depth} missing 'timeout'"


# ---------------------------------------------------------------------------
# select_providers_for_depth
# ---------------------------------------------------------------------------


def test_quick_depth_keeps_active_and_skipped() -> None:
    """Enabled providers in 'quick' profile + skipped providers are returned."""
    registry = [
        _make_provider("openalex"),
        _make_provider("arxiv"),
        _make_provider("core", skip_reason="no_key"),
    ]
    result = select_providers_for_depth(registry, "quick")
    result_names = _names(result)
    assert "openalex" in result_names
    assert "arxiv" in result_names
    assert "core" in result_names  # skipped provider preserved in output
    assert len(result) == len(registry)


def test_quick_depth_excludes_enabled_providers_not_in_profile() -> None:
    """Enabled providers NOT in the 'quick' profile are excluded."""
    registry = [
        _make_provider("openalex"),
        _make_provider("arxiv"),
        _make_provider("semantic_scholar"),  # not in quick
        _make_provider("crossref"),  # not in quick
    ]
    result = select_providers_for_depth(registry, "quick")
    result_names = _names(result)
    assert "openalex" in result_names
    assert "arxiv" in result_names
    assert "semantic_scholar" not in result_names
    assert "crossref" not in result_names


def test_none_depth_returns_full_registry() -> None:
    """depth=None should return the complete registry without filtering."""
    registry = [
        _make_provider("openalex"),
        _make_provider("arxiv"),
        _make_provider("crossref"),
        _make_provider("europe_pmc"),
        _make_provider("doaj"),
        _make_provider("pubmed"),
        _make_provider("semantic_scholar"),  # would be excluded at "balanced" depth
        _make_provider("core", skip_reason="no_key"),
    ]
    result = select_providers_for_depth(registry, None)
    assert _names(result) == _names(registry)


def test_provider_not_in_profile_excluded_when_enabled() -> None:
    """An enabled provider absent from the depth profile is excluded."""
    registry = [
        _make_provider("openalex"),
        _make_provider("dimensions"),  # not in quick, not skipped
    ]
    result = select_providers_for_depth(registry, "quick")
    result_names = _names(result)
    assert "openalex" in result_names
    assert "dimensions" not in result_names


def test_deep_profile_includes_semantic_scholar() -> None:
    """semantic_scholar should be active at deep depth."""
    registry = [
        _make_provider("semantic_scholar"),
        _make_provider("openalex"),
        _make_provider("base"),
    ]
    result = select_providers_for_depth(registry, "deep")
    result_names = _names(result)
    assert "semantic_scholar" in result_names
    assert "openalex" in result_names
    assert "base" in result_names


def test_disabled_skip_reason_preserved() -> None:
    """Providers with skip_reason='disabled' are preserved regardless of depth."""
    registry = [
        _make_provider("openalex"),
        _make_provider("crossref", skip_reason="disabled"),
    ]
    result = select_providers_for_depth(registry, "quick")
    result_names = _names(result)
    assert "crossref" in result_names  # kept because skip_reason is set
