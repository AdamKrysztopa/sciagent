from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from slowapi import Limiter

import agt.api.app as api_module
from agt.api.app import create_app
from agt.config import get_settings
from agt.models import DoctorReport, GapSuggestion, NormalizedPaper

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_UNPROCESSABLE_ENTITY = 422
FILTER_EDIT_RESULT_LIMIT = 5
FILTER_EDIT_MIN_YEAR = 2024


@dataclass(slots=True)
class _Secret:
    value: str

    def get_secret_value(self) -> str:
        return self.value


@dataclass(slots=True)
class _Runtime:
    provider: str = "xai"


@dataclass(slots=True)
class _Settings:
    backend_api_key: _Secret | None = field(default_factory=lambda: _Secret("backend-key"))
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

    def provider_api_key(self, provider: str) -> _Secret | None:
        return getattr(self, f"{provider}_api_key", None)


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
        payload = authorized.json()
        assert payload["ok"] is True
        assert "api_contract_version" in payload
        assert isinstance(payload["api_contract_version"], str)
        assert len(payload["api_contract_version"]) > 0

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

    async def fake_resume(  # noqa: PLR0913
        checkpoint: dict[str, object],
        *,
        approved: bool,
        collection_name: str | None = None,
        selected_indices: list[int] | None = None,
        settings: object | None = None,
        enable_pdf_imports: bool = False,
    ) -> dict[str, object]:
        _ = collection_name
        _ = selected_indices
        _ = settings
        _ = enable_pdf_imports
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

    async def fake_resume(  # noqa: PLR0913
        checkpoint: dict[str, object],
        *,
        approved: bool,
        collection_name: str | None = None,
        selected_indices: list[int] | None = None,
        settings: object | None = None,
        enable_pdf_imports: bool = False,
    ) -> dict[str, object]:
        _ = approved
        _ = collection_name
        _ = selected_indices
        _ = settings
        _ = enable_pdf_imports
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


