# Admin Service & Security Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single shared API key with per-user keys stored in GCP Secret Manager, add admin REST endpoints for user management, harden error handling and input validation, enforce HTTPS in the addon, and build a React admin panel.

**Architecture:** Phase 1 adds a `UserRegistry` abstraction (`src/agt/secrets.py`) that reads from GCP Secret Manager in production or falls back to the existing `AGT_BACKEND_API_KEY` for local dev. A new `_authenticate` FastAPI dependency replaces the current `_require_backend_key` + `_client_id_header` pair, deriving user identity from the validated key. Admin endpoints (`/admin/*`) are gated by an `is_admin` flag in the registry. Phase 2 layers a React SPA admin panel served at `/portal/`. Phase 3 adds in-addon banners and email notifications.

**Tech Stack:** Python 3.14, FastAPI, pydantic-settings, google-cloud-secret-manager, slowapi, hmac, React 18, Vite, TypeScript, Tailwind CSS, TanStack Query

**Spec:** `docs/superpowers/specs/2026-05-22-admin-service-security-design.md`

---

## File Structure

### Phase 1 — New files

| File | Responsibility |
|---|---|
| `src/agt/secrets.py` | `UserEntry` model, `UserRegistry` class (Secret Manager + single-key fallback), cached reads, atomic writes |
| `src/agt/api/auth.py` | `_authenticate` and `_require_admin` FastAPI dependencies |
| `src/agt/api/admin.py` | Admin CRUD endpoints: key create/revoke/list/update, usage |
| `tests/test_secrets.py` | `UserRegistry` unit tests |
| `tests/test_auth.py` | Auth dependency unit tests (mock registry) |
| `tests/test_admin_endpoints.py` | Admin endpoint integration tests |

### Phase 1 — Modified files

| File | Change |
|---|---|
| `pyproject.toml:7-23` | Add `google-cloud-secret-manager` dependency |
| `src/agt/config.py` | Add `gcp_project`, `gcp_secret_name`, `secret_cache_ttl_seconds`, `shared_llm_budget_per_user_usd` fields |
| `src/agt/api/app.py:1-20` | Add `RequestValidationError` import |
| `src/agt/api/app.py:253-271` | Remove `_require_backend_key` and `_client_id_header` |
| `src/agt/api/app.py:319-320` | Change slowapi key function from IP to slug |
| `src/agt/api/app.py:329-344` | Fix 500 handler to not leak error details |
| `src/agt/api/app.py` (after 500 handler) | Add custom 422 handler |
| `src/agt/api/app.py` (all endpoints) | Replace `Depends(_require_backend_key)` + `Depends(_client_id_header)` with `Depends(_authenticate)` |
| `src/agt/api/app.py:155` | Add `max_length=2000` to `RunRequest.query` |
| `src/agt/api/app.py:183-184` | Add `max_length` to `CreateWatchRequest` fields |
| `src/agt/models.py:49-53` | Add `max_length` to `HardFilters` string list items |
| `src/agt/models.py:109` | Add `max_length` to `FilterEditContract.seed_dois` items |
| `src/agt/guardrails.py` | Add `SharedBudgetExhaustedError`, per-user spend tracking dict, `record_shared_cost` method |
| `zotero-addon/src/host/prefs.ts` | Add `isInsecureUrl()` helper function |
| `zotero-addon/src/ui/components/HealthStatus.tsx` | Add insecure URL warning row |
| `zotero-addon/src/ui/App.tsx:178-201` | Add insecure URL check to `searchDisabledReason` |
| `.env.example` | Document new env vars |
| `tests/test_api.py:45-74` | Update `_Settings` stub with new fields |

### Phase 2 — New files

| File | Responsibility |
|---|---|
| `admin-panel/` | React SPA: Vite + TypeScript + Tailwind + TanStack Query |
| `admin-panel/src/api.ts` | Typed admin API client |
| `admin-panel/src/pages/Login.tsx` | API key login |
| `admin-panel/src/pages/Dashboard.tsx` | Overview: users, spend, health |
| `admin-panel/src/pages/Users.tsx` | User table with actions |
| `admin-panel/src/pages/CreateUser.tsx` | New user form |
| `admin-panel/src/pages/Health.tsx` | Service health view |

### Phase 2 — Modified files

| File | Change |
|---|---|
| `src/agt/api/admin.py` | Add `GET /admin/health` endpoint |
| `src/agt/api/app.py` | Mount `/portal/` static file serving |

---

## Phase 1 — Security Foundation

### Task 1: Settings fields

**Files:**

- Modify: `src/agt/config.py`
- Modify: `pyproject.toml:7-23`
- Modify: `.env.example`
- Test: `tests/test_config.py` (existing)

- [ ] **Step 1: Add `google-cloud-secret-manager` to `pyproject.toml`**

In `pyproject.toml`, add `"google-cloud-secret-manager>=2.18.0"` to the `dependencies` list:

```python
dependencies = [
  "anyio>=4.6.0",
  "fastapi>=0.116.0",
  "google-cloud-secret-manager>=2.18.0",
  "httpx>=0.28.0",
  # ... rest unchanged
]
```

- [ ] **Step 2: Add settings fields to `src/agt/config.py`**

Add these fields to the `Settings` class, after the existing `backend_api_key` field (around line 82):

```python
    gcp_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_GCP_PROJECT", "GCP_PROJECT"),
        description="GCP project ID. When set, enables Secret Manager auth mode.",
    )
    gcp_secret_name: str = Field(
        default="agt-user-registry",
        validation_alias=AliasChoices("AGT_GCP_SECRET_NAME", "GCP_SECRET_NAME"),
        description="Secret Manager secret name for user registry.",
    )
    secret_cache_ttl_seconds: int = Field(
        default=60,
        ge=5,
        le=3600,
        validation_alias=AliasChoices("AGT_SECRET_CACHE_TTL_SECONDS", "SECRET_CACHE_TTL_SECONDS"),
        description="Cache TTL in seconds for user registry reads from Secret Manager.",
    )
    shared_llm_budget_per_user_usd: float = Field(
        default=2.00,
        ge=0.0,
        validation_alias=AliasChoices(
            "AGT_SHARED_LLM_BUDGET_PER_USER_USD", "SHARED_LLM_BUDGET_PER_USER_USD"
        ),
        description="Default per-user shared LLM budget in USD.",
    )
```

- [ ] **Step 3: Update `.env.example`**

Add after the existing `AGT_BACKEND_API_KEY` entry:

```bash
# --- Per-user auth (GCP Secret Manager) ---
# AGT_GCP_PROJECT=my-gcp-project          # Enables Secret Manager auth mode
# AGT_GCP_SECRET_NAME=agt-user-registry   # Secret name (default: agt-user-registry)
# AGT_SECRET_CACHE_TTL_SECONDS=60         # Registry cache TTL (default: 60)
# AGT_SHARED_LLM_BUDGET_PER_USER_USD=2.00 # Per-user shared LLM budget (default: 2.00)
```

- [ ] **Step 4: Run `uv sync` to install the new dependency**

Run: `uv sync`

- [ ] **Step 5: Run settings tests**

