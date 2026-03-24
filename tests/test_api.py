from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

import agt.api.app as api_module
from agt.api.app import create_app
from agt.config import get_settings

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403


@dataclass(slots=True)
class _Secret:
    value: str

    def get_secret_value(self) -> str:
        return self.value


@dataclass(slots=True)
class _Settings:
    backend_api_key: _Secret | None = field(default_factory=lambda: _Secret("backend-key"))
    llm_provider: str = "xai"
    llm_fallback_provider: str | None = None


def test_health_requires_valid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    class _Preflight:
        ok = True
        message = "ok"

        def to_dict(self) -> dict[str, object]:
            return {"ok": True}

    def fake_preflight(settings: object) -> _Preflight:
        _ = settings
        return _Preflight()

    monkeypatch.setattr(api_module, "run_zotero_preflight", fake_preflight)
    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        unauthorized = client.get("/health")
        assert unauthorized.status_code == HTTP_UNAUTHORIZED

        authorized = client.get("/health", headers={"X-AGT-API-Key": "backend-key"})
        assert authorized.status_code == HTTP_OK
        assert authorized.json()["ok"] is True

    app.dependency_overrides.clear()


def test_run_resume_status_flow_with_owner_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    async def fake_search_phase(
        query: str,
        collection_name: str,
        thread_id: str | None = None,
        settings: object | None = None,
    ) -> dict[str, object]:
        _ = query
        _ = collection_name
        _ = settings
        return {
            "request_id": "req-1",
            "thread_id": thread_id or "thread-1",
            "messages": ["search complete"],
            "papers": [],
            "collection_name": "Inbox",
            "approved": False,
            "decision": "pending",
            "phase": "awaiting_approval",
            "selected_indices": [],
            "preflight": {"ok": True},
            "trace_spans": [],
            "write_result": None,
            "search_metadata": {"mode": "regex"},
        }

    async def fake_resume(
        checkpoint: dict[str, object],
        *,
        approved: bool,
        collection_name: str | None = None,
        selected_indices: list[int] | None = None,
        settings: object | None = None,
    ) -> dict[str, object]:
        _ = collection_name
        _ = selected_indices
        _ = settings
        phase = "completed" if approved else "rejected"
        decision = "approved" if approved else "rejected"
        return {
            **checkpoint,
            "phase": phase,
            "decision": decision,
            "approved": approved,
            "write_result": {"created": 1, "unchanged": 0, "failed": 0} if approved else None,
        }

    monkeypatch.setattr(api_module, "run_search_phase", fake_search_phase)
    monkeypatch.setattr(api_module, "resume_workflow", fake_resume)
    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        headers_owner_a = {
            "X-AGT-API-Key": "backend-key",
            "X-AGT-Client-ID": "owner-a",
        }
        headers_owner_b = {
            "X-AGT-API-Key": "backend-key",
            "X-AGT-Client-ID": "owner-b",
        }

        run_response = client.post(
            "/run",
            headers=headers_owner_a,
            json={"query": "q", "collection_name": "Inbox", "thread_id": "thread-a"},
        )
        assert run_response.status_code == HTTP_OK
        run_id = run_response.json()["run_id"]

        forbidden = client.get(f"/status/{run_id}", headers=headers_owner_b)
        assert forbidden.status_code == HTTP_FORBIDDEN

        resume_response = client.post(
            "/resume",
            headers=headers_owner_a,
            json={"run_id": run_id, "approved": True, "selected_indices": [0]},
        )
        assert resume_response.status_code == HTTP_OK
        assert resume_response.json()["status"] == "completed"

        status_response = client.get(f"/status/{run_id}", headers=headers_owner_a)
        assert status_response.status_code == HTTP_OK
        payload = status_response.json()
        assert payload["status"] == "completed"
        assert payload["state"]["decision"] == "approved"

    app.dependency_overrides.clear()


def test_resume_failed_phase_maps_to_failed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    async def fake_search_phase(
        query: str,
        collection_name: str,
        thread_id: str | None = None,
        settings: object | None = None,
    ) -> dict[str, object]:
        _ = query
        _ = collection_name
        _ = settings
        return {
            "request_id": "req-1",
            "thread_id": thread_id or "thread-1",
            "messages": ["search complete"],
            "papers": [],
            "collection_name": "Inbox",
            "approved": False,
            "decision": "pending",
            "phase": "awaiting_approval",
            "selected_indices": [],
            "preflight": {"ok": True},
            "trace_spans": [],
            "write_result": None,
            "search_metadata": {"mode": "regex"},
        }

    async def fake_resume(
        checkpoint: dict[str, object],
        *,
        approved: bool,
        collection_name: str | None = None,
        selected_indices: list[int] | None = None,
        settings: object | None = None,
    ) -> dict[str, object]:
        _ = approved
        _ = collection_name
        _ = selected_indices
        _ = settings
        return {
            **checkpoint,
            "phase": "failed",
            "decision": "approved",
            "approved": True,
            "write_result": {"created": 0, "unchanged": 0, "failed": 1},
        }

    monkeypatch.setattr(api_module, "run_search_phase", fake_search_phase)
    monkeypatch.setattr(api_module, "resume_workflow", fake_resume)
    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        headers = {
            "X-AGT-API-Key": "backend-key",
            "X-AGT-Client-ID": "owner-a",
        }

        run_response = client.post(
            "/run",
            headers=headers,
            json={"query": "q", "collection_name": "Inbox", "thread_id": "thread-a"},
        )
        assert run_response.status_code == HTTP_OK
        run_id = run_response.json()["run_id"]

        resume_response = client.post(
            "/resume",
            headers=headers,
            json={"run_id": run_id, "approved": True},
        )
        assert resume_response.status_code == HTTP_OK
        assert resume_response.json()["status"] == "failed"

        status_response = client.get(f"/status/{run_id}", headers=headers)
        assert status_response.status_code == HTTP_OK
        payload = status_response.json()
        assert payload["status"] == "failed"
        assert payload["state"]["phase"] == "failed"

    app.dependency_overrides.clear()
