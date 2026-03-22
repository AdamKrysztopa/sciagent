"""FastAPI backend exposing health/run/resume/status workflow endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from agt.config import Settings, get_settings
from agt.graph.workflow import resume_workflow, run_search_phase
from agt.models import AgentState
from agt.zotero.preflight import run_zotero_preflight


class RunRequest(BaseModel):
    query: str = Field(min_length=1)
    collection_name: str = Field(min_length=1)
    thread_id: str | None = None


class ResumeRequest(BaseModel):
    run_id: str = Field(min_length=1)
    approved: bool
    collection_name: str | None = None
    selected_indices: list[int] | None = None


class RunAcceptedResponse(BaseModel):
    run_id: str
    thread_id: str
    status: Literal["awaiting_approval", "completed", "rejected", "failed"]


class StatusResponse(BaseModel):
    run_id: str
    thread_id: str
    status: Literal["awaiting_approval", "completed", "rejected", "failed"]
    state: dict[str, Any] | None
    error: str | None = None


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


def create_app() -> FastAPI:
    app = FastAPI(title="SciAgent API", version="0.1.0")
    store = _RunStore()

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
            "provider": settings.llm_provider,
            "fallback_provider": settings.llm_fallback_provider,
        }

    @app.post("/run", response_model=RunAcceptedResponse)
    async def _run(  # pyright: ignore[reportUnusedFunction]
        payload: RunRequest,
        _: None = Depends(_require_backend_key),
        settings: Settings = Depends(get_settings),
        client_id: str = Depends(_client_id_header),
    ) -> RunAcceptedResponse:
        try:
            state = await run_search_phase(
                query=payload.query,
                collection_name=payload.collection_name,
                thread_id=payload.thread_id,
                settings=settings,
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

        run_id = state["thread_id"]
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

    return app


app = create_app()
