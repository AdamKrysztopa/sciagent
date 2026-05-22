"""Admin API endpoints for user key management and usage monitoring."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agt.api.auth import require_admin
from agt.comms import MessageChannel, MessageStore, MessageType, Recipients, dispatch_message_emails
from agt.config import Settings
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


class CreateMessageRequest(BaseModel):
    type: MessageType
    text: str = Field(min_length=1, max_length=2000)
    recipients: list[str] | Literal["all"] = "all"
    channel: MessageChannel = "banner"


def create_admin_router(
    get_registry: Callable[[], UserRegistry],
    budget_tracker: SharedBudgetTracker,
    message_store: MessageStore,
    *,
    default_budget: float,
    settings: Settings,
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

    @router.get("/health")
    async def admin_health() -> dict[str, object]:  # pyright: ignore[reportUnusedFunction]
        return {
            "active_users": len(get_registry().get_all()),
            "budget_tracker_users": len(
                budget_tracker.get_all_usage(default_budget=default_budget)
            ),
        }

    @router.post("/messages", status_code=status.HTTP_201_CREATED)
    async def create_message(body: CreateMessageRequest) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        recipients: Recipients = (
            body.recipients if isinstance(body.recipients, str) else list(body.recipients)
        )
        msg = message_store.create(
            type=body.type,
            text=body.text,
            recipients=recipients,
            channel=body.channel,
        )
        email_key = settings.email_api_key.get_secret_value() if settings.email_api_key else ""
        await dispatch_message_emails(
            msg,
            get_registry(),
            api_key=email_key,
            from_address=settings.email_from,
        )
        return {"id": msg.id, "status": "created"}

    @router.get("/messages")
    async def list_messages() -> list[dict[str, object]]:  # pyright: ignore[reportUnusedFunction]
        return [
            {
                "id": m.id,
                "type": m.type,
                "text": m.text,
                "recipients": m.recipients,
                "channel": m.channel,
                "created_at": m.created_at,
            }
            for m in message_store.list_all()
        ]

    return router
