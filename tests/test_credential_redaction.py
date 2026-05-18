"""MU7 — credential-leak safety tests.

Three layers of defence are verified:
1. ``redact_value`` catches zotero_api_key in dicts and SecretStr values.
2. No structlog event emitted during a /run request contains the raw API key.
3. The /status checkpoint JSON returned by the API contains no credential bytes.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest
import structlog.testing
from fastapi.testclient import TestClient
from pydantic import SecretStr

import agt.api.app as api_module
from agt.api.app import create_app
from agt.config import get_settings, redact_value
from agt.credential_context import RequestCredentials

_SENTINEL_KEY = "zotero-secret-sentinel-12345"
_SENTINEL_LIB_ID = "9876543"
HTTP_OK = 200

_ZOTERO_HEADERS = {
    "X-Zotero-API-Key": _SENTINEL_KEY,
    "X-Zotero-Library-ID": _SENTINEL_LIB_ID,
}


# ── Unit tests for redact_value ───────────────────────────────────────────────


def test_redact_value_catches_zotero_api_key_dict_key() -> None:
    result = redact_value({"zotero_api_key": _SENTINEL_KEY})
    assert isinstance(result, dict)
    assert result["zotero_api_key"] == "[REDACTED]"


def test_redact_value_catches_nested_key() -> None:
    result = redact_value({"outer": {"api_key": _SENTINEL_KEY, "other": "keep"}})
    assert isinstance(result, dict)
    outer = cast(dict[str, object], result["outer"])
    assert outer["api_key"] == "[REDACTED]"
    assert outer["other"] == "keep"


def test_redact_value_catches_secret_str() -> None:
    result = redact_value(SecretStr(_SENTINEL_KEY))
    assert result == "[REDACTED]"


def test_redact_value_leaves_plain_non_secret_string_intact() -> None:
    result = redact_value("normal string without sensitive data")
    assert result == "normal string without sensitive data"


# ── SecretStr model dump protection ───────────────────────────────────────────


def test_request_credentials_model_dump_does_not_expose_api_key() -> None:
    creds = RequestCredentials(
        zotero_api_key=SecretStr(_SENTINEL_KEY),
        zotero_library_id=_SENTINEL_LIB_ID,
    )
    dumped = json.dumps(creds.model_dump(mode="json"))
    assert _SENTINEL_KEY not in dumped


def test_request_credentials_repr_does_not_expose_api_key() -> None:
    creds = RequestCredentials(
        zotero_api_key=SecretStr(_SENTINEL_KEY),
        zotero_library_id=_SENTINEL_LIB_ID,
    )
    assert _SENTINEL_KEY not in repr(creds)
    assert _SENTINEL_KEY not in str(creds)


# ── Integration fixtures ──────────────────────────────────────────────────────


@dataclass(slots=True)
class _Secret:
    value: str

    def get_secret_value(self) -> str:
        return self.value


@dataclass(slots=True)
class _Runtime:
    provider: str = "xai"
    model_name: str = "gpt-4o-mini"


@dataclass(slots=True)
class _Settings:
    backend_api_key: _Secret | None = None
    llm_provider: str = "xai"
    llm_fallback_provider: str | None = None
    runtime: _Runtime = field(default_factory=_Runtime)
    core_api_key: _Secret | None = None
    dimensions_key: _Secret | None = None
    serpapi_key: _Secret | None = None
    zotero_collection_name: str = "SciAgent"
    openai_api_key: _Secret | None = None
    anthropic_api_key: _Secret | None = None
    xai_api_key: _Secret | None = None
    groq_api_key: _Secret | None = None
    resolved_session_dir: Path = field(
        default_factory=lambda: Path(tempfile.mkdtemp()) / f"sess-{uuid.uuid4().hex}"
    )
    resolved_cache_dir: Path = field(
        default_factory=lambda: Path(tempfile.mkdtemp()) / f"cache-{uuid.uuid4().hex}"
    )
    resolved_watch_dir: Path = field(
        default_factory=lambda: Path(tempfile.mkdtemp()) / f"watches-{uuid.uuid4().hex}"
    )
    cache_ttl_seconds: int = 3600
    cors_allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    api_rate_limit: str = "200/minute"
    resolved_llm_provider: str = "xai"
    llm_base_url: str | None = None

    def provider_api_key(self, provider: str) -> _Secret | None:
        return getattr(self, f"{provider}_api_key", None)


def _make_app(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = create_app()

    async def fake_search_phase(
        query: str,
        collection_name: str,
        thread_id: str | None = None,
        settings: object | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        return {
            "request_id": "req-mu7",
            "thread_id": thread_id or "thread-mu7",
            "messages": ["search done"],
            "papers": [],
            "collection_name": collection_name,
            "approved": False,
            "decision": "pending",
            "phase": "awaiting_approval",
            "selected_indices": [],
            "preflight": {"ok": True, "can_read": True, "can_write": True},
            "write_result": None,
            "search_metadata": None,
            "trace_spans": [],
            "filter_edit": None,
        }

    monkeypatch.setattr(api_module, "run_search_phase", fake_search_phase)

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings
    return TestClient(app)


# ── structlog capture test ────────────────────────────────────────────────────


def test_no_credential_in_structlog_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raw Zotero API key value must never appear in any structlog event dict."""
    client = _make_app(monkeypatch)

    with structlog.testing.capture_logs() as captured:
        resp = client.post(
            "/run",
            headers=_ZOTERO_HEADERS,
            json={"query": "rag", "collection_name": "Inbox"},
        )

    assert resp.status_code == HTTP_OK, resp.text

    for event in captured:
        serialized = json.dumps(event, default=str)
        assert _SENTINEL_KEY not in serialized, (
            f"Zotero API key found in structlog event: {serialized!r}"
        )


# ── Checkpoint state test ─────────────────────────────────────────────────────


def test_no_credential_in_checkpoint_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """LangGraph checkpoint returned by /status must not contain the API key bytes."""
    client = _make_app(monkeypatch)

    run_resp = client.post(
        "/run",
        headers=_ZOTERO_HEADERS,
        json={"query": "rag", "collection_name": "Inbox"},
    )
    assert run_resp.status_code == HTTP_OK, run_resp.text
    run_id = run_resp.json()["run_id"]

    status_resp = client.get(f"/status/{run_id}", headers=_ZOTERO_HEADERS)
    assert status_resp.status_code == HTTP_OK, status_resp.text

    serialized = json.dumps(status_resp.json())
    assert _SENTINEL_KEY not in serialized, "Zotero API key found in /status checkpoint JSON"