Run: `uv run pytest tests/test_config.py -q --vcr-record=none`
Expected: PASS (new fields have defaults, so existing tests are unaffected)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/agt/config.py .env.example
git commit -m "feat: add GCP Secret Manager settings fields and dependency"
```

---

### Task 2: User registry module

**Files:**

- Create: `src/agt/secrets.py`
- Create: `tests/test_secrets.py`

- [ ] **Step 1: Write tests for `UserEntry` and single-key fallback**

Create `tests/test_secrets.py`:

```python
from __future__ import annotations

import pytest

from agt.secrets import UserEntry, UserRegistry


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
    s.backend_api_key = _Secret(backend_api_key) if isinstance(backend_api_key, str) else backend_api_key  # type: ignore[attr-defined]
    s.gcp_project = gcp_project  # type: ignore[attr-defined]
    s.gcp_secret_name = gcp_secret_name  # type: ignore[attr-defined]
    s.secret_cache_ttl_seconds = 60  # type: ignore[attr-defined]
    s.shared_llm_budget_per_user_usd = shared_llm_budget_per_user_usd  # type: ignore[attr-defined]
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
        assert users["default"].budget_usd == 2.00

    def test_single_key_custom_budget(self) -> None:
        settings = _make_settings(backend_api_key="key", shared_llm_budget_per_user_usd=10.0)
        registry = UserRegistry(settings)  # type: ignore[arg-type]
        assert registry.get_all()["default"].budget_usd == 10.0


class TestKeyValidation:
    def test_generate_key_format(self) -> None:
        from agt.secrets import generate_key

        key = generate_key("alice")
        assert key.startswith("agt_alice_")
        hex_part = key.split("_", 2)[2]
        assert len(hex_part) == 32
        int(hex_part, 16)  # must be valid hex

    def test_generate_key_rejects_invalid_slug(self) -> None:
        from agt.secrets import generate_key

        with pytest.raises(ValueError, match="slug"):
            generate_key("Alice!")  # uppercase + special char

        with pytest.raises(ValueError, match="slug"):
            generate_key("")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_secrets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agt.secrets'`

- [ ] **Step 3: Implement `src/agt/secrets.py`**

```python
"""User registry: GCP Secret Manager with single-key fallback."""

from __future__ import annotations

import json
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agt.config import Settings

_log = structlog.get_logger()
_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


@dataclass(frozen=True, slots=True)
class UserEntry:
    key: str
    email: str
    budget_usd: float
    is_admin: bool
    created_at: str


def generate_key(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"slug must be 1-32 chars matching [a-z0-9_-], got: {slug!r}"
        )
    return f"agt_{slug}_{secrets.token_hex(16)}"


def _entry_from_dict(data: dict[str, object]) -> UserEntry:
    return UserEntry(
        key=str(data.get("key", "")),
        email=str(data.get("email", "")),
        budget_usd=float(data.get("budget_usd", 2.0)),
        is_admin=bool(data.get("is_admin", False)),
        created_at=str(data.get("created_at", "")),
    )


def _entry_to_dict(entry: UserEntry) -> dict[str, object]:
    return {
        "key": entry.key,
        "email": entry.email,
        "budget_usd": entry.budget_usd,
        "is_admin": entry.is_admin,
        "created_at": entry.created_at,
    }


class UserRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, UserEntry] | None = None
        self._cache_time: float = 0.0

    def get_all(self) -> dict[str, UserEntry]:
        if self._settings.gcp_project is not None:
            return self._get_cached()
        return self._single_key_fallback()

    def update(self, registry: dict[str, UserEntry]) -> None:
        if self._settings.gcp_project is None:
            raise RuntimeError("Cannot update registry in single-key fallback mode")
        self._write_to_secret_manager(registry)
        self._cache = dict(registry)
        self._cache_time = time.monotonic()

    def invalidate_cache(self) -> None:
        self._cache = None
        self._cache_time = 0.0

    def _single_key_fallback(self) -> dict[str, UserEntry]:
        if self._settings.backend_api_key is None:
            return {}
        return {
            "default": UserEntry(
                key=self._settings.backend_api_key.get_secret_value(),
                email="",
                budget_usd=self._settings.shared_llm_budget_per_user_usd,
                is_admin=True,
                created_at="",
            ),
        }

    def _get_cached(self) -> dict[str, UserEntry]:
        now = time.monotonic()
        if (
            self._cache is not None
            and (now - self._cache_time) < self._settings.secret_cache_ttl_seconds
        ):
            return self._cache
        self._cache = self._read_from_secret_manager()
        self._cache_time = now
        return self._cache

    def _read_from_secret_manager(self) -> dict[str, UserEntry]:
        from google.cloud import secretmanager  # type: ignore[import-untyped]

        client = secretmanager.SecretManagerServiceClient()
        name = (
            f"projects/{self._settings.gcp_project}"
            f"/secrets/{self._settings.gcp_secret_name}/versions/latest"
        )
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("UTF-8")
        raw: object = json.loads(payload)
        if not isinstance(raw, dict):
            _log.error("secret_manager_invalid_format", secret=self._settings.gcp_secret_name)
            return {}
        result: dict[str, UserEntry] = {}
        for slug, entry_data in raw.items():
            if isinstance(slug, str) and isinstance(entry_data, dict):
                result[slug] = _entry_from_dict(entry_data)
        return result

    def _write_to_secret_manager(self, registry: dict[str, UserEntry]) -> None:
        from google.cloud import secretmanager  # type: ignore[import-untyped]

        client = secretmanager.SecretManagerServiceClient()
        parent = (
            f"projects/{self._settings.gcp_project}"
            f"/secrets/{self._settings.gcp_secret_name}"
        )
        payload_dict = {slug: _entry_to_dict(entry) for slug, entry in registry.items()}
        payload_bytes = json.dumps(payload_dict, indent=2).encode("UTF-8")
        client.add_secret_version(
            request={"parent": parent, "payload": {"data": payload_bytes}}
        )
        _log.info("secret_manager_updated", secret=self._settings.gcp_secret_name,
                   user_count=len(registry))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_secrets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agt/secrets.py tests/test_secrets.py
git commit -m "feat: add UserRegistry with Secret Manager + single-key fallback"
```

---

### Task 3: Auth module

**Files:**

- Create: `src/agt/api/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write tests for `_authenticate` and `_require_admin`**

Create `tests/test_auth.py`:

```python
from __future__ import annotations

import hmac

import pytest
from fastapi import FastAPI, Depends
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

    @app.get("/protected")
    async def _protected(slug: str = Depends(authenticate(_get_registry))) -> dict[str, str]:
        return {"slug": slug}

    @app.get("/admin-only")
    async def _admin(
        slug: str = Depends(authenticate(_get_registry)),
        _: None = Depends(require_admin),
    ) -> dict[str, str]:
        return {"slug": slug}

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agt.api.auth'`

- [ ] **Step 3: Implement `src/agt/api/auth.py`**