def test_run_accepts_filter_edit_and_forwards_it(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    captured: dict[str, object] = {}

    async def fake_search_phase(
        query: str,
        collection_name: str,
        thread_id: str | None = None,
        settings: object | None = None,
        filter_edit: object | None = None,
    ) -> dict[str, object]:
        _ = settings
        captured["query"] = query
        captured["collection_name"] = collection_name
        captured["thread_id"] = thread_id
        captured["filter_edit"] = filter_edit
        return {
            "request_id": "req-2",
            "thread_id": thread_id or "thread-2",
            "messages": ["search complete"],
            "papers": [],
            "collection_name": collection_name,
            "approved": False,
            "decision": "pending",
            "phase": "awaiting_approval",
            "selected_indices": [],
            "preflight": {"ok": True},
            "trace_spans": [],
            "write_result": None,
            "search_metadata": {"mode": "regex"},
        }

    monkeypatch.setattr(api_module, "run_search_phase", fake_search_phase)
    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        response = client.post(
            "/run",
            headers={"X-AGT-API-Key": "backend-key", "X-AGT-Client-ID": "owner-a"},
            json={
                "query": "graph neural networks",
                "collection_name": "Inbox",
                "thread_id": "thread-filter-edit",
                "filter_edit": {
                    "original_query": "graph neural networks",
                    "hard_filters": {
                        "min_year": FILTER_EDIT_MIN_YEAR,
                        "include_keywords": ["graph", "neural"],
                    },
                    "soft_preferences": {"min_semantic_score": 0.25},
                    "result_limit": FILTER_EDIT_RESULT_LIMIT,
                },
            },
        )

        assert response.status_code == HTTP_OK
        assert captured["query"] == "graph neural networks"
        assert captured["collection_name"] == "Inbox"
        assert captured["thread_id"] == "thread-filter-edit"
        filter_edit = captured["filter_edit"]
        assert filter_edit is not None
        assert getattr(filter_edit, "result_limit") == FILTER_EDIT_RESULT_LIMIT
        assert getattr(filter_edit, "hard_filters").min_year == FILTER_EDIT_MIN_YEAR
        assert getattr(filter_edit, "hard_filters").include_keywords == ["graph", "neural"]

    app.dependency_overrides.clear()


def test_capabilities_returns_source_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.get("/capabilities", headers={"X-AGT-API-Key": "backend-key"})
        assert resp.status_code == HTTP_OK
        payload = resp.json()
        assert payload["api_contract_version"] == "2026-05"
        assert isinstance(payload["source_policy"], list)
        assert len(payload["source_policy"]) > 0
        source_names = [s["name"] for s in payload["source_policy"]]
        assert "semantic_scholar" in source_names
        assert "openalex" in source_names
        assert "arxiv" in source_names
        assert "filter_support" in payload
        assert "year_filter" in payload["filter_support"]
        assert "pdf_import_supported" in payload

    app.dependency_overrides.clear()


def test_capabilities_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.get("/capabilities")
        assert resp.status_code == HTTP_UNAUTHORIZED

    app.dependency_overrides.clear()


def test_resume_native_write_returns_approved_papers(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    sample_paper: dict[str, object] = {
        "title": "Test Paper",
        "year": 2024,
        "doi": None,
        "arxiv_id": None,
        "abstract": None,
        "authors": [],
        "url": None,
        "pdf_url": None,
        "source": "semantic_scholar",
        "index": 0,
        "semantic_score": 0.9,
        "citation_count": 5,
        "influential_citation_count": 0,
        "open_access": False,
        "summary": None,
        "score": 0.9,
    }

    async def fake_search_phase(
        query: str,
        collection_name: str,
        thread_id: str | None = None,
        settings: object | None = None,
        filter_edit: object | None = None,
    ) -> dict[str, object]:
        _ = query, collection_name, settings, filter_edit
        return {
            "request_id": "req-nw",
            "thread_id": thread_id or "thread-nw",
            "messages": ["search complete"],
            "papers": [sample_paper],
            "collection_name": "Inbox",
            "approved": False,
            "decision": "pending",
            "phase": "awaiting_approval",
            "selected_indices": [0],
            "preflight": {"ok": True},
            "trace_spans": [],
            "write_result": None,
            "search_metadata": {"mode": "regex"},
        }

    monkeypatch.setattr(api_module, "run_search_phase", fake_search_phase)
    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        headers = {
            "X-AGT-API-Key": "backend-key",
            "X-AGT-Client-ID": "owner-nw",
        }
        run_resp = client.post(
            "/run",
            headers=headers,
            json={"query": "q", "collection_name": "Inbox", "thread_id": "thread-nw"},
        )
        assert run_resp.status_code == HTTP_OK
        run_id = run_resp.json()["run_id"]

        resume_resp = client.post(
            "/resume",
            headers=headers,
            json={
                "run_id": run_id,
                "approved": True,
                "native_write": True,
                "selected_indices": [0],
            },
        )
        assert resume_resp.status_code == HTTP_OK
        body = resume_resp.json()
        assert body["status"] == "completed"
        assert body["approved_papers"] is not None
        assert len(body["approved_papers"]) == 1
        assert body["approved_papers"][0]["title"] == "Test Paper"

    app.dependency_overrides.clear()


def test_run_rejects_filter_edit_query_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        response = client.post(
            "/run",
            headers={"X-AGT-API-Key": "backend-key", "X-AGT-Client-ID": "owner-a"},
            json={
                "query": "graph neural networks",
                "collection_name": "Inbox",
                "filter_edit": {
                    "original_query": "different query",
                    "hard_filters": {"min_year": 2024},
                },
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    app.dependency_overrides.clear()


def test_resume_accepts_enable_pdf_imports_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """ResumeRequest accepts enable_pdf_imports and passes it to resume_workflow."""
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    captured: dict[str, object] = {}

    async def fake_search_phase(
        query: str,
        collection_name: str,
        thread_id: str | None = None,
        settings: object | None = None,
        filter_edit: object | None = None,
    ) -> dict[str, object]:
        _ = query, collection_name, settings, filter_edit
        return {
            "request_id": "req-pdf",
            "thread_id": thread_id or "thread-pdf",
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

    async def fake_resume(  # noqa: PLR0913
        checkpoint: dict[str, object],
        *,
        approved: bool,
        collection_name: str | None = None,
        selected_indices: list[int] | None = None,
        settings: object | None = None,
        enable_pdf_imports: bool = False,
    ) -> dict[str, object]:
        captured["enable_pdf_imports"] = enable_pdf_imports
        return {
            **checkpoint,
            "phase": "completed",
            "decision": "approved",
            "approved": True,
            "write_result": {"created": 0, "unchanged": 0, "failed": 0},
        }

    monkeypatch.setattr(api_module, "run_search_phase", fake_search_phase)
    monkeypatch.setattr(api_module, "resume_workflow", fake_resume)
    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        headers = {"X-AGT-API-Key": "backend-key", "X-AGT-Client-ID": "owner-pdf"}

        run_resp = client.post(
            "/run",
            headers=headers,
            json={"query": "q", "collection_name": "Inbox", "thread_id": "thread-pdf"},
        )
        assert run_resp.status_code == HTTP_OK
        run_id = run_resp.json()["run_id"]

        resume_resp = client.post(
            "/resume",
            headers=headers,
            json={"run_id": run_id, "approved": True, "enable_pdf_imports": True},
        )
        assert resume_resp.status_code == HTTP_OK
        assert captured.get("enable_pdf_imports") is True

    app.dependency_overrides.clear()


_DOCTOR_TOTAL_ITEMS = 3


def test_library_doctor_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /library-doctor returns a DoctorReport for the given collection."""
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    async def fake_scan(collection_name: str, settings: object, **kwargs: object) -> DoctorReport:
        return DoctorReport(
            collection_name=collection_name,
            total_items=_DOCTOR_TOTAL_ITEMS,
            issues=[],
            duplicate_pairs=[],
        )

    monkeypatch.setattr(api_module, "scan_collection", fake_scan)
    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.post(
            "/library-doctor",
            headers={"X-AGT-API-Key": "backend-key"},
            json={"collection_name": "My Papers"},
        )
        assert resp.status_code == HTTP_OK
        payload = resp.json()
        assert payload["collection_name"] == "My Papers"
        assert payload["total_items"] == _DOCTOR_TOTAL_ITEMS
        assert payload["issues"] == []
        assert payload["duplicate_pairs"] == []

    app.dependency_overrides.clear()


def test_library_doctor_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /library-doctor rejects requests without a valid API key."""
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.post(
            "/library-doctor",
            json={"collection_name": "My Papers"},
        )
        assert resp.status_code == HTTP_UNAUTHORIZED

    app.dependency_overrides.clear()


def test_gap_finder_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /gap-finder returns a GapFinderResponse with reasoning and papers."""
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    def fake_build_provider(settings: object) -> object:
        class _DummyProvider:
            def invoke(self, prompt: str) -> str:
                return ""

            async def ainvoke(self, prompt: str) -> str:
                return ""

            def bind_tools(self, tools: object) -> object:
                return self

        return _DummyProvider()

    async def fake_find_gaps(
        collection_name: str, settings: object, provider: object, **kwargs: object
    ) -> GapSuggestion:
        return GapSuggestion(
            reasoning="Missing systematic reviews.",
            papers=[NormalizedPaper(title="Gap Paper", authors=["Author A"], doi="10.1234/gap")],
        )

    monkeypatch.setattr(api_module, "find_gaps", fake_find_gaps)
    monkeypatch.setattr(api_module, "build_provider", fake_build_provider)
    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.post(
            "/gap-finder",
            headers={"X-AGT-API-Key": "backend-key"},
            json={"collection_name": "My Papers"},
        )
        assert resp.status_code == HTTP_OK
        payload = resp.json()
        assert payload["reasoning"] == "Missing systematic reviews."
        assert len(payload["papers"]) == 1
        assert payload["papers"][0]["title"] == "Gap Paper"

    app.dependency_overrides.clear()


def test_gap_finder_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /gap-finder rejects requests without a valid API key."""
    app = create_app()

    def fake_get_settings() -> _Settings:
        return _Settings()

    app.dependency_overrides[get_settings] = fake_get_settings

    with TestClient(app) as client:
        resp = client.post(
            "/gap-finder",
            json={"collection_name": "My Papers"},
        )
        assert resp.status_code == HTTP_UNAUTHORIZED

    app.dependency_overrides.clear()


def test_cors_headers_present(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_settings() -> _Settings:
        return _Settings()

    monkeypatch.setattr(api_module, "get_settings", _fake_get_settings)
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    # Use OPTIONS preflight — handled entirely by CORSMiddleware before any endpoint runs.
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") in ("*", "http://localhost:3000")


def test_rate_limiter_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_settings() -> _Settings:
        return _Settings()

    monkeypatch.setattr(api_module, "get_settings", _fake_get_settings)
    app = create_app()
    # SlowAPIMiddleware with default_limits does not inject per-response headers;
    # verify the limiter is wired onto app.state instead.
    assert isinstance(app.state.limiter, Limiter)


def test_get_version(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_settings() -> _Settings:
        return _Settings()

    monkeypatch.setattr(api_module, "get_settings", _fake_get_settings)
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/version")

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert "version" in payload
    assert isinstance(payload["version"], str)
