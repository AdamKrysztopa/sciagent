"""Shared helpers for runnable example scripts."""

from __future__ import annotations

import os
from pathlib import Path

from agt.config import Settings
from agt.providers.protocol import LLMProvider
from agt.providers.router import build_provider

_DUMMY_XAI_KEY = "xai-local"


def resolve_env_key(*names: str) -> str | None:
    """Return the first non-empty environment value from candidate names."""

    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def resolve_xai_key() -> str:
    """Resolve xAI API key from environment variables or local .env."""

    key = resolve_env_key("AGT_XAI_API_KEY", "XAI_API_KEY")
    if key:
        return key

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                continue
            name, _, value = stripped.partition("=")
            if name.strip() in {"AGT_XAI_API_KEY", "XAI_API_KEY"}:
                return value.strip().strip("\"'")

    return _DUMMY_XAI_KEY


def normalize_strict_settings_env() -> None:
    """Normalize known alias env vars to AGT_* names for strict settings parsing."""

    if "AGT_XAI_API_KEY" not in os.environ:
        alias = os.getenv("XAI_API_KEY")
        if alias:
            os.environ["AGT_XAI_API_KEY"] = alias

    # Settings is strict; keep only modeled key names for xAI.
    os.environ.pop("XAI_API_KEY", None)

    if "AGT_OPENAI_API_KEY" not in os.environ:
        alias = os.getenv("OPENAI_API_KEY")
        if alias:
            os.environ["AGT_OPENAI_API_KEY"] = alias

    if "AGT_ANTHROPIC_API_KEY" not in os.environ:
        alias = os.getenv("ANTHROPIC_API_KEY")
        if alias:
            os.environ["AGT_ANTHROPIC_API_KEY"] = alias

    # Strip plain aliases that can conflict under strict extra='forbid'.
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("ANTHROPIC_API_KEY", None)


def try_build_provider(settings: Settings) -> LLMProvider | None:
    """Build an LLM provider only when a non-dummy key is configured."""

    try:
        key = settings.xai_api_key.get_secret_value()
        if key == _DUMMY_XAI_KEY:
            return None
        return build_provider(settings)
    except Exception:
        return None


def default_zotero_api_key() -> str:
    return resolve_env_key("AGT_ZOTERO_API_KEY", "ZOTERO_API_KEY") or "zot-local"


def default_zotero_library_id() -> str:
    return resolve_env_key("AGT_ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_ID") or "local-library"
