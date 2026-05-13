"""FastAPI backend exposing health/run/resume/status workflow endpoints."""

from __future__ import annotations

import importlib.metadata
import uuid
from dataclasses import dataclass
from typing import Any, Literal, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field, model_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from agt.config import Settings, get_settings
from agt.graph.workflow import resume_workflow, run_search_phase
from agt.models import (
    AgentState,
    DoctorReport,
    FilterEditContract,
    GapSuggestion,
    NormalizedPaper,
    SourceCapability,
)
from agt.providers.router import build_provider
from agt.result_cache import ResultCache
from agt.session_export import ExportFormat, export_session
from agt.session_store import SessionStore
from agt.tools.capabilities import ALL_PROVIDER_CAPS, ProviderHealth
from agt.tools.gap_finder import find_gaps
from agt.tools.key_validator import KNOWN_PROVIDERS, validate_key
from agt.tools.keyword_extract import KeywordExtraction, extract_keywords
from agt.tools.search_papers import build_source_policy
from agt.tools.spell_check import correct_query
from agt.tools.zotero_upsert import normalize_doi, title_author_fingerprint
from agt.watch_store import Watch, WatchStore, create_watch
from agt.zotero.library_doctor import scan_collection
from agt.zotero.preflight import run_zotero_preflight

# Backend contract version exposed via /health for client compatibility checks.
# Format: YYYY-MM for stable monthly revision windows.
API_CONTRACT_VERSION = "2026-05"


class RunRequest(BaseModel):
    query: str = Field(min_length=1)
    collection_name: str | None = Field(default=None, min_length=1)
    thread_id: str | None = None
    filter_edit: FilterEditContract | None = None
    search_depth: Literal["quick", "balanced", "deep"] | None = None

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
    # When True, attach open-access PDF URLs to newly-created Zotero items (SCI-0302).
    enable_pdf_imports: bool = False


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


class ProviderInfo(BaseModel):
    """Combined capability + health view for a single search provider."""

    # Capability fields
    name: str
    fields: dict[str, str]  # ProviderField.value -> FieldSupport.value
    requires_key: bool
    key_env_var: str | None
    key_upgrade_hint: str | None
    notes: str
    # Health fields (defaults until a global health registry is wired in P8.2+)
    status: str
    reason: str
    last_ok_at: float | None
    last_error_at: float | None
    consecutive_failures: int
    retry_after: float | None


class CorrectQueryResponse(BaseModel):
    original: str
    corrected: str
    changed: bool


class KeyValidateRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    api_key: str = Field(min_length=1, max_length=512)

    model_config = {
        "json_schema_extra": {"examples": [{"provider": "semantic_scholar", "api_key": "s2-..."}]}
    }


class KeyValidateResponse(BaseModel):
    provider: str
    valid: bool
    error: str | None = None


class ExtractKeywordsRequest(BaseModel):
    query: str = Field(min_length=1)


class ExtractKeywordsResponse(BaseModel):
    include_keywords: list[str]
    exclude_keywords: list[str]
    collection_name: str | None
    min_year: int | None
    max_year: int | None
    min_citations: int | None
    max_citations: int | None
    open_access_only: bool


class LibraryDoctorRequest(BaseModel):
    collection_name: str = Field(min_length=1)


class GapFinderRequest(BaseModel):
    collection_name: str = Field(min_length=1)


class GapFinderResponse(BaseModel):
    reasoning: str
    papers: list[dict[str, Any]]


class CreateWatchRequest(BaseModel):
    name: str = Field(min_length=1)
    query: str = Field(min_length=1)
    collection_name: str | None = None
    filter_edit: FilterEditContract | None = None


class WatchSummary(BaseModel):
    id: str
    name: str
    query: str
    collection_name: str | None
    created_at: str
    last_run_at: str | None
    seen_count: int
    filter_edit: dict[str, Any] | None


class WatchRerunResponse(BaseModel):
    watch_id: str
    run_id: str
    thread_id: str
    status: Literal["awaiting_approval", "completed", "rejected", "failed"]
    new_count: int
    total_count: int


