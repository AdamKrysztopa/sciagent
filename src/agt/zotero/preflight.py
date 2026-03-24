"""Startup checks for Zotero API capabilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import httpx

from agt.config import Settings

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
    access = payload.get("access", {})
    library_access = access.get("library", {})
    section = library_access.get(library_type, {})
    return bool(section.get("write"))


def _library_probe_path(settings: Settings) -> str:
    if settings.zotero_library_type == "group":
        return f"/groups/{settings.zotero_library_id}/collections?limit=1"
    return f"/users/{settings.zotero_library_id}/collections?limit=1"


def run_zotero_preflight(settings: Settings, client: httpx.Client | None = None) -> PreflightResult:
    """Verify Zotero key validity and target-library read/write capability."""

    owns_client = client is None
    api_client = client or httpx.Client(base_url=ZOTERO_API_BASE, timeout=settings.timeout_seconds)
    headers = {"Zotero-API-Key": settings.zotero_api_key.get_secret_value()}

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

        can_write = _get_write_capability(key_payload, settings.zotero_library_type)

        probe_resp = api_client.get(_library_probe_path(settings), headers=headers)
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
