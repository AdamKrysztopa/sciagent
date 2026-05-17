"""FastAPI dependency for request-scoped credential injection (MU1)."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Header, HTTPException, status

from agt.config import LibraryType
from agt.credential_context import RequestCredentials, current_credentials


def get_credentials(  # noqa: PLR0913
    zotero_api_key: str | None = Header(default=None, alias="X-Zotero-API-Key"),
    zotero_library_id: str | None = Header(default=None, alias="X-Zotero-Library-ID"),
    zotero_library_type: str | None = Header(default=None, alias="X-Zotero-Library-Type"),
    llm_api_key: str | None = Header(default=None, alias="X-LLM-API-Key"),
    llm_provider: str | None = Header(default=None, alias="X-LLM-Provider"),
    llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    llm_base_url: str | None = Header(default=None, alias="X-LLM-Base-URL"),
) -> Generator[RequestCredentials]:
    """Validate Zotero headers and bind credentials to the request context."""
    if not zotero_api_key or not zotero_library_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_zotero_credentials",
            headers={"WWW-Authenticate": "X-Zotero-API-Key"},
        )

    lib_type: LibraryType = (
        "group"
        if zotero_library_type and zotero_library_type.strip().lower() == "group"
        else "user"
    )

    creds = RequestCredentials(
        zotero_api_key=zotero_api_key,
        zotero_library_id=zotero_library_id,
        zotero_library_type=lib_type,
        llm_api_key=llm_api_key or None,
        llm_provider=llm_provider or None,
        llm_model=llm_model or None,
        llm_base_url=llm_base_url or None,
    )

    previous = current_credentials.get()
    current_credentials.set(creds)
    try:
        yield creds
    finally:
        current_credentials.set(previous)
