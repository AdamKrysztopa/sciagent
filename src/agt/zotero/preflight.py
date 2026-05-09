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
    section = access.get(library_type, {})
    return bool(section.get("write"))


def _library_probe_path(settings: Settings) -> str:
    if settings.zotero_library_type == "group":
        return f"/groups/{settings.zotero_library_id}/collections?limit=1"
    return f"/users/{settings.zotero_library_id}/collections?limit=1"


def _validate_zotero_settings(settings: Settings) -> PreflightResult | None:
    """Return error PreflightResult if settings are invalid or incomplete, None if valid."""
    missing = [
        name
        for name, val in [
            ("AGT_ZOTERO_API_KEY", settings.zotero_api_key),
            ("AGT_ZOTERO_LIBRARY_ID", settings.zotero_library_id),
        ]
        if val is None
    ]
    if missing:
        return PreflightResult(
            ok=False,
            message=f"Missing required Zotero settings: {', '.join(missing)}",
            can_read=False,
            can_write=False,
            key_valid=False,
        )

    assert settings.zotero_api_key is not None
    api_key = settings.zotero_api_key.get_secret_value()
    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        return PreflightResult(
            ok=False,
            message="AGT_ZOTERO_API_KEY contains non-ASCII characters — check for lookalike Unicode letters in the key",
            can_read=False,
            can_write=False,
            key_valid=False,
        )
    return None


def run_zotero_preflight(settings: Settings, client: httpx.Client | None = None) -> PreflightResult:
    """Verify Zotero key validity and target-library read/write capability."""
    validation_error = _validate_zotero_settings(settings)
    if validation_error is not None:
        return validation_error

    assert settings.zotero_api_key is not None
    assert settings.zotero_library_id is not None
    api_key = settings.zotero_api_key.get_secret_value()

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
