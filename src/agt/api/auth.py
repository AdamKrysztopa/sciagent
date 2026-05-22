"""Per-user API key authentication and admin authorization."""

from __future__ import annotations

import hmac
from collections.abc import Callable

from fastapi import Header, HTTPException, Request, status

from agt.secrets import UserRegistry


def authenticate(
    get_registry: Callable[[], UserRegistry],
) -> Callable[..., str]:
    """Return a FastAPI dependency that validates ``X-AGT-API-Key`` against the registry.

    The dependency sets ``request.state.user_slug`` and ``request.state.is_admin``
    for downstream middleware and guards (e.g. ``require_admin``).

    Uses ``hmac.compare_digest`` and iterates *all* users to prevent timing attacks.
    """

    def _authenticate(
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-AGT-API-Key"),
    ) -> str:
        registry = get_registry()
        users = registry.get_all()
        candidate = x_api_key or ""
        matched_slug: str | None = None
        for slug, entry in users.items():
            if hmac.compare_digest(candidate, entry.key):
                matched_slug = slug
        if matched_slug is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_api_key",
            )
        request.state.user_slug = matched_slug
        request.state.is_admin = users[matched_slug].is_admin
        return matched_slug

    return _authenticate


def require_admin(request: Request) -> None:
    """FastAPI dependency that rejects non-admin users with HTTP 403.

    Must be used *after* ``authenticate`` in the dependency chain so that
    ``request.state.is_admin`` is populated.
    """
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_required",
        )
