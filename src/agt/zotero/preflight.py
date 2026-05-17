"""Startup checks for Zotero API capabilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, cast

import httpx

from agt.config import Settings
from agt.credential_context import (
    resolve_zotero_api_key,
    resolve_zotero_library_id,
    resolve_zotero_library_type,
)

ZOTERO_API_BASE = "https://api.zotero.org"
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401


@dataclass(slots=True)
class PreflightResult:
    """Result payload for startup permission checks."""

    ok: bool
    message: str
    can_read: bool
    can_write: bool
    key_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_write_capability(payload: dict[str, Any], library_type: str) -> bool:
    # Zotero /keys/current returns: {"access": {"user": {"write": true}, "groups": {...}}}
    access: dict[str, Any] = payload.get("access") or {}
    if library_type == "user":
        user: dict[str, Any] = access.get("user") or {}
        return bool(user.get("write"))
    # For group libraries check access.groups.all or any group entry.
    groups: dict[str, Any] = access.get("groups") or {}
    all_group: dict[str, Any] = groups.get("all") or {}
    if all_group.get("write"):
        return True
    return any(
        bool(cast(dict[str, Any], v).get("write")) for v in groups.values() if isinstance(v, dict)
    )


def _library_probe_path(lib_type: str, lib_id: str) -> str:
    if lib_type == "group":
        return f"/groups/{lib_id}/collections?limit=1"
    return f"/users/{lib_id}/collections?limit=1"


def run_zotero_preflight(settings: Settings, client: httpx.Client | None = None) -> PreflightResult:  # noqa: PLR0911
    """Verify Zotero key validity and target-library read/write capability.

    Credentials are resolved from the request contextvar first, falling back to
    ``settings`` for local single-user dev mode.
    """
    try:
        api_key = resolve_zotero_api_key(settings)
        lib_id = resolve_zotero_library_id(settings)
    except ValueError as exc:
        return PreflightResult(
            ok=False,
            message=str(exc),
            can_read=False,
            can_write=False,
            key_valid=False,
        )

    lib_type = resolve_zotero_library_type(settings)

    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        return PreflightResult(
            ok=False,
            message="Zotero API key contains non-ASCII characters — check for lookalike Unicode letters",
            can_read=False,
            can_write=False,
            key_valid=False,
        )

    owns_client = client is None
    api_client = client or httpx.Client(base_url=ZOTERO_API_BASE, timeout=settings.timeout_seconds)
    headers = {"Zotero-API-Key": api_key}

    try:
        key_resp = api_client.get("/keys/current", headers=headers)
        if key_resp.status_code == HTTP_UNAUTHORIZED:
            return PreflightResult(
                ok=False,
                message="Zotero API key is invalid or expired.",
                can_read=False,
                can_write=False,
                key_valid=False,
            )
        key_resp.raise_for_status()
        key_payload = key_resp.json()

        can_write = _get_write_capability(key_payload, lib_type)

        probe_resp = api_client.get(_library_probe_path(lib_type, lib_id), headers=headers)
        can_read = probe_resp.status_code == HTTP_OK

        if not can_read:
            return PreflightResult(
                ok=False,
                message=(
                    "Unable to access target Zotero library. Check library type/id and key scope."
                ),
                can_read=False,
                can_write=can_write,
                key_valid=True,
            )

        if not can_write:
            return PreflightResult(
                ok=False,
                message=(
                    "Zotero key lacks write permission for the configured library. "
                    "Grant write access or use a different key."
                ),
                can_read=True,
                can_write=False,
                key_valid=True,
            )

        return PreflightResult(
            ok=True,
            message="Zotero preflight checks passed.",
            can_read=True,
            can_write=True,
            key_valid=True,
        )
    except httpx.HTTPError as exc:
        return PreflightResult(
            ok=False,
            message=f"Zotero preflight failed: {exc}",
            can_read=False,
            can_write=False,
            key_valid=False,
        )
    finally:
        if owns_client:
            api_client.close()
