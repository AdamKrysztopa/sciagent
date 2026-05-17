"""Request-scoped Zotero + LLM credential context for multi-user mode (MU1).

``current_credentials`` is set by ``agt.api.credentials.get_credentials`` at
request entry and reset in ``finally``.  Tools call the resolve_* helpers which
fall back to ``settings`` when the contextvar is unset (local single-user dev).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

from pydantic import BaseModel

from agt.config import LibraryType

if TYPE_CHECKING:
    from agt.config import Settings


class RequestCredentials(BaseModel):
    """Per-request Zotero credentials and optional LLM override from HTTP headers."""

    zotero_api_key: str
    zotero_library_id: str
    zotero_library_type: LibraryType = "user"
    llm_api_key: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None


current_credentials: ContextVar[RequestCredentials | None] = ContextVar(
    "current_credentials", default=None
)


def resolve_zotero_api_key(settings: Settings) -> str:
    """Return Zotero API key from request context, falling back to settings."""
    creds = current_credentials.get()
    if creds is not None:
        return creds.zotero_api_key
    if settings.zotero_api_key is None:
        raise ValueError(
            "No Zotero API key — send X-Zotero-API-Key header or set AGT_ZOTERO_API_KEY"
        )
    return settings.zotero_api_key.get_secret_value()


def resolve_zotero_library_id(settings: Settings) -> str:
    """Return Zotero library ID from request context, falling back to settings."""
    creds = current_credentials.get()
    if creds is not None:
        return creds.zotero_library_id
    if settings.zotero_library_id is None:
        raise ValueError(
            "No Zotero library ID — send X-Zotero-Library-ID header or set AGT_ZOTERO_LIBRARY_ID"
        )
    return settings.zotero_library_id


def resolve_zotero_library_type(settings: Settings) -> LibraryType:
    """Return library type from request context, falling back to settings."""
    creds = current_credentials.get()
    if creds is not None:
        return creds.zotero_library_type
    return settings.zotero_library_type
