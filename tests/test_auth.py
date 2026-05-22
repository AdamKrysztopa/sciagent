from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from agt.api.auth import authenticate, require_admin
from agt.secrets import UserEntry, UserRegistry

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403


def _make_registry(users: dict[str, UserEntry]) -> UserRegistry:
    class _FakeRegistry(UserRegistry):
        def __init__(self) -> None:
            pass  # skip Settings init

        def get_all(self) -> dict[str, UserEntry]:
            return users

    return _FakeRegistry()


def _test_app(registry: UserRegistry) -> FastAPI:
    app = FastAPI()

    def _get_registry() -> UserRegistry:
        return registry

    async def _protected(slug: str = Depends(authenticate(_get_registry))) -> dict[str, str]:
        return {"slug": slug}

    async def _admin(
        slug: str = Depends(authenticate(_get_registry)),
        _: None = Depends(require_admin),
    ) -> dict[str, str]:
        return {"slug": slug}

    app.add_api_route("/protected", _protected, methods=["GET"])
    app.add_api_route("/admin-only", _admin, methods=["GET"])
    return app


_ALICE = UserEntry(
    key="agt_alice_aaaabbbbccccddddeeeeffffaaaabbbb",
    email="alice@example.com",
    budget_usd=2.0,
    is_admin=True,
    created_at="2026-01-01T00:00:00Z",
)
_BOB = UserEntry(
    key="agt_bob_11112222333344445555666677778888",
    email="bob@example.com",
    budget_usd=2.0,
    is_admin=False,
    created_at="2026-01-01T00:00:00Z",
)


class TestAuthenticate:
    def test_valid_key_returns_slug(self) -> None:
        registry = _make_registry({"alice": _ALICE})
        app = _test_app(registry)
        with TestClient(app) as client:
            resp = client.get("/protected", headers={"X-AGT-API-Key": _ALICE.key})
        assert resp.status_code == HTTP_OK
        assert resp.json()["slug"] == "alice"

    def test_missing_key_returns_401(self) -> None:
        registry = _make_registry({"alice": _ALICE})
        app = _test_app(registry)
        with TestClient(app) as client:
            resp = client.get("/protected")
        assert resp.status_code == HTTP_UNAUTHORIZED
        assert resp.json()["detail"] == "invalid_api_key"

    def test_wrong_key_returns_401(self) -> None:
        registry = _make_registry({"alice": _ALICE})
        app = _test_app(registry)
        with TestClient(app) as client:
            resp = client.get("/protected", headers={"X-AGT-API-Key": "wrong"})
        assert resp.status_code == HTTP_UNAUTHORIZED

    def test_timing_safe_comparison(self) -> None:
        registry = _make_registry({"alice": _ALICE, "bob": _BOB})
        app = _test_app(registry)
        with TestClient(app) as client:
            resp = client.get("/protected", headers={"X-AGT-API-Key": _BOB.key})
        assert resp.status_code == HTTP_OK
        assert resp.json()["slug"] == "bob"


class TestRequireAdmin:
    def test_admin_user_passes(self) -> None:
        registry = _make_registry({"alice": _ALICE})
        app = _test_app(registry)
        with TestClient(app) as client:
            resp = client.get("/admin-only", headers={"X-AGT-API-Key": _ALICE.key})
        assert resp.status_code == HTTP_OK

    def test_non_admin_returns_403(self) -> None:
        registry = _make_registry({"bob": _BOB})
        app = _test_app(registry)
        with TestClient(app) as client:
            resp = client.get("/admin-only", headers={"X-AGT-API-Key": _BOB.key})
        assert resp.status_code == HTTP_FORBIDDEN
        assert resp.json()["detail"] == "admin_required"