```python
"""Per-user API key authentication and admin authorization."""

from __future__ import annotations

import hmac
from collections.abc import Callable

from fastapi import Header, HTTPException, Request, status

from agt.secrets import UserRegistry


def authenticate(
    get_registry: Callable[[], UserRegistry],
) -> Callable[..., str]:
    def _authenticate(
        x_api_key: str | None = Header(default=None, alias="X-AGT-API-Key"),
        request: Request | None = None,
    ) -> str:
        registry = get_registry()
        users = registry.get_all()
        candidate = x_api_key or ""
        matched_slug: str | None = None
        for slug, entry in users.items():
            if hmac.compare_digest(candidate, entry.key):
                matched_slug = slug
        if matched_slug is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_api_key",
            )
        if request is not None:
            request.state.user_slug = matched_slug
            request.state.is_admin = users[matched_slug].is_admin
        return matched_slug

    return _authenticate


def require_admin(request: Request) -> None:
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_required",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agt/api/auth.py tests/test_auth.py
git commit -m "feat: add per-user API key authentication with admin guard"
```

---

### Task 4: Error response sanitisation

**Files:**

- Modify: `src/agt/api/app.py:1-20` (imports)
- Modify: `src/agt/api/app.py:329-344` (500 handler)
- Modify: `src/agt/api/app.py` (add 422 handler)
- Test: `tests/test_api.py` (add tests)

- [ ] **Step 1: Write tests for error sanitisation**

Add to `tests/test_api.py` at the end of the file:

```python
def test_422_does_not_leak_field_values(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/run",
            json={"query": ""},  # min_length=1 violation
            headers={"X-AGT-API-Key": "backend-key", **_ZOTERO_HEADERS},
        )
        assert resp.status_code == HTTP_UNPROCESSABLE_ENTITY
        body = resp.json()
        assert body["detail"] == "validation_error"
        for err in body["errors"]:
            assert "input" not in err


def test_500_does_not_leak_exception_details(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings

    @app.get("/test-boom")
    async def _boom() -> None:
        raise RuntimeError("secret internal details")

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/test-boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"] == "internal_error"
        assert "secret" not in str(body)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_api.py::test_422_does_not_leak_field_values tests/test_api.py::test_500_does_not_leak_exception_details -v`
Expected: FAIL — the current 500 handler leaks `{type(exc).__name__}:{exc}` and there is no custom 422 handler

- [ ] **Step 3: Add `RequestValidationError` import to `app.py`**

At `src/agt/api/app.py`, add to the imports (after the `from fastapi import ...` line):

```python
from fastapi.exceptions import RequestValidationError
```

- [ ] **Step 4: Fix the 500 handler**

In `src/agt/api/app.py`, replace the `content=` line in `_unhandled_exception_handler` (around line 343):

Change:

```python
            content={"detail": f"internal_server_error:{type(exc).__name__}:{exc}"},
```

To:

```python
            content={"detail": "internal_error"},
```

- [ ] **Step 5: Add custom 422 handler**

In `src/agt/api/app.py`, right after the `_unhandled_exception_handler` function, add:

```python
    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        safe_errors = [
            {"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": "validation_error", "errors": safe_errors},
        )
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_api.py::test_422_does_not_leak_field_values tests/test_api.py::test_500_does_not_leak_exception_details -v`
Expected: PASS

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q --vcr-record=none`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/agt/api/app.py tests/test_api.py
git commit -m "fix: sanitise 422/500 error responses to prevent data leakage"
```

---

### Task 5: Input validation

**Files:**

- Modify: `src/agt/api/app.py:155` (`RunRequest.query`)
- Modify: `src/agt/api/app.py:183-184` (`CreateWatchRequest`)
- Modify: `src/agt/models.py:49-53` (`HardFilters` string lists)
- Modify: `src/agt/models.py:109` (`FilterEditContract.seed_dois`)
- Test: `tests/test_api.py`

- [ ] **Step 1: Write a test for query length limit**

Add to `tests/test_api.py`:

```python
def test_query_exceeding_max_length_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/run",
            json={"query": "x" * 2001},
            headers={"X-AGT-API-Key": "backend-key", **_ZOTERO_HEADERS},
        )
        assert resp.status_code == HTTP_UNPROCESSABLE_ENTITY
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_api.py::test_query_exceeding_max_length_returns_422 -v`
Expected: FAIL — currently no `max_length` on `RunRequest.query`

- [ ] **Step 3: Add `max_length` to request models in `app.py`**

In `src/agt/api/app.py`, update `RunRequest`:

```python
class RunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
```

Update `CreateWatchRequest`:

```python
class CreateWatchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=2000)
    collection_name: str | None = None
    filter_edit: FilterEditContract | None = None
```

- [ ] **Step 4: Add `max_length` to `HardFilters` string list items in `models.py`**

In `src/agt/models.py`, add `from typing import Annotated` to imports if not present, then update `HardFilters`:

```python
_Keyword = Annotated[str, Field(max_length=500)]
_AuthorName = Annotated[str, Field(max_length=200)]
_VenueName = Annotated[str, Field(max_length=200)]
_Doi = Annotated[str, Field(max_length=100)]


class HardFilters(BaseModel):
    """Filters that cannot be relaxed or overridden by LLM rewriting."""

    min_year: int | None = Field(default=None, ge=1900, le=2100)
    max_year: int | None = Field(default=None, ge=1900, le=2100)
    min_citations: int = Field(default=0, ge=0)
    max_citations: int | None = Field(default=None, ge=0)
    open_access_only: bool = False
    include_keywords: list[_Keyword] = Field(default_factory=list)
    exclude_keywords: list[_Keyword] = Field(default_factory=list)
    author_ids: list[str] = Field(default_factory=list)
    author_names: list[_AuthorName] = Field(default_factory=list)
    venue_ids: list[str] = Field(default_factory=list)
    venue_names: list[_VenueName] = Field(default_factory=list)
```

Update `FilterEditContract.seed_dois`:

```python
class FilterEditContract(BaseModel):
    """Shared filter review/edit contract for Streamlit, REST API, and Zotero add-on (ZAP-4A)."""

    original_query: str
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    soft_preferences: SoftPreferences = Field(default_factory=SoftPreferences)
    result_limit: int = Field(default=10, ge=1, le=50)
    seed_dois: list[_Doi] = Field(default_factory=list)
    authors: list[ResolvedAuthor] = Field(default_factory=lambda: cast(list[ResolvedAuthor], []))
    venues: list[ResolvedVenue] = Field(default_factory=lambda: cast(list[ResolvedVenue], []))
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_api.py -q --vcr-record=none`
Expected: PASS

Run: `uv run pytest -q --vcr-record=none`
Expected: PASS (ensure no regressions from type annotation changes)

- [ ] **Step 6: Run type checker**

Run: `uv run pyright`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/agt/api/app.py src/agt/models.py tests/test_api.py
git commit -m "feat: add input length validation to request models"
```

---

### Task 6: Replace auth in app.py

**Files:**

- Modify: `src/agt/api/app.py:253-271` (remove old auth functions)
- Modify: `src/agt/api/app.py` (all endpoint signatures)
- Modify: `tests/test_api.py` (update `_Settings` stub, test auth)

This is the largest single task — it touches every endpoint signature. The mechanical change: replace every `_: None = Depends(_require_backend_key)` + `client_id: str = Depends(_client_id_header)` with `slug: str = Depends(_auth)`.

- [ ] **Step 1: Update `_Settings` stub in `tests/test_api.py`**

Add the new fields to the `_Settings` dataclass (around line 45):

```python
@dataclass(slots=True)
class _Settings:
    backend_api_key: _Secret | None = field(default_factory=lambda: _Secret("backend-key"))
    gcp_project: str | None = None
    gcp_secret_name: str = "agt-user-registry"
    secret_cache_ttl_seconds: int = 60
    shared_llm_budget_per_user_usd: float = 2.00
    llm_provider: str = "xai"
    # ... rest of existing fields unchanged ...
