"""Admin API endpoints for user key management and usage monitoring."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

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
    async def list_keys() -> list[UserSummary]:  # pyright: ignore[reportUnusedFunction]
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
    async def create_key(body: CreateKeyRequest) -> CreateKeyResponse:  # pyright: ignore[reportUnusedFunction]
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
            created_at=datetime.now(UTC).isoformat(),
        )
        users[body.slug] = entry
        registry.update(users)
        return CreateKeyResponse(slug=body.slug, key=key, email=body.email, budget_usd=budget)

    @router.delete("/keys/{slug}")
    async def revoke_key(slug: str) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
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
    async def update_key(slug: str, body: UpdateKeyRequest) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
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
    async def get_usage() -> dict[str, dict[str, object]]:  # pyright: ignore[reportUnusedFunction]
        return budget_tracker.get_all_usage(default_budget=default_budget)

    return router