def _watch_to_summary(watch: Watch) -> WatchSummary:
    return WatchSummary(
        id=watch.id,
        name=watch.name,
        query=watch.query,
        collection_name=watch.collection_name,
        created_at=watch.created_at,
        last_run_at=watch.last_run_at,
        seen_count=len(watch.seen_fingerprints),
        filter_edit=watch.filter_edit,
    )


def _paper_fingerprints(paper: NormalizedPaper) -> tuple[str | None, str]:
    """Return (normalized_doi_or_None, title_author_fp) for a paper."""
    doi = normalize_doi(paper.doi)
    fp = title_author_fingerprint(paper.title, [a.name for a in paper.authors])
    return doi, fp


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
        self._watch_store: WatchStore | None = None

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

    def watch_store(self, settings: Settings) -> WatchStore:
        if self._watch_store is None:
            self._watch_store = WatchStore(settings.resolved_watch_dir)
        return self._watch_store


def create_app() -> FastAPI:  # noqa: PLR0915
    app = FastAPI(title="SciAgent API", version="0.1.0")
    _settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[_settings.api_rate_limit],
    )
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)
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

    @app.get("/version")
    async def _version() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        try:
            version = importlib.metadata.version("sciagent")
        except importlib.metadata.PackageNotFoundError:
            version = "0.0.0"
        return {"version": version}

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
                    search_depth=payload.search_depth,
                )
            else:
                state = await run_search_phase(
                    query=payload.query,
                    collection_name=collection_name,
                    thread_id=payload.thread_id,
                    settings=settings,
                    filter_edit=payload.filter_edit,
                    search_depth=payload.search_depth,
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
            enable_pdf_imports=payload.enable_pdf_imports,
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

    @app.get("/providers", response_model=dict[str, ProviderInfo])
    async def _providers(  # pyright: ignore[reportUnusedFunction]
        _: None = Depends(_require_backend_key),
    ) -> dict[str, ProviderInfo]:
        """Return capability + health for every known search provider.

        Health data is initialised to ``ProviderHealth()`` defaults because
        there is no global health registry yet.
        TODO(P8.2): wire real per-provider health state once the registry exists.
        """
        result: dict[str, ProviderInfo] = {}
        for name, caps in ALL_PROVIDER_CAPS.items():
            health = ProviderHealth()
            result[name] = ProviderInfo(
                name=caps.name,
                fields={f.value: s.value for f, s in caps.fields.items()},
                requires_key=caps.requires_key,
                key_env_var=caps.key_env_var,
                key_upgrade_hint=caps.key_upgrade_hint,
                notes=caps.notes,
                status=health.status.value,
                reason=health.reason,
                last_ok_at=health.last_ok_at,
                last_error_at=health.last_error_at,
                consecutive_failures=health.consecutive_failures,
                retry_after=health.retry_after,
            )
        return result

    @app.post("/keys/validate", response_model=KeyValidateResponse)
    async def _validate_key(  # pyright: ignore[reportUnusedFunction]
        payload: KeyValidateRequest,
        _: None = Depends(_require_backend_key),
    ) -> KeyValidateResponse:
        """Validate a provider API key with a minimal test call.

        Security: the key is NEVER logged or reflected in error responses.
        """
        if payload.provider not in KNOWN_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unknown_provider:{payload.provider}",
            )
        valid, error = await validate_key(payload.provider, payload.api_key)
        return KeyValidateResponse(
            provider=payload.provider,
            valid=valid,
            error=error,
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
            min_year=result.min_year,
            max_year=result.max_year,
            min_citations=result.min_citations,
            max_citations=result.max_citations,
            open_access_only=result.open_access_only,
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

    @app.post("/library-doctor", response_model=DoctorReport)
    async def _library_doctor(  # pyright: ignore[reportUnusedFunction]
        body: LibraryDoctorRequest,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> DoctorReport:
        return await scan_collection(body.collection_name, settings)

    @app.post("/gap-finder", response_model=GapFinderResponse)
    async def _gap_finder(  # pyright: ignore[reportUnusedFunction]
        body: GapFinderRequest,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> GapFinderResponse:
        provider = build_provider(settings)
        suggestion: GapSuggestion = await find_gaps(body.collection_name, settings, provider)
        return GapFinderResponse(
            reasoning=suggestion.reasoning,
            papers=[p.model_dump() for p in suggestion.papers],
        )

    # ── Watch List (SCI-0401/0402) ──────────────────────────────────────────

    @app.post("/watches", response_model=WatchSummary, status_code=status.HTTP_201_CREATED)
    async def _create_watch(  # pyright: ignore[reportUnusedFunction]
        body: CreateWatchRequest,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> WatchSummary:
        watch = create_watch(
            body.name,
            body.query,
            collection_name=body.collection_name,
            filter_edit=body.filter_edit.model_dump() if body.filter_edit is not None else None,
        )
        app_state.watch_store(settings).save(watch)
        return _watch_to_summary(watch)

    @app.get("/watches", response_model=list[WatchSummary])
    async def _list_watches(  # pyright: ignore[reportUnusedFunction]
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> list[WatchSummary]:
        return [_watch_to_summary(w) for w in app_state.watch_store(settings).list_watches()]

    @app.get("/watches/{watch_id}", response_model=WatchSummary)
    async def _get_watch(  # pyright: ignore[reportUnusedFunction]
        watch_id: str,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> WatchSummary:
        try:
            watch = app_state.watch_store(settings).load(watch_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="watch_not_found"
            ) from exc
        return _watch_to_summary(watch)

    @app.delete("/watches/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def _delete_watch(  # pyright: ignore[reportUnusedFunction]
        watch_id: str,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
    ) -> None:
        try:
            app_state.watch_store(settings).delete(watch_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="watch_not_found"
            ) from exc

    @app.post("/watches/{watch_id}/rerun", response_model=WatchRerunResponse)
    async def _rerun_watch(  # pyright: ignore[reportUnusedFunction]
        watch_id: str,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
        client_id: str = Depends(_client_id_header),
    ) -> WatchRerunResponse:
        ws = app_state.watch_store(settings)
        try:
            watch = ws.load(watch_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="watch_not_found"
            ) from exc

        filter_edit: FilterEditContract | None = (
            FilterEditContract.model_validate(watch.filter_edit)
            if watch.filter_edit is not None
            else None
        )
        collection = watch.collection_name or settings.zotero_collection_name
        try:
            state = await run_search_phase(
                query=watch.query,
                collection_name=collection,
                settings=settings,
                filter_edit=filter_edit,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"run_failed:{exc}"
            ) from exc

        # Tag papers as new vs seen and update the watch's seen_fingerprints.
        seen_set: set[str] = set(watch.seen_fingerprints)
        new_fps: list[str] = []
        raw_papers: list[dict[str, Any]] = state.get("papers", [])
        tagged_papers: list[dict[str, Any]] = []
        new_count = 0

        for raw in raw_papers:
            paper = NormalizedPaper.model_validate(raw)
            doi, fp = _paper_fingerprints(paper)
            is_new = (doi is None or doi not in seen_set) and fp not in seen_set
            watch_status_val = "new" if is_new else "seen"
            if is_new:
                new_count += 1
                if doi is not None:
                    new_fps.append(doi)
                new_fps.append(fp)
            tagged_papers.append({**raw, "watch_status": watch_status_val})

        # Persist updated watch.
        from datetime import UTC, datetime  # noqa: PLC0415

        watch.seen_fingerprints = list(dict.fromkeys(watch.seen_fingerprints + new_fps))
        watch.last_run_at = datetime.now(tz=UTC).isoformat(timespec="seconds")
        ws.save(watch)

        run_id: str = state["thread_id"]
        updated_state = {**cast(dict[str, Any], state), "papers": tagged_papers}
        store.put(
            _RunRecord(
                run_id=run_id,
                owner=client_id,
                thread_id=run_id,
                status="awaiting_approval",
                state=updated_state,
            )
        )
        return WatchRerunResponse(
            watch_id=watch_id,
            run_id=run_id,
            thread_id=run_id,
            status="awaiting_approval",
            new_count=new_count,
            total_count=len(tagged_papers),
        )

    return app


app = create_app()