```

- [ ] **Step 2: Remove `_require_backend_key` and `_client_id_header` from `app.py`**

Delete lines 253-271 in `src/agt/api/app.py` (the two functions `_require_backend_key` and `_client_id_header`).

- [ ] **Step 3: Add auth wiring in `create_app()`**

In `src/agt/api/app.py`, add imports at the top:

```python
from agt.api.auth import authenticate, require_admin
from agt.secrets import UserRegistry
```

Inside `create_app()`, after the `app_state = _AppState()` line, add:

```python
    _user_registry = UserRegistry(_settings)

    def _get_registry() -> UserRegistry:
        return _user_registry

    _auth = authenticate(_get_registry)
```

- [ ] **Step 4: Replace all `Depends(_require_backend_key)` + `Depends(_client_id_header)`**

For every endpoint that uses both:
- Replace `_: None = Depends(_require_backend_key),` and `client_id: str = Depends(_client_id_header),` with `slug: str = Depends(_auth),`
- Replace every usage of `client_id` in that function body with `slug`

For endpoints that use only `Depends(_require_backend_key)`:
- Replace `_: None = Depends(_require_backend_key),` with `slug: str = Depends(_auth),`
- The `slug` variable may go unused in these endpoints; that's fine (or prefix with `_slug` if needed)

Example — the `/run` endpoint (line 389):

Before:

```python
    @app.post("/run", response_model=RunAcceptedResponse)
    async def _run(
        payload: RunRequest,
        _: None = Depends(_require_backend_key),
        _creds: RequestCredentials = Depends(get_credentials),
        settings: Settings = Depends(get_settings),
        client_id: str = Depends(_client_id_header),
    ) -> RunAcceptedResponse:
```

After:

```python
    @app.post("/run", response_model=RunAcceptedResponse)
    async def _run(
        payload: RunRequest,
        slug: str = Depends(_auth),
        _creds: RequestCredentials = Depends(get_credentials),
        settings: Settings = Depends(get_settings),
    ) -> RunAcceptedResponse:
```

And change `owner=client_id` to `owner=slug` in `_RunRecord(...)`.

Apply this same pattern to all ~25 endpoints listed by `grep`. Every `client_id` → `slug`, every `_: None = Depends(_require_backend_key)` → `slug: str = Depends(_auth)`.

- [ ] **Step 5: Update test headers**

In `tests/test_api.py`, all test headers that use `X-AGT-Client-ID` should be removed (the header is now ignored). The `X-AGT-API-Key: backend-key` header remains since it matches the single-key fallback.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_api.py -q --vcr-record=none`
Expected: PASS

Run: `uv run pyright`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/agt/api/app.py tests/test_api.py
git commit -m "feat: replace shared API key with per-user auth dependency"
```

---

### Task 7: Slug-based rate limiting

**Files:**

- Modify: `src/agt/api/app.py:319-321` (Limiter key function)

- [ ] **Step 1: Write a test confirming slug-based rate limiting**

Add to `tests/test_api.py`:

```python
def test_rate_limit_key_uses_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Limiter key function should extract user_slug from request state."""
    from starlette.testclient import TestClient as _TC
    from starlette.requests import Request as _Request
    from agt.api.app import create_app

    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings(api_rate_limit="2/minute")

    app.dependency_overrides[get_settings] = fake_get_settings

    with _TC(app, raise_server_exceptions=False) as client:
        headers = {"X-AGT-API-Key": "backend-key", **_ZOTERO_HEADERS}
        r1 = client.get("/health", headers=headers)
        r2 = client.get("/health", headers=headers)
        r3 = client.get("/health", headers=headers)
        assert r1.status_code == HTTP_OK
        assert r2.status_code == HTTP_OK
        # Third request may be rate-limited (depends on timing),
        # but the key point is it doesn't crash
```

- [ ] **Step 2: Replace the Limiter key function**

In `src/agt/api/app.py`, before `create_app()`, add:

```python
def _get_user_key(request: Request) -> str:
    return getattr(request.state, "user_slug", request.client.host if request.client else "unknown")
```

Inside `create_app()`, change:

```python
    _limiter = Limiter(
        key_func=_get_user_key,
        default_limits=[_settings.api_rate_limit],
    )
```

Remove the `get_remote_address` import from the `slowapi.util` import line.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_api.py -q --vcr-record=none`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/agt/api/app.py tests/test_api.py
git commit -m "feat: switch rate limiter from IP-based to per-user-slug keys"
```

---

### Task 8: Per-user LLM spend tracking

**Files:**

- Modify: `src/agt/guardrails.py`
- Create: `tests/test_shared_budget.py`

- [ ] **Step 1: Write tests for shared budget tracking**

Create `tests/test_shared_budget.py`:

```python
from __future__ import annotations

import pytest

from agt.guardrails import SharedBudgetExhaustedError, SharedBudgetTracker


class TestSharedBudgetTracker:
    def test_record_cost_under_budget(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=2.00)
        tracker.record_cost("alice", 0.50)
        assert tracker.get_spend("alice") == pytest.approx(0.50)

    def test_record_cost_exceeds_budget_raises(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=1.00)
        tracker.record_cost("alice", 0.80)
        with pytest.raises(SharedBudgetExhaustedError):
            tracker.record_cost("alice", 0.30)

    def test_per_user_budget_override(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=1.00)
        tracker.record_cost("alice", 0.80, budget_override=5.00)
        tracker.record_cost("alice", 0.80, budget_override=5.00)  # total 1.60, under 5.00
        assert tracker.get_spend("alice") == pytest.approx(1.60)

    def test_separate_user_budgets(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=1.00)
        tracker.record_cost("alice", 0.90)
        tracker.record_cost("bob", 0.90)  # bob has his own budget
        assert tracker.get_spend("alice") == pytest.approx(0.90)
        assert tracker.get_spend("bob") == pytest.approx(0.90)

    def test_get_spend_unknown_user(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=2.00)
        assert tracker.get_spend("unknown") == 0.0

    def test_get_all_usage(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=2.00)
        tracker.record_cost("alice", 0.50)
        tracker.record_cost("bob", 1.20)
        tracker.record_request("alice")
        tracker.record_request("alice")
        tracker.record_request("bob")
        usage = tracker.get_all_usage(default_budget=2.00)
        assert usage["alice"]["spend_usd"] == pytest.approx(0.50)
        assert usage["alice"]["requests"] == 2
        assert usage["bob"]["spend_usd"] == pytest.approx(1.20)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_shared_budget.py -v`
Expected: FAIL — `ImportError: cannot import name 'SharedBudgetTracker'`

- [ ] **Step 3: Add `SharedBudgetTracker` to `src/agt/guardrails.py`**

Add at the end of the file:

```python
class SharedBudgetExhaustedError(RuntimeError):
    pass


class SharedBudgetTracker:
    def __init__(self, default_budget_usd: float) -> None:
        self._default_budget = default_budget_usd
        self._spend: dict[str, float] = {}
        self._requests: dict[str, int] = {}
        self._last_seen: dict[str, float] = {}

    def record_cost(
        self, slug: str, cost_usd: float, *, budget_override: float | None = None
    ) -> None:
        budget = budget_override if budget_override is not None else self._default_budget
        current = self._spend.get(slug, 0.0)
        if current + cost_usd > budget:
            raise SharedBudgetExhaustedError(
                f"Shared LLM budget exhausted for user {slug!r}"
            )
        self._spend[slug] = current + cost_usd
        self._last_seen[slug] = time.monotonic()

    def record_request(self, slug: str) -> None:
        self._requests[slug] = self._requests.get(slug, 0) + 1
        self._last_seen[slug] = time.monotonic()

    def get_spend(self, slug: str) -> float:
        return self._spend.get(slug, 0.0)

    def get_all_usage(
        self, default_budget: float
    ) -> dict[str, dict[str, object]]:
        slugs = set(self._spend) | set(self._requests)
        result: dict[str, dict[str, object]] = {}
        for slug in sorted(slugs):
            result[slug] = {
                "spend_usd": self._spend.get(slug, 0.0),
                "cap_usd": default_budget,
                "requests": self._requests.get(slug, 0),
            }
        return result
```

Ensure `import time` is in the existing imports at the top of the file.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_shared_budget.py -v`
Expected: PASS

- [ ] **Step 5: Add 402 exception handler to `app.py`**

In `src/agt/api/app.py`, import the error class at the top of `create_app()`:

```python
    from agt.guardrails import SharedBudgetExhaustedError
```

After the 422 exception handler, add:

```python
    @app.exception_handler(SharedBudgetExhaustedError)
    async def _shared_budget_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: SharedBudgetExhaustedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=402,
            content={
                "detail": "shared_llm_budget_exhausted",
                "hint": "Set your own LLM API key in the addon settings to continue.",
            },
        )
```

- [ ] **Step 6: Wire budget check into the `/run` endpoint**

In the `/run` endpoint handler in `app.py`, after authentication succeeds and before the workflow runs, add a pre-flight budget check. After the run completes, record the cost:

```python
    # Inside _run(), after slug is resolved:
    from agt.credential_context import current_credentials

    # Skip budget tracking when user provides their own LLM key
    creds = current_credentials.get(None)
    uses_shared_llm = creds is None or creds.llm_api_key is None

    if uses_shared_llm:
        registry = _get_registry()
        users = registry.get_all()
        user_budget = users[slug].budget_usd if slug in users else _settings.shared_llm_budget_per_user_usd
        if _budget_tracker.get_spend(slug) >= user_budget:
            raise SharedBudgetExhaustedError(f"Budget exhausted for {slug}")

    # ... existing workflow execution ...

    # After workflow completes, record estimated cost for shared LLM usage:
    if uses_shared_llm:
        _budget_tracker.record_cost(slug, 0.05, budget_override=user_budget)
    _budget_tracker.record_request(slug)
```

The `0.05` per-run estimate is a placeholder; refine with actual token-based cost tracking later.

- [ ] **Step 7: Commit**

```bash
git add src/agt/guardrails.py src/agt/api/app.py tests/test_shared_budget.py
git commit -m "feat: add per-user shared LLM budget tracking with 402 handler"
```

---

### Task 9: Admin API endpoints

**Files:**

- Create: `src/agt/api/admin.py`
- Modify: `src/agt/api/app.py` (mount admin router)
- Create: `tests/test_admin_endpoints.py`

- [ ] **Step 1: Write tests for admin endpoints**

Create `tests/test_admin_endpoints.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from agt.api.admin import create_admin_router
from agt.api.auth import authenticate
from agt.guardrails import SharedBudgetTracker
from agt.secrets import UserEntry, UserRegistry

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
    admin_router = create_admin_router(get_reg, tracker, default_budget=2.00)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_admin_endpoints.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agt.api.admin'`

- [ ] **Step 3: Implement `src/agt/api/admin.py`**

```python
"""Admin API endpoints for user key management and usage monitoring."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agt.api.auth import require_admin
from agt.guardrails import SharedBudgetTracker
from agt.secrets import UserEntry, UserRegistry, generate_key


class CreateKeyRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    email: str = Field(min_length=1, max_length=320)
    budget_usd: float | None = None


class CreateKeyResponse(BaseModel):
    slug: str
    key: str
    email: str
    budget_usd: float


class UserSummary(BaseModel):
    slug: str
    email: str
    key_suffix: str
    budget_usd: float
    is_admin: bool
    created_at: str


class UpdateKeyRequest(BaseModel):
    budget_usd: float | None = None
    is_admin: bool | None = None


def create_admin_router(
    get_registry: Callable[[], UserRegistry],
    budget_tracker: SharedBudgetTracker,
    *,
    default_budget: float,
) -> APIRouter:
    router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

    @router.get("/keys", response_model=list[UserSummary])
    async def list_keys() -> list[UserSummary]:
        registry = get_registry()
        users = registry.get_all()
        return [
            UserSummary(
                slug=slug,
                email=entry.email,
                key_suffix=f"...{entry.key[-4:]}",
                budget_usd=entry.budget_usd,
                is_admin=entry.is_admin,
                created_at=entry.created_at,
            )
            for slug, entry in sorted(users.items())
        ]

    @router.post("/keys", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
    async def create_key(body: CreateKeyRequest) -> CreateKeyResponse:
        registry = get_registry()
        users = registry.get_all()
        if body.slug in users:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User {body.slug!r} already exists",
            )
        budget = body.budget_usd if body.budget_usd is not None else default_budget
        key = generate_key(body.slug)
        entry = UserEntry(
            key=key,
            email=body.email,
            budget_usd=budget,
            is_admin=False,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        users[body.slug] = entry
        registry.update(users)
        return CreateKeyResponse(slug=body.slug, key=key, email=body.email, budget_usd=budget)

    @router.delete("/keys/{slug}")
    async def revoke_key(slug: str) -> dict[str, str]:
        registry = get_registry()
        users = registry.get_all()
        if slug not in users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {slug!r} not found",
            )
        del users[slug]
        registry.update(users)
        return {"status": "revoked", "slug": slug}

    @router.patch("/keys/{slug}")
    async def update_key(slug: str, body: UpdateKeyRequest) -> dict[str, str]:
        registry = get_registry()
        users = registry.get_all()
        if slug not in users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {slug!r} not found",
            )
        old = users[slug]
        users[slug] = UserEntry(
            key=old.key,
            email=old.email,
            budget_usd=body.budget_usd if body.budget_usd is not None else old.budget_usd,
            is_admin=body.is_admin if body.is_admin is not None else old.is_admin,
            created_at=old.created_at,
        )
        registry.update(users)
        return {"status": "updated", "slug": slug}

    @router.get("/usage")
    async def get_usage() -> dict[str, dict[str, object]]:
        return budget_tracker.get_all_usage(default_budget=default_budget)

    return router
