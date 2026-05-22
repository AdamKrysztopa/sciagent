from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from agt.api.admin import create_admin_router
from agt.api.auth import authenticate
from agt.comms import MessageStore
from agt.guardrails import SharedBudgetTracker
from agt.secrets import UserEntry, UserRegistry


@dataclass(slots=True)
class _FakeSettings:
    email_api_key: object = None
    email_from: str = "noreply@test.example"


HTTP_OK = 200
HTTP_CREATED = 201
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409

_ADMIN_KEY = "agt_admin_aaaabbbbccccddddeeeeffffaaaabbbb"
_USER_KEY = "agt_bob_11112222333344445555666677778888"

_ADMIN_ENTRY = UserEntry(
    key=_ADMIN_KEY,
    email="admin@example.com",
    budget_usd=2.0,
    is_admin=True,
    created_at="2026-01-01T00:00:00Z",
)
_USER_ENTRY = UserEntry(
    key=_USER_KEY,
    email="bob@example.com",
    budget_usd=2.0,
    is_admin=False,
    created_at="2026-01-01T00:00:00Z",
)


class _FakeRegistry(UserRegistry):
    def __init__(self, users: dict[str, UserEntry]) -> None:
        self._users = dict(users)

    def get_all(self) -> dict[str, UserEntry]:
        return dict(self._users)

    def update(self, registry: dict[str, UserEntry]) -> None:
        self._users = dict(registry)


def _make_app() -> tuple[FastAPI, _FakeRegistry]:
    registry = _FakeRegistry({"admin": _ADMIN_ENTRY, "bob": _USER_ENTRY})
    tracker = SharedBudgetTracker(default_budget_usd=2.00)

    def get_reg() -> UserRegistry:
        return registry

    app = FastAPI()
    _auth = authenticate(get_reg)
    admin_router = create_admin_router(
        get_reg,
        tracker,
        MessageStore(),
        default_budget=2.00,
        settings=_FakeSettings(),  # type: ignore[arg-type]
    )
    app.include_router(admin_router, dependencies=[Depends(_auth)])
    return app, registry


class TestListKeys:
    def test_admin_can_list(self) -> None:
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/admin/keys", headers={"X-AGT-API-Key": _ADMIN_KEY})
        assert resp.status_code == HTTP_OK
        users = resp.json()
        slugs = [u["slug"] for u in users]
        assert "admin" in slugs
        assert "bob" in slugs
        for u in users:
            assert u["key_suffix"].startswith("...")

    def test_non_admin_gets_403(self) -> None:
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/admin/keys", headers={"X-AGT-API-Key": _USER_KEY})
        assert resp.status_code == HTTP_FORBIDDEN


class TestCreateKey:
    def test_admin_creates_user(self) -> None:
        app, registry = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/admin/keys",
                json={"slug": "charlie", "email": "charlie@test.com"},
                headers={"X-AGT-API-Key": _ADMIN_KEY},
            )
        assert resp.status_code == HTTP_CREATED
        body = resp.json()
        assert body["slug"] == "charlie"
        assert body["key"].startswith("agt_charlie_")
        assert "charlie" in registry.get_all()

    def test_duplicate_slug_returns_409(self) -> None:
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.post(
                "/admin/keys",
                json={"slug": "bob", "email": "bob2@test.com"},
                headers={"X-AGT-API-Key": _ADMIN_KEY},
            )
        assert resp.status_code == HTTP_CONFLICT


class TestRevokeKey:
    def test_admin_revokes_user(self) -> None:
        app, registry = _make_app()
        with TestClient(app) as client:
            resp = client.delete(
                "/admin/keys/bob",
                headers={"X-AGT-API-Key": _ADMIN_KEY},
            )
        assert resp.status_code == HTTP_OK
        assert "bob" not in registry.get_all()

    def test_revoke_nonexistent_returns_404(self) -> None:
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.delete(
                "/admin/keys/nobody",
                headers={"X-AGT-API-Key": _ADMIN_KEY},
            )
        assert resp.status_code == HTTP_NOT_FOUND


class TestUsage:
    def test_admin_gets_usage(self) -> None:
        app, _ = _make_app()
        with TestClient(app) as client:
            resp = client.get("/admin/usage", headers={"X-AGT-API-Key": _ADMIN_KEY})
        assert resp.status_code == HTTP_OK
