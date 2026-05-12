"""Tests for watch list API endpoints (SCI-0401/0402)."""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import agt.api.app as api_module
from agt.api.app import create_app
from agt.config import get_settings
from agt.models import NormalizedPaper, SearchMetadata

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204
HTTP_NOT_FOUND = 404


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

    def provider_api_key(self, provider: str) -> _Secret | None:
        return getattr(self, f"{provider}_api_key", None)


def _make_settings() -> _Settings:
    return _Settings()


def _fake_search_state(
    query: str = "test query", papers: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    rid = str(uuid.uuid4())
    return {
        "request_id": rid,
        "thread_id": rid,
        "messages": [f"Processed query: {query}"],
        "papers": papers or [],
        "collection_name": "SciAgent",
        "approved": False,
        "decision": "pending",
        "phase": "awaiting_approval",
        "selected_indices": [],
        "preflight": {"ok": True},
        "trace_spans": [],
        "write_result": None,
        "search_metadata": SearchMetadata(
            original_query=query,
            regex_query=query,
            sources_used=["semantic_scholar"],
            sources_failed=[],
        ).model_dump(),
    }


def _paper_dict(title: str = "Test Paper", doi: str | None = "10.1234/test") -> dict[str, Any]:
    return NormalizedPaper(
        title=title,
        authors=["Smith, J"],
        doi=doi,
        source="semantic_scholar",
    ).model_dump()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = create_app()
    settings = _make_settings()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


_AUTH = {"X-AGT-API-Key": "backend-key"}


# ---------------------------------------------------------------------------
# CRUD: create
# ---------------------------------------------------------------------------


def test_create_watch_returns_201(client: TestClient) -> None:
    resp = client.post(
        "/watches",
        json={"name": "My Watch", "query": "CRISPR gene editing"},
        headers=_AUTH,
    )
    assert resp.status_code == HTTP_CREATED
    data = resp.json()
    assert data["name"] == "My Watch"
    assert data["query"] == "CRISPR gene editing"
    assert data["seen_count"] == 0
    assert "id" in data
    assert data["last_run_at"] is None


def test_create_watch_with_filter_edit(client: TestClient) -> None:
    resp = client.post(
        "/watches",
        json={
            "name": "Recent CRISPR",
            "query": "CRISPR",
            "filter_edit": {
                "original_query": "CRISPR",
                "hard_filters": {
                    "min_year": 2022,
                    "max_year": None,
                    "min_citations": 0,
                    "max_citations": None,
                    "open_access_only": False,
                    "include_keywords": [],
                    "exclude_keywords": [],
                },
                "soft_preferences": {
                    "require_positive_community_perception": False,
                    "min_semantic_score": 0.0,
                },
                "result_limit": 5,
            },
        },
        headers=_AUTH,
    )
    assert resp.status_code == HTTP_CREATED
    data = resp.json()
    assert data["filter_edit"] is not None
    assert data["filter_edit"]["hard_filters"]["min_year"] == 2022  # noqa: PLR2004


def test_create_watch_requires_name(client: TestClient) -> None:
    resp = client.post(
        "/watches",
        json={"name": "", "query": "CRISPR"},
        headers=_AUTH,
    )
    assert resp.status_code == 422  # noqa: PLR2004


# ---------------------------------------------------------------------------
# CRUD: list and get
# ---------------------------------------------------------------------------


def test_list_watches_empty(client: TestClient) -> None:
    resp = client.get("/watches", headers=_AUTH)
    assert resp.status_code == HTTP_OK
    assert resp.json() == []


def test_list_watches_returns_all(client: TestClient) -> None:
    client.post("/watches", json={"name": "W1", "query": "Q1"}, headers=_AUTH)
    client.post("/watches", json={"name": "W2", "query": "Q2"}, headers=_AUTH)
    resp = client.get("/watches", headers=_AUTH)
    assert resp.status_code == HTTP_OK
    names = {w["name"] for w in resp.json()}
    assert "W1" in names
    assert "W2" in names


def test_get_watch_by_id(client: TestClient) -> None:
    created = client.post("/watches", json={"name": "Targeted", "query": "RAG 2024"}, headers=_AUTH)
    watch_id = created.json()["id"]
    resp = client.get(f"/watches/{watch_id}", headers=_AUTH)
    assert resp.status_code == HTTP_OK
    assert resp.json()["name"] == "Targeted"


def test_get_watch_not_found(client: TestClient) -> None:
    resp = client.get(f"/watches/{uuid.uuid4()}", headers=_AUTH)
    assert resp.status_code == HTTP_NOT_FOUND


# ---------------------------------------------------------------------------
# CRUD: delete
# ---------------------------------------------------------------------------


def test_delete_watch(client: TestClient) -> None:
    created = client.post("/watches", json={"name": "Del", "query": "q"}, headers=_AUTH)
    watch_id = created.json()["id"]
    resp = client.delete(f"/watches/{watch_id}", headers=_AUTH)
    assert resp.status_code == HTTP_NO_CONTENT
    assert client.get(f"/watches/{watch_id}", headers=_AUTH).status_code == HTTP_NOT_FOUND


def test_delete_watch_not_found(client: TestClient) -> None:
    resp = client.delete(f"/watches/{uuid.uuid4()}", headers=_AUTH)
    assert resp.status_code == HTTP_NOT_FOUND


# ---------------------------------------------------------------------------
# Rerun: new-paper detection (SCI-0402)
# ---------------------------------------------------------------------------


def test_rerun_watch_tags_new_papers(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    settings = _make_settings()
    app.dependency_overrides[get_settings] = lambda: settings

    paper1 = _paper_dict("Paper A", doi="10.1000/a")
    paper2 = _paper_dict("Paper B", doi="10.1000/b")

    async def fake_run_search_phase(**kwargs: Any) -> dict[str, Any]:
        return _fake_search_state(papers=[paper1, paper2])

    monkeypatch.setattr(api_module, "run_search_phase", fake_run_search_phase)

    with TestClient(app) as client:
        created = client.post("/watches", json={"name": "W", "query": "q"}, headers=_AUTH)
        watch_id = created.json()["id"]

        resp = client.post(f"/watches/{watch_id}/rerun", headers=_AUTH)
        assert resp.status_code == HTTP_OK
        data = resp.json()
        assert data["watch_id"] == watch_id
        assert data["new_count"] == 2  # noqa: PLR2004
        assert data["total_count"] == 2  # noqa: PLR2004
        assert "run_id" in data
        assert data["status"] == "awaiting_approval"


def test_rerun_watch_marks_seen_papers_on_second_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second rerun of the same watch should mark previously seen papers as 'seen'."""
    app = create_app()
    settings = _make_settings()
    app.dependency_overrides[get_settings] = lambda: settings

    paper_a = _paper_dict("Paper A", doi="10.1000/a")

    async def fake_run_search_phase(**kwargs: Any) -> dict[str, Any]:
        return _fake_search_state(papers=[paper_a])

    monkeypatch.setattr(api_module, "run_search_phase", fake_run_search_phase)

    with TestClient(app) as client:
        created = client.post("/watches", json={"name": "W2", "query": "q"}, headers=_AUTH)
        watch_id = created.json()["id"]

        # First rerun — paper is new
        r1 = client.post(f"/watches/{watch_id}/rerun", headers=_AUTH)
        assert r1.json()["new_count"] == 1

        # Second rerun — same paper is seen
        r2 = client.post(f"/watches/{watch_id}/rerun", headers=_AUTH)
        assert r2.json()["new_count"] == 0
        assert r2.json()["total_count"] == 1


def test_rerun_updates_last_run_at(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    settings = _make_settings()
    app.dependency_overrides[get_settings] = lambda: settings

    async def fake_run_search_phase(**kwargs: Any) -> dict[str, Any]:
        return _fake_search_state(papers=[])

    monkeypatch.setattr(api_module, "run_search_phase", fake_run_search_phase)

    with TestClient(app) as client:
        created = client.post("/watches", json={"name": "W3", "query": "q"}, headers=_AUTH)
        watch_id = created.json()["id"]
        assert created.json()["last_run_at"] is None

        client.post(f"/watches/{watch_id}/rerun", headers=_AUTH)

        detail = client.get(f"/watches/{watch_id}", headers=_AUTH)
        assert detail.json()["last_run_at"] is not None


def test_rerun_watch_not_found(client: TestClient) -> None:
    resp = client.post(f"/watches/{uuid.uuid4()}/rerun", headers=_AUTH)
    assert resp.status_code == HTTP_NOT_FOUND


def test_rerun_updates_seen_count(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    settings = _make_settings()
    app.dependency_overrides[get_settings] = lambda: settings

    async def fake_run_search_phase(**kwargs: Any) -> dict[str, Any]:
        return _fake_search_state(
            papers=[_paper_dict("P1", "10.1/p1"), _paper_dict("P2", "10.1/p2")]
        )

    monkeypatch.setattr(api_module, "run_search_phase", fake_run_search_phase)

    with TestClient(app) as client:
        created = client.post("/watches", json={"name": "W4", "query": "q"}, headers=_AUTH)
        watch_id = created.json()["id"]
        assert created.json()["seen_count"] == 0

        client.post(f"/watches/{watch_id}/rerun", headers=_AUTH)

        detail = client.get(f"/watches/{watch_id}", headers=_AUTH)
        assert detail.json()["seen_count"] > 0