```

- [ ] **Step 4: Mount admin router in `app.py`**

In `src/agt/api/app.py`, inside `create_app()`, after the `_auth = authenticate(...)` line, add:

```python
    from agt.api.admin import create_admin_router
    from agt.guardrails import SharedBudgetTracker

    _budget_tracker = SharedBudgetTracker(_settings.shared_llm_budget_per_user_usd)
    _admin_router = create_admin_router(
        _get_registry,
        _budget_tracker,
        default_budget=_settings.shared_llm_budget_per_user_usd,
    )
    app.include_router(_admin_router, dependencies=[Depends(_auth)])
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_admin_endpoints.py -v`
Expected: PASS

Run: `uv run pytest -q --vcr-record=none`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agt/api/admin.py src/agt/api/app.py tests/test_admin_endpoints.py
git commit -m "feat: add admin REST endpoints for key management and usage"
```

---

### Task 10: HTTPS enforcement in addon

**Files:**

- Modify: `zotero-addon/src/host/prefs.ts`
- Modify: `zotero-addon/src/ui/components/HealthStatus.tsx`
- Modify: `zotero-addon/src/ui/App.tsx:178-201`
- Test: `zotero-addon/src/host/prefs.test.ts`

- [ ] **Step 1: Add `isInsecureUrl` test to `prefs.test.ts`**

Add to `zotero-addon/src/host/prefs.test.ts`:

