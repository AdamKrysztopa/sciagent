"""Startup checks for Zotero configuration."""

from __future__ import annotations

from dataclasses import dataclass

from agt.config import Settings


@dataclass(slots=True)
class PreflightResult:
    ok: bool
    message: str


def run_zotero_preflight(settings: Settings) -> PreflightResult:
    """Perform static checks before calling Zotero APIs."""

    if settings.zotero_library_type not in {"user", "group"}:
        return PreflightResult(ok=False, message="Invalid library type")
    if not settings.zotero_library_id.strip():
        return PreflightResult(ok=False, message="Missing Zotero library id")
    return PreflightResult(ok=True, message="Zotero preflight checks passed")
