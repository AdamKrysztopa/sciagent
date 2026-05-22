"""User registry: GCP Secret Manager with single-key fallback."""

from __future__ import annotations

import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import structlog

if TYPE_CHECKING:
    from agt.config import Settings

_log = structlog.get_logger()
_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


@dataclass(frozen=True, slots=True)
class UserEntry:
    """Immutable value object representing a registered user."""

    key: str
    email: str
    budget_usd: float
    is_admin: bool
    created_at: str


def generate_key(slug: str) -> str:
    """Generate an API key in the format ``agt_{slug}_{32-hex-chars}``."""
    if not _SLUG_RE.match(slug):
        raise ValueError(f"slug must be 1-32 chars matching [a-z0-9_-], got: {slug!r}")
    return f"agt_{slug}_{secrets.token_hex(16)}"


def _entry_from_dict(data: dict[str, object]) -> UserEntry:
    return UserEntry(
        key=str(data.get("key", "")),
        email=str(data.get("email", "")),
        budget_usd=float(data.get("budget_usd", 2.0)),  # type: ignore[arg-type]
        is_admin=bool(data.get("is_admin", False)),
        created_at=str(data.get("created_at", "")),
    )


def _entry_to_dict(entry: UserEntry) -> dict[str, object]:
    return {
        "key": entry.key,
        "email": entry.email,
        "budget_usd": entry.budget_usd,
        "is_admin": entry.is_admin,
        "created_at": entry.created_at,
    }


class UserRegistry:
    """Read/write user registry backed by GCP Secret Manager with single-key fallback."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, UserEntry] | None = None
        self._cache_time: float = 0.0

    def get_all(self) -> dict[str, UserEntry]:
        """Return all registered users, using Secret Manager or single-key fallback."""
        if self._settings.gcp_project is not None:
            return self._get_cached()
        return self._single_key_fallback()

    def update(self, registry: dict[str, UserEntry]) -> None:
        """Write an updated registry to Secret Manager (not available in fallback mode)."""
        if self._settings.gcp_project is None:
            raise RuntimeError("Cannot update registry in single-key fallback mode")
        self._write_to_secret_manager(registry)
        self._cache = dict(registry)
        self._cache_time = time.monotonic()

    def invalidate_cache(self) -> None:
        """Force the next ``get_all`` call to re-read from Secret Manager."""
        self._cache = None
        self._cache_time = 0.0

    def _single_key_fallback(self) -> dict[str, UserEntry]:
        if self._settings.backend_api_key is None:
            return {}
        return {
            "default": UserEntry(
                key=self._settings.backend_api_key.get_secret_value(),
                email="",
                budget_usd=self._settings.shared_llm_budget_per_user_usd,
                is_admin=True,
                created_at="",
            ),
        }

    def _get_cached(self) -> dict[str, UserEntry]:
        now = time.monotonic()
        if (
            self._cache is not None
            and (now - self._cache_time) < self._settings.secret_cache_ttl_seconds
        ):
            return self._cache
        self._cache = self._read_from_secret_manager()
        self._cache_time = now
        return self._cache

    def _read_from_secret_manager(self) -> dict[str, UserEntry]:
        from google.cloud import secretmanager  # type: ignore[import-untyped]  # noqa: PLC0415

        client = secretmanager.SecretManagerServiceClient()
        name = (
            f"projects/{self._settings.gcp_project}"
            f"/secrets/{self._settings.gcp_secret_name}/versions/latest"
        )
        response = client.access_secret_version(  # pyright: ignore[reportUnknownMemberType]
            request={"name": name}
        )
        payload: str = response.payload.data.decode("UTF-8")
        raw: object = json.loads(payload)
        if not isinstance(raw, dict):
            _log.error("secret_manager_invalid_format", secret=self._settings.gcp_secret_name)
            return {}
        raw_dict = cast(dict[str, object], raw)
        result: dict[str, UserEntry] = {}
        for slug, entry_data in raw_dict.items():
            if isinstance(entry_data, dict):
                result[slug] = _entry_from_dict(cast(dict[str, object], entry_data))
        return result

    def _write_to_secret_manager(self, registry: dict[str, UserEntry]) -> None:
        from google.cloud import secretmanager  # type: ignore[import-untyped]  # noqa: PLC0415

        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{self._settings.gcp_project}/secrets/{self._settings.gcp_secret_name}"
        payload_dict = {slug: _entry_to_dict(entry) for slug, entry in registry.items()}
        payload_bytes = json.dumps(payload_dict, indent=2).encode("UTF-8")
        client.add_secret_version(  # pyright: ignore[reportUnknownMemberType]
            request={"parent": parent, "payload": {"data": payload_bytes}}
        )
        _log.info(
            "secret_manager_updated",
            secret=self._settings.gcp_secret_name,
            user_count=len(registry),
        )