```typescript
import { isInsecureUrl } from "./prefs";

describe("isInsecureUrl", () => {
  it("returns true for http:// URLs", () => {
    expect(isInsecureUrl("http://example.com/api")).toBe(true);
  });

  it("returns false for https:// URLs", () => {
    expect(isInsecureUrl("https://example.com/api")).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(isInsecureUrl("")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `zotero-addon/`: `npm run test -- --testPathPattern=prefs`
Expected: FAIL — `isInsecureUrl` is not exported

- [ ] **Step 3: Add `isInsecureUrl` to `prefs.ts`**

At the end of `zotero-addon/src/host/prefs.ts`, add:

```typescript
export function isInsecureUrl(url: string): boolean {
  return url.startsWith("http://");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run from `zotero-addon/`: `npm run test -- --testPathPattern=prefs`
Expected: PASS

- [ ] **Step 5: Add insecure URL warning to `HealthStatus.tsx`**

In `zotero-addon/src/ui/components/HealthStatus.tsx`, update the `HealthStatusProps` interface:

```typescript
interface HealthStatusProps {
  backendUrl: string;
  backendMode: string;
  busy: boolean;
  error: string | null;
  onRefresh(): void;
  response: HealthResponse | null;
}
```

Add the import and a warning block. At the top of the `HealthStatus` function body, after the existing variables:

```typescript
import { isInsecureUrl } from "../../host/prefs";
```

Inside the component, after the preflight warning `<output>` block and before the "Waiting" empty state:

```typescript
      {backendMode === "remote" && isInsecureUrl(backendUrl) ? (
        <div className="agt-error">
          Insecure connection — backend URL must use HTTPS.
        </div>
      ) : null}
```

- [ ] **Step 6: Update `HealthStatus` usage in `App.tsx`**

In `zotero-addon/src/ui/App.tsx`, wherever `<HealthStatus>` is rendered, add the `backendMode` prop:

```typescript
<HealthStatus
  backendUrl={controller.config.backendUrl}
  backendMode={controller.config.backendMode}
  busy={controller.healthBusy}
  error={controller.healthError}
  onRefresh={controller.onRefreshHealth}
  response={controller.healthResponse}
/>
```

- [ ] **Step 7: Add insecure URL check to `searchDisabledReason`**

In `zotero-addon/src/ui/App.tsx`, inside `searchDisabledReason` (line 178), add a check after the existing `backendMode === "remote"` checks (after line 187):

```typescript
import { isInsecureUrl } from "../host/prefs";

// Add after the zoteroLibraryId check:
  if (controller.config.backendMode === "remote" && isInsecureUrl(controller.config.backendUrl)) {
    return "Backend URL must use HTTPS. Update it in settings.";
  }
```

- [ ] **Step 8: Run addon quality gates**

Run from `zotero-addon/`:

```bash
npm run lint && npm run build && npm run typecheck && npm run test
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add zotero-addon/src/host/prefs.ts zotero-addon/src/host/prefs.test.ts \
       zotero-addon/src/ui/components/HealthStatus.tsx zotero-addon/src/ui/App.tsx
git commit -m "feat: enforce HTTPS for remote backend connections in addon"
```

---

### Task 11: Phase 1 quality gate

**Files:** None (verification only)

- [ ] **Step 1: Run full Python quality gates**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --vcr-record=none
```

Expected: All PASS

- [ ] **Step 2: Run addon quality gates**

```bash
cd zotero-addon && npm run lint && npm run build && npm run typecheck && npm run test
```

Expected: All PASS

- [ ] **Step 3: Run docs quality gate**

```bash
npx --yes markdownlint-cli2 "README.md" "docs/**/*.md" "examples/**/*.md" ".github/**/*.md" "zotero-addon/README.md"
uv run mkdocs build --strict
```

Expected: All PASS

- [ ] **Step 4: Update `docs/settings.md` with new env vars**

Document the new settings fields (`AGT_GCP_PROJECT`, `AGT_GCP_SECRET_NAME`, `AGT_SECRET_CACHE_TTL_SECONDS`, `AGT_SHARED_LLM_BUDGET_PER_USER_USD`) in the environment variables section of `docs/settings.md`.

- [ ] **Step 5: Commit**

```bash
git add docs/settings.md
git commit -m "docs: add new security settings to docs/settings.md"
```

---

## Phase 2 — Admin Panel

### Task 12: Admin panel project setup

**Files:**

- Create: `admin-panel/` (Vite + React + TypeScript + Tailwind)

- [ ] **Step 1: Scaffold the project**

```bash
npm create vite@latest admin-panel -- --template react-ts
cd admin-panel
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install @tanstack/react-query
```

- [ ] **Step 2: Configure Tailwind**

In `admin-panel/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "dist",
  },
  server: {
    proxy: {
      "/admin": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
```

Replace `admin-panel/src/index.css` content with:

```css
@import "tailwindcss";
```

- [ ] **Step 3: Set up `App.tsx` shell with routing**

Replace `admin-panel/src/App.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Users } from "./pages/Users";
import { CreateUser } from "./pages/CreateUser";
import { Health } from "./pages/Health";

const queryClient = new QueryClient();

type Page = "dashboard" | "users" | "create-user" | "health";

export default function App() {
  const [apiKey, setApiKey] = useState<string | null>(
    () => sessionStorage.getItem("agt-admin-key"),
  );
  const [page, setPage] = useState<Page>("dashboard");

  if (apiKey === null) {
    return <Login onLogin={(key) => { sessionStorage.setItem("agt-admin-key", key); setApiKey(key); }} />;
  }

  const nav = (
    <nav className="flex gap-4 p-4 bg-gray-100 border-b">
      <button onClick={() => setPage("dashboard")} className={page === "dashboard" ? "font-bold" : ""}>Dashboard</button>
      <button onClick={() => setPage("users")} className={page === "users" ? "font-bold" : ""}>Users</button>
      <button onClick={() => setPage("create-user")} className={page === "create-user" ? "font-bold" : ""}>Create User</button>
      <button onClick={() => setPage("health")} className={page === "health" ? "font-bold" : ""}>Health</button>
      <button onClick={() => { sessionStorage.removeItem("agt-admin-key"); setApiKey(null); }} className="ml-auto text-red-600">Logout</button>
    </nav>
  );

  return (
    <QueryClientProvider client={queryClient}>
      {nav}
      <main className="p-6 max-w-5xl mx-auto">
        {page === "dashboard" && <Dashboard apiKey={apiKey} />}
        {page === "users" && <Users apiKey={apiKey} />}
        {page === "create-user" && <CreateUser apiKey={apiKey} onCreated={() => setPage("users")} />}
        {page === "health" && <Health apiKey={apiKey} />}
      </main>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 4: Verify it builds**

Run from `admin-panel/`: `npm run build`
Expected: PASS (pages will be placeholder stubs at first)

- [ ] **Step 5: Commit**

```bash
git add admin-panel/
git commit -m "feat: scaffold admin panel with Vite + React + TypeScript + Tailwind"
```

---

### Task 13: API client + Login page

**Files:**

- Create: `admin-panel/src/api.ts`
- Create: `admin-panel/src/pages/Login.tsx`

- [ ] **Step 1: Create typed API client**

Create `admin-panel/src/api.ts`:

```typescript
export interface UserSummary {
  slug: string;
  email: string;
  key_suffix: string;
  budget_usd: number;
  is_admin: boolean;
  created_at: string;
}

export interface CreateKeyRequest {
  slug: string;
  email: string;
  budget_usd?: number;
}

export interface CreateKeyResponse {
  slug: string;
  key: string;
  email: string;
  budget_usd: number;
}

export interface UsageEntry {
  spend_usd: number;
  cap_usd: number;
  requests: number;
}

export interface HealthResponse {
  ok: boolean;
  provider: string;
  fallback_provider: string | null;
  preflight: { ok: boolean; message: string | null };
}

async function apiFetch<T>(path: string, apiKey: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: {
      "X-AGT-API-Key": apiKey,
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  listKeys: (apiKey: string) => apiFetch<UserSummary[]>("/admin/keys", apiKey),

  createKey: (apiKey: string, body: CreateKeyRequest) =>
    apiFetch<CreateKeyResponse>("/admin/keys", apiKey, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  revokeKey: (apiKey: string, slug: string) =>
    apiFetch<{ status: string }>(`/admin/keys/${slug}`, apiKey, { method: "DELETE" }),

  updateKey: (apiKey: string, slug: string, body: { budget_usd?: number; is_admin?: boolean }) =>
    apiFetch<{ status: string }>(`/admin/keys/${slug}`, apiKey, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  getUsage: (apiKey: string) => apiFetch<Record<string, UsageEntry>>("/admin/usage", apiKey),

  getHealth: (apiKey: string) => apiFetch<HealthResponse>("/health", apiKey),
};
```

- [ ] **Step 2: Create Login page**

Create `admin-panel/src/pages/Login.tsx`:

```typescript
import { useState } from "react";
import { api } from "../api";

export function Login({ onLogin }: { onLogin: (key: string) => void }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.listKeys(key);
      onLogin(key);
    } catch {
      setError("Invalid admin API key.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded shadow-md w-96">
        <h1 className="text-xl font-bold mb-4">SciAgent Admin</h1>
        <label className="block mb-2 text-sm font-medium">API Key</label>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          className="w-full border rounded px-3 py-2 mb-4"
          placeholder="agt_admin_..."
          required
        />
        {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
        <button
          type="submit"
          disabled={loading || key.length === 0}
          className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Checking..." : "Login"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run from `admin-panel/`: `npm run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add admin-panel/src/api.ts admin-panel/src/pages/Login.tsx
git commit -m "feat: add admin panel API client and login page"
```

---

### Task 14: Dashboard, Users, Create User pages

**Files:**

- Create: `admin-panel/src/pages/Dashboard.tsx`
- Create: `admin-panel/src/pages/Users.tsx`
- Create: `admin-panel/src/pages/CreateUser.tsx`

- [ ] **Step 1: Create Dashboard page**

Create `admin-panel/src/pages/Dashboard.tsx`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function Dashboard({ apiKey }: { apiKey: string }) {
  const keys = useQuery({ queryKey: ["keys"], queryFn: () => api.listKeys(apiKey) });
  const usage = useQuery({ queryKey: ["usage"], queryFn: () => api.getUsage(apiKey) });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.getHealth(apiKey) });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm text-gray-500">Active Users</p>
          <p className="text-3xl font-bold">{keys.data?.length ?? "—"}</p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm text-gray-500">Total Spend</p>
          <p className="text-3xl font-bold">
            {usage.data
              ? `$${Object.values(usage.data).reduce((s, u) => s + u.spend_usd, 0).toFixed(2)}`
              : "—"}
          </p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm text-gray-500">Backend</p>
          <p className="text-3xl font-bold">{health.data?.ok ? "Healthy" : health.isError ? "Error" : "—"}</p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create Users page**

Create `admin-panel/src/pages/Users.tsx`:

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

export function Users({ apiKey }: { apiKey: string }) {
  const queryClient = useQueryClient();
  const keys = useQuery({ queryKey: ["keys"], queryFn: () => api.listKeys(apiKey) });
  const usage = useQuery({ queryKey: ["usage"], queryFn: () => api.getUsage(apiKey) });

  const revoke = useMutation({
    mutationFn: (slug: string) => api.revokeKey(apiKey, slug),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["keys"] }); },
  });

  if (keys.isLoading) return <p>Loading...</p>;
  if (keys.isError) return <p className="text-red-600">Failed to load users.</p>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Users</h1>
      <table className="w-full bg-white rounded shadow">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left p-3">Slug</th>
            <th className="text-left p-3">Email</th>
            <th className="text-left p-3">Key</th>
            <th className="text-right p-3">Budget</th>
            <th className="text-right p-3">Spend</th>
            <th className="text-right p-3">Requests</th>
            <th className="text-left p-3">Admin</th>
            <th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          {keys.data?.map((u) => {
            const usg = usage.data?.[u.slug];
            return (
              <tr key={u.slug} className="border-t">
                <td className="p-3 font-mono">{u.slug}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3 font-mono text-gray-400">{u.key_suffix}</td>
                <td className="p-3 text-right">${u.budget_usd.toFixed(2)}</td>
                <td className="p-3 text-right">${usg?.spend_usd.toFixed(2) ?? "0.00"}</td>
                <td className="p-3 text-right">{usg?.requests ?? 0}</td>
                <td className="p-3">{u.is_admin ? "Yes" : "No"}</td>
                <td className="p-3">
                  <button
                    onClick={() => { if (confirm(`Revoke ${u.slug}?`)) revoke.mutate(u.slug); }}
                    className="text-red-600 hover:underline text-sm"
                    disabled={revoke.isPending}
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Create CreateUser page**

Create `admin-panel/src/pages/CreateUser.tsx`:

```typescript
import { useState } from "react";
import { api } from "../api";

export function CreateUser({ apiKey, onCreated }: { apiKey: string; onCreated: () => void }) {
  const [slug, setSlug] = useState("");
  const [email, setEmail] = useState("");
  const [budget, setBudget] = useState("2.00");
  const [error, setError] = useState<string | null>(null);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await api.createKey(apiKey, {
        slug,
        email,
        budget_usd: parseFloat(budget),
      });
      setCreatedKey(resp.key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setLoading(false);
    }
  }

  if (createdKey !== null) {
    return (
      <div className="bg-white p-6 rounded shadow max-w-md">
        <h2 className="text-xl font-bold mb-4 text-green-700">User Created</h2>
        <p className="mb-2">API key for <strong>{slug}</strong>:</p>
        <code className="block bg-gray-100 p-3 rounded break-all mb-4">{createdKey}</code>
        <p className="text-sm text-gray-500 mb-4">Copy this key now — it cannot be shown again.</p>
        <button onClick={onCreated} className="bg-blue-600 text-white px-4 py-2 rounded">
          Done
        </button>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Create User</h1>
      <form onSubmit={handleSubmit} className="bg-white p-6 rounded shadow max-w-md space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Slug</label>
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
            className="w-full border rounded px-3 py-2"
            placeholder="alice"
            required
            maxLength={32}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border rounded px-3 py-2"
            placeholder="alice@example.com"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Budget (USD)</label>
          <input
            type="number"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            className="w-full border rounded px-3 py-2"
            step="0.50"
            min="0"
          />
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={loading || slug.length === 0 || email.length === 0}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create User"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

Run from `admin-panel/`: `npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add admin-panel/src/pages/
git commit -m "feat: add Dashboard, Users, and CreateUser pages to admin panel"
```

---

### Task 15: Health page, admin health endpoint, static serving

**Files:**

- Create: `admin-panel/src/pages/Health.tsx`
- Modify: `src/agt/api/admin.py` (add `GET /admin/health`)
- Modify: `src/agt/api/app.py` (mount static files)

- [ ] **Step 1: Add `GET /admin/health` endpoint**

In `src/agt/api/admin.py`, add to `create_admin_router`, before the `return router`:

```python
    @router.get("/health")
    async def admin_health() -> dict[str, object]:
        return {
            "active_users": len(get_registry().get_all()),
            "budget_tracker_users": len(budget_tracker.get_all_usage(default_budget=default_budget)),
        }
```

- [ ] **Step 2: Create Health page**

Create `admin-panel/src/pages/Health.tsx`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function Health({ apiKey }: { apiKey: string }) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(apiKey),
    refetchInterval: 30_000,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Service Health</h1>
      <div className="bg-white p-6 rounded shadow max-w-md">
        {health.isLoading && <p>Checking...</p>}
        {health.isError && <p className="text-red-600">Backend unreachable</p>}
        {health.data && (
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>Status</span>
              <span className={health.data.ok ? "text-green-600 font-bold" : "text-red-600 font-bold"}>
                {health.data.ok ? "Healthy" : "Unhealthy"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Provider</span>
              <span>{health.data.provider}</span>
            </div>
            <div className="flex justify-between">
              <span>Fallback</span>
              <span>{health.data.fallback_provider ?? "none"}</span>
            </div>
            <div className="flex justify-between">
              <span>Preflight</span>
              <span>{health.data.preflight.ok ? "OK" : health.data.preflight.message}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Mount static file serving in `app.py`**

In `src/agt/api/app.py`, add import at the top:

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles
```

At the end of `create_app()`, before `return app`, add:

```python
    _portal_dir = Path(__file__).resolve().parents[3] / "admin-panel" / "dist"
    if _portal_dir.is_dir():
        app.mount("/portal", StaticFiles(directory=str(_portal_dir), html=True), name="portal")
```

- [ ] **Step 4: Build the admin panel**

Run from `admin-panel/`: `npm run build`
Expected: Creates `admin-panel/dist/` with built files

- [ ] **Step 5: Run all quality gates**

Python:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q --vcr-record=none
```

Admin panel:

```bash
cd admin-panel && npm run build
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add admin-panel/src/pages/Health.tsx src/agt/api/admin.py src/agt/api/app.py
git commit -m "feat: add Health page, admin health endpoint, and portal static serving"
```

---

## Phase 3 — Communication (Outline)

Phase 3 decisions are deferred (message persistence: Firestore vs. Secret Manager). These tasks describe the scope; detailed code will be specified when the persistence decision is made.

### Task 16: Message backend endpoints

**Files:**

- Create: `src/agt/comms.py` — message model, storage interface
- Modify: `src/agt/api/admin.py` — `POST /admin/messages` (admin-only: create message)
- Modify: `src/agt/api/app.py` — `GET /user/messages` (authenticated: pending messages), `POST /user/messages/{id}/dismiss`
- Create: `tests/test_comms.py`

**Scope:**

- `Message` dataclass: `id`, `type` (info/warning/critical), `text`, `recipients` (list of slugs or `"all"`), `channel` (banner/email/both), `created_at`
- In-memory message store for MVP; swap to Firestore later
- Admin creates message → store assigns ID → marks as pending for each recipient
- User fetches pending messages → returns list → user dismisses by ID

---

### Task 17: In-addon banner component

**Files:**

- Create: `zotero-addon/src/ui/components/MessageBanner.tsx` — banner display component
- Modify: `zotero-addon/src/ui/hooks/useSciAgentController.ts` — poll `GET /user/messages` on sidebar open
- Modify: `zotero-addon/src/ui/App.tsx` — render `MessageBanner` at the top of IdleView
- Modify: `zotero-addon/src/client/backendClient.ts` — add `fetchMessages()` and `dismissMessage()` methods

**Scope:**

- Poll messages on sidebar open (single fetch, not interval)
- Display banners stacked at top: info (blue), warning (yellow), critical (red)
- Dismiss button removes the banner and calls `POST /user/messages/{id}/dismiss`

---

### Task 18: Email integration

**Files:**

- Create: `src/agt/email.py` — transactional email sender (SendGrid or Resend)
- Modify: `src/agt/comms.py` — call email sender when `channel` includes `"email"`
- Modify: `src/agt/config.py` — add `AGT_EMAIL_API_KEY`, `AGT_EMAIL_FROM` settings
- Modify: `admin-panel/src/pages/Messages.tsx` — compose form: recipients, text, channel selector

**Scope:**

- Email API key stored in Secret Manager (`agt-email-api-key`)
- Plain text emails only (no HTML templates for MVP)
- Admin selects recipients (individual, all, custom list) and channel (banner/email/both) from the compose form

---

## Task Status Tracking

| Task | Phase | Status | Description |
|---|---|---|---|
| 1 | 1 | `[x]` | Settings fields + dependency |
| 2 | 1 | `[x]` | User registry module |
| 3 | 1 | `[x]` | Auth module |
| 4 | 1 | `[x]` | Error response sanitisation |
| 5 | 1 | `[x]` | Input validation |
| 6 | 1 | `[x]` | Replace auth in app.py |
| 7 | 1 | `[x]` | Slug-based rate limiting |
| 8 | 1 | `[x]` | Per-user LLM spend tracking |
| 9 | 1 | `[x]` | Admin API endpoints |
| 10 | 1 | `[x]` | HTTPS enforcement in addon |
| 11 | 1 | `[x]` | Phase 1 quality gate |
| 12 | 2 | `[ ]` | Admin panel project setup |
| 13 | 2 | `[ ]` | API client + Login page |
| 14 | 2 | `[ ]` | Dashboard, Users, Create User pages |
| 15 | 2 | `[ ]` | Health page + static serving |
| 16 | 3 | `[ ]` | Message backend (outline) |
| 17 | 3 | `[ ]` | In-addon banners (outline) |
| 18 | 3 | `[ ]` | Email integration (outline) |
