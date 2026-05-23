"""Live smoke tests against the deployed SciAgent Cloud Run service.

Run with:
    AGT_SMOKE_URL=https://sciagent-xxx-ew.a.run.app \\
    AGT_SMOKE_ADMIN_KEY=agt_admin_... \\
    uv run pytest tests/test_smoke.py -v
"""

from __future__ import annotations

import os
import secrets as _secrets
from collections.abc import Generator
from typing import Any, cast

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AGT_SMOKE_URL") is None,
    reason="AGT_SMOKE_URL not set — skipping live smoke tests",
)

_SMOKE_URL = os.environ.get("AGT_SMOKE_URL", "")
_ADMIN_KEY = os.environ.get("AGT_SMOKE_ADMIN_KEY", "")

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
KEY_SECRET_LENGTH = 32


@pytest.fixture(scope="session")
def client() -> Generator[httpx.Client]:
    with httpx.Client(base_url=_SMOKE_URL, timeout=30) as c:
        yield c


@pytest.fixture()
def ephemeral_user(client: httpx.Client) -> Generator[dict[str, Any]]:
    if not _ADMIN_KEY:
        pytest.skip("AGT_SMOKE_ADMIN_KEY not set")
    slug = f"smoke-{_secrets.token_hex(4)}"
    resp = client.post(
        "/admin/keys",
        json={"slug": slug, "email": f"{slug}@smoke.invalid", "budget_usd": 0.01},
        headers={"X-AGT-API-Key": _ADMIN_KEY},
    )
    assert resp.status_code == HTTP_CREATED
    data: dict[str, Any] = resp.json()
    yield data
    client.delete(f"/admin/keys/{slug}", headers={"X-AGT-API-Key": _ADMIN_KEY})


class TestHealthSmoke:
    def test_https_url(self) -> None:
        assert _SMOKE_URL.startswith("https://"), f"Smoke URL must use HTTPS, got: {_SMOKE_URL!r}"

    def test_health_ok(self, client: httpx.Client) -> None:
        resp = client.get("/health")
        assert resp.status_code == HTTP_OK
        assert resp.json()["ok"] is True


class TestAuthSmoke:
    def test_missing_key_returns_401(self, client: httpx.Client) -> None:
        resp = client.get("/admin/keys")
        assert resp.status_code == HTTP_UNAUTHORIZED
        assert resp.json()["detail"] == "invalid_api_key"

    def test_wrong_key_returns_401(self, client: httpx.Client) -> None:
        resp = client.get("/admin/keys", headers={"X-AGT-API-Key": "wrong-key"})
        assert resp.status_code == HTTP_UNAUTHORIZED

    def test_admin_key_authenticates(self, client: httpx.Client) -> None:
        if not _ADMIN_KEY:
            pytest.skip("AGT_SMOKE_ADMIN_KEY not set")
        resp = client.get("/admin/keys", headers={"X-AGT-API-Key": _ADMIN_KEY})
        assert resp.status_code == HTTP_OK
        users: list[object] = resp.json()
        assert isinstance(users, list)
        assert len(users) > 0


class TestAdminSmoke:
    def test_create_user_key_has_correct_prefix(
        self, client: httpx.Client, ephemeral_user: dict[str, Any]
    ) -> None:
        slug = cast(str, ephemeral_user["slug"])
        key = cast(str, ephemeral_user["key"])
        assert key.startswith(f"agt_{slug}_")
        assert len(key.split("_")[2]) == KEY_SECRET_LENGTH

    def test_user_key_cannot_access_admin_endpoints(
        self, client: httpx.Client, ephemeral_user: dict[str, Any]
    ) -> None:
        user_key = cast(str, ephemeral_user["key"])
        resp = client.get("/admin/keys", headers={"X-AGT-API-Key": user_key})
        assert resp.status_code == HTTP_FORBIDDEN
        assert resp.json()["detail"] == "admin_required"

    def test_usage_endpoint_returns_dict(self, client: httpx.Client) -> None:
        if not _ADMIN_KEY:
            pytest.skip("AGT_SMOKE_ADMIN_KEY not set")
        resp = client.get("/admin/usage", headers={"X-AGT-API-Key": _ADMIN_KEY})
        assert resp.status_code == HTTP_OK
        assert isinstance(resp.json(), dict)

    def test_error_responses_do_not_leak_details(self, client: httpx.Client) -> None:
        resp = client.get("/admin/keys", headers={"X-AGT-API-Key": "leak-test-key"})
        assert resp.status_code == HTTP_UNAUTHORIZED
        body = resp.json()
        assert "leak-test-key" not in str(body)


class TestPortalSmoke:
    def test_portal_serves_html(self, client: httpx.Client) -> None:
        resp = client.get("/portal/")
        assert resp.status_code == HTTP_OK
        assert "text/html" in resp.headers.get("content-type", "")

    def test_portal_assets_use_portal_prefix(self, client: httpx.Client) -> None:
        resp = client.get("/portal/")
        assert resp.status_code == HTTP_OK
        body = resp.text
        assert "/portal/assets/" in body, (
            "Admin panel assets should be served under /portal/assets/ — "
            "check that vite.config.ts has base='/portal/'"
        )
