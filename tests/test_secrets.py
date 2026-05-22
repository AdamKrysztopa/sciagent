from __future__ import annotations

import pytest

from agt.secrets import UserEntry, UserRegistry, generate_key


def _make_settings(
    *,
    backend_api_key: object | None = None,
    gcp_project: str | None = None,
    shared_llm_budget_per_user_usd: float = 2.00,
    gcp_secret_name: str = "agt-user-registry",
) -> object:
    class _Secret:
        def __init__(self, v: str) -> None:
            self._v = v

        def get_secret_value(self) -> str:
            return self._v

    class _FakeSettings:
        pass

    s = _FakeSettings()
    s.backend_api_key = (  # pyright: ignore[reportAttributeAccessIssue]
        _Secret(backend_api_key) if isinstance(backend_api_key, str) else backend_api_key
    )
    s.gcp_project = gcp_project  # pyright: ignore[reportAttributeAccessIssue]
    s.gcp_secret_name = gcp_secret_name  # pyright: ignore[reportAttributeAccessIssue]
    s.secret_cache_ttl_seconds = 60  # pyright: ignore[reportAttributeAccessIssue]
    s.shared_llm_budget_per_user_usd = shared_llm_budget_per_user_usd  # pyright: ignore[reportAttributeAccessIssue]
    return s


class TestUserEntry:
    def test_user_entry_fields(self) -> None:
        entry = UserEntry(
            key="agt_alice_abcd1234abcd1234abcd1234abcd1234",
            email="alice@example.com",
            budget_usd=5.0,
            is_admin=True,
            created_at="2026-05-22T10:00:00Z",
        )
        assert entry.key.startswith("agt_alice_")
        assert entry.is_admin is True


class TestSingleKeyFallback:
    def test_no_key_returns_empty_registry(self) -> None:
        settings = _make_settings(backend_api_key=None)
        registry = UserRegistry(settings)  # type: ignore[arg-type]
        assert registry.get_all() == {}

    def test_single_key_returns_default_admin(self) -> None:
        settings = _make_settings(backend_api_key="test-key-123")
        registry = UserRegistry(settings)  # type: ignore[arg-type]
        users = registry.get_all()
        assert "default" in users
        assert users["default"].key == "test-key-123"
        assert users["default"].is_admin is True
        assert users["default"].budget_usd == 2.00  # noqa: PLR2004

    def test_single_key_custom_budget(self) -> None:
        settings = _make_settings(backend_api_key="key", shared_llm_budget_per_user_usd=10.0)
        registry = UserRegistry(settings)  # type: ignore[arg-type]
        assert registry.get_all()["default"].budget_usd == 10.0  # noqa: PLR2004


class TestKeyValidation:
    def test_generate_key_format(self) -> None:
        key = generate_key("alice")
        assert key.startswith("agt_alice_")
        hex_part = key.split("_", 2)[2]
        assert len(hex_part) == 32  # noqa: PLR2004
        int(hex_part, 16)  # must be valid hex

    def test_generate_key_rejects_invalid_slug(self) -> None:
        with pytest.raises(ValueError, match="slug"):
            generate_key("Alice!")  # uppercase + special char

        with pytest.raises(ValueError, match="slug"):
            generate_key("")
