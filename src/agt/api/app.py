"""FastAPI backend exposing health/run/resume/status workflow endpoints."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field, model_validator

from agt.config import Settings, get_settings
from agt.graph.workflow import resume_workflow, run_search_phase
from agt.models import AgentState, FilterEditContract, SourceCapability
from agt.providers.router import build_provider
from agt.result_cache import ResultCache
from agt.session_export import ExportFormat, export_session
from agt.session_store import SessionStore
from agt.tools.keyword_extract import KeywordExtraction, extract_keywords
from agt.tools.search_papers import build_source_policy
from agt.tools.spell_check import correct_query
from agt.zotero.preflight import run_zotero_preflight

# Backend contract version exposed via /health for client compatibility checks.
# Format: YYYY-MM for stable monthly revision windows.
API_CONTRACT_VERSION = "2026-05"


class RunRequest(BaseModel):
    query: str = Field(min_length=1)
    collection_name: str | None = Field(default=None, min_length=1)
    thread_id: str | None = None
    filter_edit: FilterEditContract | None = None

    @model_validator(mode="after")
    def validate_filter_edit_query(self) -> RunRequest:
        if self.filter_edit is None:
            return self
        if self.filter_edit.original_query.strip() != self.query.strip():
            raise ValueError("filter_edit.original_query must match query")
        return self


class ResumeRequest(BaseModel):
    run_id: str = Field(min_length=1)
    approved: bool
    collection_name: str | None = None
    selected_indices: list[int] | None = None
    # When True the backend skips the pyzotero write and returns approved papers
    # so the add-on can perform ZAP-6/7/8 native Zotero JS writes.
    native_write: bool = False


class RunAcceptedResponse(BaseModel):
    run_id: str
    thread_id: str
    status: Literal["awaiting_approval", "completed", "rejected", "failed"]
    # Populated only when ResumeRequest.native_write=True so the add-on can write natively.
    approved_papers: list[dict[str, Any]] | None = None


class CapabilitiesResponse(BaseModel):
    api_contract_version: str
    source_policy: list[SourceCapability]
    # Maps filter names to the sources that enforce them server-side.
    filter_support: dict[str, list[str]]
    pdf_import_supported: bool
    # Maps provider name to True if an API key is configured.
    provider_availability: dict[str, bool]
    active_provider: str


class StatusResponse(BaseModel):
    run_id: str
    thread_id: str
    status: Literal["awaiting_approval", "completed", "rejected", "failed"]
    state: dict[str, Any] | None
    error: str | None = None


class CorrectQueryResponse(BaseModel):
    original: str
    corrected: str
    changed: bool


class ExtractKeywordsRequest(BaseModel):
    query: str = Field(min_length=1)


class ExtractKeywordsResponse(BaseModel):
    include_keywords: list[str]
    exclude_keywords: list[str]
    collection_name: str | None


@dataclass(slots=True)
class _RunRecord:
    run_id: str
    owner: str
    thread_id: str
    status: Literal["awaiting_approval", "completed", "rejected", "failed"]
    state: Any | None
    error: str | None = None


class _RunStore:
    def __init__(self) -> None:
        self._records: dict[str, _RunRecord] = {}

    def put(self, record: _RunRecord) -> None:
        self._records[record.run_id] = record

    def get(self, run_id: str) -> _RunRecord:
        record = self._records.get(run_id)
        if record is None:
            raise KeyError(run_id)
        return record


def _require_backend_key(
    x_api_key: str | None = Header(default=None, alias="X-AGT-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.backend_api_key is None:
        return
    if x_api_key != settings.backend_api_key.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_api_key",
        )


def _client_id_header(
    x_client_id: str | None = Header(default=None, alias="X-AGT-Client-ID"),
) -> str:
    if x_client_id is None or not x_client_id.strip():
        return "anonymous"
    return x_client_id.strip()


class _AppState:
    """Lazy-initialized per-app singletons."""

    def __init__(self) -> None:
        self._session_store: SessionStore | None = None
        self._result_cache: ResultCache | None = None

    def session_store(self, settings: Settings) -> SessionStore:
        if self._session_store is None:
            self._session_store = SessionStore(settings.resolved_session_dir)
        return self._session_store

    def result_cache(self, settings: Settings) -> ResultCache:
        if self._result_cache is None:
            self._result_cache = ResultCache(
                settings.resolved_cache_dir, settings.cache_ttl_seconds
            )
        return self._result_cache


def create_app() -> FastAPI:  # noqa: PLR0915
    app = FastAPI(title="SciAgent API", version="0.1.0")
    store = _RunStore()
    app_state = _AppState()

    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:  # pyright: ignore[reportUnusedFunction]
        return RedirectResponse(url="/docs")

    @app.get("/health")
    async def _health(  # pyright: ignore[reportUnusedFunction]
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, Any]:
        preflight = run_zotero_preflight(settings)
        return {
            "ok": preflight.ok,
            "message": preflight.message,
            "preflight": preflight.to_dict(),
            "provider": settings.runtime.provider,
            "fallback_provider": settings.llm_fallback_provider,
            "api_contract_version": API_CONTRACT_VERSION,
        }

    @app.post("/run", response_model=RunAcceptedResponse)
    async def _run(  # pyright: ignore[reportUnusedFunction]
        payload: RunRequest,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
        client_id: str = Depends(_client_id_header),
    ) -> RunAcceptedResponse:
        collection_name = payload.collection_name or settings.zotero_collection_name
        cache = app_state.result_cache(settings)
        hard_filters = (
            payload.filter_edit.hard_filters.model_dump() if payload.filter_edit is not None else {}
        )
        result_limit = payload.filter_edit.result_limit if payload.filter_edit is not None else 10
        cached = cache.get(payload.query, hard_filters, result_limit)
        if cached is not None:
            run_id = payload.thread_id or str(uuid.uuid4())
            cached_state = cast(
                AgentState,
                {
                    **cached,
                    "thread_id": run_id,
                    "request_id": run_id,
                    "collection_name": collection_name,
                    "approved": False,
                    "decision": "pending",
                    "phase": "search_complete",
                    "selected_indices": [],
                    "write_result": None,
                },
            )
            store.put(
                _RunRecord(
                    run_id=run_id,
                    owner=client_id,
                    thread_id=run_id,
                    status="awaiting_approval",
                    state=cached_state,
                )
            )
            return RunAcceptedResponse(
                run_id=run_id,
                thread_id=run_id,
                status="awaiting_approval",
            )
        try:
            if payload.filter_edit is None:
                state = await run_search_phase(
                    query=payload.query,
                    collection_name=collection_name,
                    thread_id=payload.thread_id,
                    settings=settings,
                )
            else:
                state = await run_search_phase(
                    query=payload.query,
                    collection_name=collection_name,
                    thread_id=payload.thread_id,
                    settings=settings,
                    filter_edit=payload.filter_edit,
                )
        except RuntimeError as exc:
            run_id = payload.thread_id or "pending-run"
            store.put(
                _RunRecord(
                    run_id=run_id,
                    owner=client_id,
                    thread_id=payload.thread_id or run_id,
                    status="failed",
                    state=None,
                    error=str(exc),
                )
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"run_failed:{exc}",
            ) from exc

        cache.set(
            payload.query,
            hard_filters,
            result_limit,
            {"papers": state.get("papers", []), "search_metadata": state.get("search_metadata")},
        )
        sess = app_state.session_store(settings)
        run_id = state["thread_id"]
        sess.save(run_id, cast(dict[str, Any], state))
        store.put(
            _RunRecord(
                run_id=run_id,
                owner=client_id,
                thread_id=state["thread_id"],
                status="awaiting_approval",
                state=state,
            )
        )
        return RunAcceptedResponse(
            run_id=run_id,
            thread_id=state["thread_id"],
            status="awaiting_approval",
        )

    @app.post("/resume", response_model=RunAcceptedResponse)
    async def _resume(  # pyright: ignore[reportUnusedFunction]
        payload: ResumeRequest,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
        client_id: str = Depends(_client_id_header),
    ) -> RunAcceptedResponse:
        try:
            record = store.get(payload.run_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found"
            ) from exc

        if record.owner != client_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="run_forbidden")

        if record.state is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="run_has_no_checkpoint"
            )

        if payload.native_write and payload.approved:
            # Native write mode: skip pyzotero; return approved papers for add-on to write.
            checkpoint = cast(AgentState, record.state)
            selected = payload.selected_indices
            if selected is None:
                selected = checkpoint["selected_indices"]
            all_papers = checkpoint["papers"]
            approved_papers = [all_papers[i] for i in selected if 0 <= i < len(all_papers)]
            next_status_nw: Literal["awaiting_approval", "completed", "rejected", "failed"] = (
                "completed"
            )
            store.put(
                _RunRecord(
                    run_id=record.run_id,
                    owner=record.owner,
                    thread_id=record.thread_id,
                    status=next_status_nw,
                    state={
                        **checkpoint,
                        "phase": "completed",
                        "decision": "approved",
                        "approved": True,
                        "selected_indices": selected,
                        "write_result": {"native_write": True, "created": len(approved_papers)},
                    },
                )
            )
            return RunAcceptedResponse(
                run_id=record.run_id,
                thread_id=record.thread_id,
                status=next_status_nw,
                approved_papers=approved_papers,
            )

        resumed = await resume_workflow(
            cast(AgentState, record.state),
            approved=payload.approved,
            collection_name=payload.collection_name,
            selected_indices=payload.selected_indices,
            settings=settings,
        )
        next_status: Literal["awaiting_approval", "completed", "rejected", "failed"]
        if resumed["phase"] == "completed":
            next_status = "completed"
        elif resumed["phase"] == "failed":
            next_status = "failed"
        elif resumed["phase"] == "rejected":
            next_status = "rejected"
        else:
            next_status = "awaiting_approval"

        store.put(
            _RunRecord(
                run_id=record.run_id,
                owner=record.owner,
                thread_id=record.thread_id,
                status=next_status,
                state=resumed,
            )
        )
        return RunAcceptedResponse(
            run_id=record.run_id,
            thread_id=record.thread_id,
            status=next_status,
        )

    @app.get("/capabilities", response_model=CapabilitiesResponse)
    async def _capabilities(  # pyright: ignore[reportUnusedFunction]
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> CapabilitiesResponse:
        source_policy = build_source_policy(settings)
        filter_support: dict[str, list[str]] = {
            "year_filter": [s.name for s in source_policy if s.supports_year_filter],
            "open_access_filter": [s.name for s in source_policy if s.supports_open_access_filter],
        }
        provider_availability = {
            p: settings.provider_api_key(p) is not None  # type: ignore[arg-type]
            for p in ("openai", "anthropic", "xai", "groq")
        }
        return CapabilitiesResponse(
            api_contract_version=API_CONTRACT_VERSION,
            source_policy=source_policy,
            filter_support=filter_support,
            pdf_import_supported=True,
            provider_availability=provider_availability,
            active_provider=settings.runtime.provider,
        )

    @app.get("/correct-query", response_model=CorrectQueryResponse)
    async def _correct_query_endpoint(  # pyright: ignore[reportUnusedFunction]
        q: str = Query(default="", description="Query to spell-check"),
        _: None = Depends(_require_backend_key),
    ) -> CorrectQueryResponse:
        corrected = correct_query(q)
        return CorrectQueryResponse(original=q, corrected=corrected, changed=corrected != q)

    @app.post("/extract-keywords", response_model=ExtractKeywordsResponse)
    async def _extract_keywords_endpoint(  # pyright: ignore[reportUnusedFunction]
        body: ExtractKeywordsRequest,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> ExtractKeywordsResponse:
        try:
            provider = build_provider(settings)
            result: KeywordExtraction = await extract_keywords(body.query, provider)
        except Exception:
            result = KeywordExtraction()
        return ExtractKeywordsResponse(
            include_keywords=result.include_keywords,
            exclude_keywords=result.exclude_keywords,
            collection_name=result.collection_name,
        )

    @app.get("/status/{run_id}", response_model=StatusResponse)
    async def _status_endpoint(  # pyright: ignore[reportUnusedFunction]
        run_id: str,
        _: None = Depends(_require_backend_key),
        client_id: str = Depends(_client_id_header),
    ) -> StatusResponse:
        try:
            record = store.get(run_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found"
            ) from exc

        if record.owner != client_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="run_forbidden")

        return StatusResponse(
            run_id=record.run_id,
            thread_id=record.thread_id,
            status=record.status,
            state=record.state,
            error=record.error,
        )

    @app.get("/status/{run_id}/export")
    async def _export_run(  # pyright: ignore[reportUnusedFunction]
        run_id: str,
        fmt: ExportFormat = Query(default="markdown", alias="format"),
        _: None = Depends(_require_backend_key),
        client_id: str = Depends(_client_id_header),
    ) -> PlainTextResponse:
        try:
            record = store.get(run_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found"
            ) from exc
        if record.owner != client_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="run_forbidden")
        if record.state is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="run_has_no_state")
        state_dict = cast(dict[str, Any], record.state)
        content = export_session(state_dict, fmt, run_id=run_id)
        media_map: dict[ExportFormat, str] = {
            "markdown": "text/markdown; charset=utf-8",
            "json": "application/json; charset=utf-8",
            "csv": "text/csv; charset=utf-8",
        }
        return PlainTextResponse(content=content, media_type=media_map[fmt])

    @app.get("/sessions")
    async def _list_sessions(  # pyright: ignore[reportUnusedFunction]
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> list[dict[str, Any]]:
        return app_state.session_store(settings).list_sessions()

    @app.get("/sessions/{session_id}")
    async def _get_session(  # pyright: ignore[reportUnusedFunction]
        session_id: str,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, Any]:
        try:
            return app_state.session_store(settings).load(session_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found"
            ) from exc

    @app.post("/sessions/{session_id}/rerun", response_model=RunAcceptedResponse)
    async def _rerun_session(  # pyright: ignore[reportUnusedFunction]
        session_id: str,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
        client_id: str = Depends(_client_id_header),
    ) -> RunAcceptedResponse:
        try:
            rerun = app_state.session_store(settings).extract_rerun_payload(session_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="session_not_found"
            ) from exc
        query: str = rerun.get("query", "")
        collection_name: str | None = rerun.get("collection_name")
        filter_edit_data: dict[str, Any] | None = rerun.get("filter_edit")
        filter_edit: FilterEditContract | None = (
            FilterEditContract.model_validate(filter_edit_data)
            if filter_edit_data and query
            else None
        )
        try:
            state = await run_search_phase(
                query=query,
                collection_name=collection_name or settings.zotero_collection_name,
                settings=settings,
                filter_edit=filter_edit,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"run_failed:{exc}"
            ) from exc
        run_id = state["thread_id"]
        app_state.session_store(settings).save(run_id, cast(dict[str, Any], state))
        store.put(
            _RunRecord(
                run_id=run_id,
                owner=client_id,
                thread_id=run_id,
                status="awaiting_approval",
                state=state,
            )
        )
        return RunAcceptedResponse(
            run_id=run_id,
            thread_id=run_id,
            status="awaiting_approval",
        )

    @app.get("/cache/stats")
    async def _cache_stats(  # pyright: ignore[reportUnusedFunction]
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, Any]:
        return app_state.result_cache(settings).stats()

    @app.delete("/cache/clear")
    async def _cache_clear(  # pyright: ignore[reportUnusedFunction]
        expired_only: bool = Query(default=False),
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, Any]:
        deleted = app_state.result_cache(settings).clear(expired_only=expired_only)
        return {"deleted": deleted, "expired_only": expired_only}

    return app


app = create_app()
