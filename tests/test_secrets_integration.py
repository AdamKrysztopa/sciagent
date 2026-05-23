"""Integration tests for GCP Secret Manager.

Run with:
    AGT_GCP_PROJECT=sciagent-496617 \\
    uv run pytest tests/test_secrets_integration.py -v
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets as _secrets
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest

from agt.secrets import UserEntry, UserRegistry

pytestmark = pytest.mark.skipif(
    os.environ.get("AGT_GCP_PROJECT") is None,
    reason="AGT_GCP_PROJECT not set — skipping Secret Manager integration tests",
)


@pytest.fixture(scope="module")
def gcp_project() -> str:
    return os.environ["AGT_GCP_PROJECT"]


@pytest.fixture(scope="module")
def test_secret_name() -> str:
    return f"agt-inttest-{_secrets.token_hex(4)}"


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_secret(gcp_project: str, test_secret_name: str) -> Generator[None, Any, Any]:
    yield
    with contextlib.suppress(Exception):
        from google.cloud import secretmanager  # type: ignore[import-untyped]  # noqa: PLC0415

        client = secretmanager.SecretManagerServiceClient()
        client.delete_secret(  # pyright: ignore[reportUnknownMemberType]
            request={"name": f"projects/{gcp_project}/secrets/{test_secret_name}"}
        )


def _seed_secret(gcp_project: str, secret_name: str, data: dict[str, Any]) -> None:
    from google.cloud import secretmanager  # type: ignore[import-untyped]  # noqa: PLC0415

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{gcp_project}"
    with contextlib.suppress(Exception):
        client.create_secret(  # pyright: ignore[reportUnknownMemberType]
            request={
                "parent": parent,
                "secret_id": secret_name,
                "secret": {"replication": {"automatic": {}}},
            }
        )
    client.add_secret_version(  # pyright: ignore[reportUnknownMemberType]
        request={
            "parent": f"{parent}/secrets/{secret_name}",
            "payload": {"data": json.dumps(data).encode("UTF-8")},
        }
    )


def _fake_settings(gcp_project: str, secret_name: str) -> object:
    class _FakeSettings:
        pass

    s = _FakeSettings()
    s.gcp_project = gcp_project  # type: ignore[attr-defined]
    s.gcp_secret_name = secret_name  # type: ignore[attr-defined]
    s.secret_cache_ttl_seconds = 5  # type: ignore[attr-defined]
    s.shared_llm_budget_per_user_usd = 2.0  # type: ignore[attr-defined]
    s.backend_api_key = None  # type: ignore[attr-defined]
    return s


_ALICE_KEY = "agt_alice_aaaabbbbccccddddeeeeffffaaaabbbb"
_BOB_KEY = "agt_bob_11112222333344445555666677778888"
_BOB_BUDGET_USD = 5.0


class TestSecretManagerRead:
    def test_reads_user_entry(self, gcp_project: str, test_secret_name: str) -> None:
        _seed_secret(
            gcp_project,
            test_secret_name,
            {
                "alice": {
                    "key": _ALICE_KEY,
                    "email": "alice@test.com",
                    "budget_usd": 2.0,
                    "is_admin": True,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            },
        )
        settings = _fake_settings(gcp_project, test_secret_name)
        reg = UserRegistry(settings)  # type: ignore[arg-type]
        users = reg.get_all()

        assert "alice" in users
        assert users["alice"].email == "alice@test.com"
        assert users["alice"].is_admin is True
        assert users["alice"].key == _ALICE_KEY

    def test_cache_returns_stale_within_ttl(self, gcp_project: str, test_secret_name: str) -> None:
        settings = _fake_settings(gcp_project, test_secret_name)
        reg = UserRegistry(settings)  # type: ignore[arg-type]
        result1 = reg.get_all()
        result2 = reg.get_all()
        assert result1 == result2


class TestSecretManagerWrite:
    def test_adds_user_and_persists(self, gcp_project: str, test_secret_name: str) -> None:
        settings = _fake_settings(gcp_project, test_secret_name)
        reg = UserRegistry(settings)  # type: ignore[arg-type]
        users = reg.get_all()

        bob = UserEntry(
            key=_BOB_KEY,
            email="bob@test.com",
            budget_usd=_BOB_BUDGET_USD,
            is_admin=False,
            created_at=datetime.now(UTC).isoformat(),
        )
        users["bob"] = bob
        reg.update(users)
        reg.invalidate_cache()

        users2 = reg.get_all()
        assert "bob" in users2
        assert users2["bob"].budget_usd == _BOB_BUDGET_USD

    def test_removes_user_and_persists(self, gcp_project: str, test_secret_name: str) -> None:
        settings = _fake_settings(gcp_project, test_secret_name)
        reg = UserRegistry(settings)  # type: ignore[arg-type]
        users = reg.get_all()
        assert "bob" in users

        del users["bob"]
        reg.update(users)
        reg.invalidate_cache()

        users2 = reg.get_all()
        assert "bob" not in users2
