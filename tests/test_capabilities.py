"""Tests for capabilities.py, provider_base.py, and GET /providers endpoint.

Coverage:
1. SearchProviderCapabilities.supports() returns correct FieldSupport.
2. ProviderHealth defaults are correct.
3. ProviderStatus values are valid strings.
4. SearchProviderProtocol isinstance check passes for a conforming class.
5. SearchProviderBase._user_agent() with and without mailto.
6. GET /providers returns 200 with all expected provider names.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agt.api.app import create_app
from agt.config import get_settings
from agt.models import NormalizedPaper
from agt.tools.capabilities import (
    ALL_PROVIDER_CAPS,
    BASE_CAPS,
    CORE_PUBLIC_CAPS,
    DIMENSIONS_CAPS,
    OPENALEX_CAPS,
    PUBMED_CAPS,
    SEMANTIC_SCHOLAR_CAPS,
    FieldSupport,
    ProviderField,
    ProviderHealth,
    ProviderStatus,
    SearchProviderCapabilities,
)
from agt.tools.provider_base import SearchProviderBase, SearchProviderProtocol

HTTP_OK = 200

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeSettings:
    """Minimal settings stub — no API key so auth is skipped."""

    backend_api_key: None = None


# ---------------------------------------------------------------------------
# P8.1-A: SearchProviderCapabilities
# ---------------------------------------------------------------------------


def test_supports_returns_full_for_title() -> None:
    assert OPENALEX_CAPS.supports(ProviderField.TITLE) is FieldSupport.FULL


def test_supports_returns_none_for_missing_field() -> None:
    assert OPENALEX_CAPS.supports(ProviderField.REFERENCES) is FieldSupport.NONE


def test_supports_returns_shallow() -> None:
    assert BASE_CAPS.supports(ProviderField.ABSTRACT) is FieldSupport.SHALLOW


def test_capabilities_name_matches_registry_key() -> None:
    for name, caps in ALL_PROVIDER_CAPS.items():
        assert caps.name == name, f"Registry key {name!r} does not match caps.name {caps.name!r}"


def test_all_provider_fields_present_in_each_caps() -> None:
    """Every canonical caps table must have an entry for every ProviderField."""
    for name, caps in ALL_PROVIDER_CAPS.items():
        for field in ProviderField:
            assert field in caps.fields, f"{name}: missing field {field!r} in capabilities table"


# ---------------------------------------------------------------------------
# P8.1-A: ProviderHealth defaults
# ---------------------------------------------------------------------------


def test_provider_health_defaults() -> None:
    health = ProviderHealth()
    assert health.status is ProviderStatus.AVAILABLE
    assert health.reason == ""
    assert health.last_ok_at is None
    assert health.last_error_at is None
    assert health.consecutive_failures == 0
    assert health.retry_after is None


def test_provider_health_is_mutable() -> None:
    health = ProviderHealth()
    health.status = ProviderStatus.FAILED
    expected_failures = 3
    health.consecutive_failures = expected_failures
    assert health.status is ProviderStatus.FAILED
    assert health.consecutive_failures == expected_failures


# ---------------------------------------------------------------------------
# P8.1-A: ProviderStatus values are valid strings
# ---------------------------------------------------------------------------


def test_provider_status_values_are_strings() -> None:
    for member in ProviderStatus:
        assert isinstance(member.value, str)
        assert member.value  # non-empty


def test_field_support_values_are_strings() -> None:
    for member in FieldSupport:
        assert isinstance(member.value, str)
        assert member.value


# ---------------------------------------------------------------------------
# P8.1-B: SearchProviderProtocol isinstance check
# ---------------------------------------------------------------------------


class _ConformingProvider:
    """Minimal class that satisfies SearchProviderProtocol structurally."""

    def capabilities(self) -> SearchProviderCapabilities:
        return OPENALEX_CAPS

    def health(self) -> ProviderHealth:
        return ProviderHealth()

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]:
        return []


class _NonConformingProvider:
    """Class that does NOT satisfy SearchProviderProtocol."""

    def capabilities(self) -> SearchProviderCapabilities:
        return OPENALEX_CAPS

    # Missing health() and search()


def test_conforming_provider_passes_protocol_check() -> None:
    assert isinstance(_ConformingProvider(), SearchProviderProtocol)


def test_non_conforming_provider_fails_protocol_check() -> None:
    assert not isinstance(_NonConformingProvider(), SearchProviderProtocol)


# ---------------------------------------------------------------------------
# P8.1-B: SearchProviderBase user-agent
# ---------------------------------------------------------------------------


class _MinimalProvider(SearchProviderBase):
    """Minimal concrete subclass for testing SearchProviderBase."""

    capabilities_ = OPENALEX_CAPS

    async def _search_impl(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]:
        return []


@pytest.mark.anyio
async def test_user_agent_without_mailto() -> None:
    provider = _MinimalProvider()
    try:
        ua = provider._user_agent()  # pyright: ignore[reportPrivateUsage]
        assert ua.startswith("SciAgent/0.1")
        assert "mailto" not in ua
    finally:
        await provider.aclose()


@pytest.mark.anyio
async def test_user_agent_with_mailto() -> None:
    provider = _MinimalProvider(mailto="researcher@example.edu")
    try:
        ua = provider._user_agent()  # pyright: ignore[reportPrivateUsage]
        assert "mailto:researcher@example.edu" in ua
    finally:
        await provider.aclose()


@pytest.mark.anyio
async def test_search_provider_base_capabilities_returns_class_var() -> None:
    provider = _MinimalProvider()
    try:
        caps = provider.capabilities()
        assert caps is OPENALEX_CAPS
    finally:
        await provider.aclose()


@pytest.mark.anyio
async def test_search_provider_base_health_defaults() -> None:
    provider = _MinimalProvider()
    try:
        h = provider.health()
        assert h.status is ProviderStatus.AVAILABLE
        assert h.consecutive_failures == 0
    finally:
        await provider.aclose()


@pytest.mark.anyio
async def test_record_failure_updates_health() -> None:
    provider = _MinimalProvider()
    try:
        provider._record_failure(RuntimeError("timeout"))  # pyright: ignore[reportPrivateUsage]
        h = provider.health()
        assert h.status is ProviderStatus.FAILED
        assert h.consecutive_failures == 1
        assert "timeout" in h.reason
        assert h.last_error_at is not None
    finally:
        await provider.aclose()


@pytest.mark.anyio
async def test_record_success_resets_health() -> None:
    provider = _MinimalProvider()
    try:
        provider._record_failure(RuntimeError("transient"))  # pyright: ignore[reportPrivateUsage]
        provider._record_success()  # pyright: ignore[reportPrivateUsage]
        h = provider.health()
        assert h.status is ProviderStatus.AVAILABLE
        assert h.consecutive_failures == 0
        assert h.reason == ""
        assert h.last_ok_at is not None
    finally:
        await provider.aclose()


# ---------------------------------------------------------------------------
# P8.1-C: GET /providers endpoint
# ---------------------------------------------------------------------------

_EXPECTED_PROVIDER_NAMES = {
    "openalex",
    "crossref",
    "arxiv",
    "europe_pmc",
    "doaj",
    "semantic_scholar",
    "core",
    "pubmed",
    "base",
    "opencitations",
    "dimensions",
    "google_scholar",
}


def test_get_providers_returns_200_with_all_names(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _FakeSettings:
        return _FakeSettings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.get("/providers")

    app.dependency_overrides.clear()

    assert resp.status_code == HTTP_OK
    data: dict[str, object] = resp.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == _EXPECTED_PROVIDER_NAMES


def test_get_providers_each_entry_has_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _FakeSettings:
        return _FakeSettings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.get("/providers")

    app.dependency_overrides.clear()

    assert resp.status_code == HTTP_OK
    for name, info in resp.json().items():
        assert "name" in info, f"{name}: missing 'name'"
        assert "fields" in info, f"{name}: missing 'fields'"
        assert "requires_key" in info, f"{name}: missing 'requires_key'"
        assert "status" in info, f"{name}: missing 'status'"
        assert "consecutive_failures" in info, f"{name}: missing 'consecutive_failures'"
        # fields dict maps string keys to string values
        for field_key, field_val in info["fields"].items():
            assert isinstance(field_key, str)
            assert isinstance(field_val, str)


def test_get_providers_key_required_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _FakeSettings:
        return _FakeSettings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.get("/providers")

    app.dependency_overrides.clear()

    data = resp.json()
    assert data["core"]["requires_key"] is True
    assert data["dimensions"]["requires_key"] is True
    assert data["google_scholar"]["requires_key"] is True
    assert data["openalex"]["requires_key"] is False
    assert data["arxiv"]["requires_key"] is False


def test_get_providers_health_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _FakeSettings:
        return _FakeSettings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.get("/providers")

    app.dependency_overrides.clear()

    for _name, info in resp.json().items():
        assert info["status"] == "available"
        assert info["consecutive_failures"] == 0
        assert info["last_ok_at"] is None
        assert info["last_error_at"] is None


# ---------------------------------------------------------------------------
# P8.12-C: ProviderField enum members
# ---------------------------------------------------------------------------

_EXPECTED_PROVIDER_FIELDS = {
    ProviderField.TITLE,
    ProviderField.ABSTRACT,
    ProviderField.AUTHORS,
    ProviderField.DOI,
    ProviderField.YEAR,
    ProviderField.VENUE,
    ProviderField.CITATION_COUNT,
    ProviderField.OA_URL,
    ProviderField.REFERENCES,
    ProviderField.RELATED,
}


def test_provider_field_enum_has_all_expected_members() -> None:
    assert set(ProviderField) == _EXPECTED_PROVIDER_FIELDS


def test_field_support_enum_has_full_shallow_none() -> None:
    members = set(FieldSupport)
    assert FieldSupport.FULL in members
    assert FieldSupport.SHALLOW in members
    assert FieldSupport.NONE in members


def test_provider_status_enum_has_expected_members() -> None:
    members = set(ProviderStatus)
    assert ProviderStatus.AVAILABLE in members
    assert ProviderStatus.SHALLOW in members
    assert ProviderStatus.DISABLED in members
    assert ProviderStatus.MISSING_KEY in members
    assert ProviderStatus.FAILED in members
    assert ProviderStatus.RATE_LIMITED in members


# ---------------------------------------------------------------------------
# P8.12-C: Canonical capability constants
# ---------------------------------------------------------------------------


def test_openalex_caps_requires_key_is_false() -> None:
    assert OPENALEX_CAPS.requires_key is False


def test_openalex_caps_supports_title_full() -> None:
    assert OPENALEX_CAPS.supports(ProviderField.TITLE) is FieldSupport.FULL


def test_core_caps_requires_key_is_true() -> None:
    assert CORE_PUBLIC_CAPS.requires_key is True


def test_core_caps_key_env_var() -> None:
    assert CORE_PUBLIC_CAPS.key_env_var == "AGT_CORE_API_KEY"


def test_semantic_scholar_key_upgrade_hint_is_non_empty() -> None:
    hint = SEMANTIC_SCHOLAR_CAPS.key_upgrade_hint
    assert hint is not None
    assert len(hint) > 0


def test_all_canonical_caps_have_non_empty_name() -> None:
    for name, caps in ALL_PROVIDER_CAPS.items():
        assert caps.name, f"caps for {name!r} has empty name"


def test_all_canonical_caps_have_non_empty_fields() -> None:
    for name, caps in ALL_PROVIDER_CAPS.items():
        assert caps.fields, f"caps for {name!r} has empty fields dict"


def test_keyed_providers_have_key_env_var() -> None:
    """Every provider with requires_key=True must also declare key_env_var."""
    for name, caps in ALL_PROVIDER_CAPS.items():
        if caps.requires_key:
            assert caps.key_env_var is not None, (
                f"{name}: requires_key=True but key_env_var is None"
            )


def test_pubmed_and_base_caps_exist() -> None:
    assert PUBMED_CAPS.name == "pubmed"
    assert BASE_CAPS.name == "base"


def test_dimensions_caps_requires_key() -> None:
    assert DIMENSIONS_CAPS.requires_key is True
    assert DIMENSIONS_CAPS.key_env_var is not None
