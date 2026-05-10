"""Shared helpers for runnable example scripts."""

from __future__ import annotations

import os
from pathlib import Path

from agt.config import LLMProviderName, Settings
from agt.providers.protocol import LLMProvider
from agt.providers.router import build_provider

_DUMMY_XAI_KEY = "xai-local"
_DUMMY_OPENAI_KEY = "openai-local"
_DUMMY_ANTHROPIC_KEY = "anthropic-local"
_DEMO_PROVIDER_PRIORITY: tuple[LLMProviderName, ...] = ("openai", "anthropic", "xai")
_PROVIDER_KEY_NAMES: dict[LLMProviderName, tuple[str, str]] = {
    "openai": ("AGT_OPENAI_API_KEY", "OPENAI_API_KEY"),
    "anthropic": ("AGT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    "xai": ("AGT_XAI_API_KEY", "XAI_API_KEY"),
    "groq": ("AGT_GROQ_API_KEY", "GROQ_API_KEY"),
}
_DUMMY_PROVIDER_KEYS: dict[LLMProviderName, str] = {
    "openai": _DUMMY_OPENAI_KEY,
    "anthropic": _DUMMY_ANTHROPIC_KEY,
    "xai": _DUMMY_XAI_KEY,
    "groq": "groq-local",
}


def _resolve_dotenv_key(*names: str) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None

    values: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        normalized_name = name.strip()
        if normalized_name in names and normalized_name not in values:
            values[normalized_name] = value.strip().strip("\"'")

    for name in names:
        value = values.get(name)
        if value:
            return value
    return None


def resolve_env_key(*names: str) -> str | None:
    """Return the first non-empty environment value from candidate names."""

    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return _resolve_dotenv_key(*names)


def resolve_xai_key() -> str:
    """Resolve xAI API key from environment variables or local .env."""

    return resolve_env_key("AGT_XAI_API_KEY", "XAI_API_KEY") or _DUMMY_XAI_KEY


def default_provider_settings_payload() -> dict[str, str]:
    """Resolve the best demo provider payload without forcing xAI as the first path."""

    for provider_name in _DEMO_PROVIDER_PRIORITY:
        canonical_name, alias_name = _PROVIDER_KEY_NAMES[provider_name]
        key = resolve_env_key(canonical_name, alias_name)
        if key:
            return {
                "AGT_LLM_PROVIDER": provider_name,
                canonical_name: key,
            }

    return {
        "AGT_LLM_PROVIDER": "openai",
        "AGT_OPENAI_API_KEY": _DUMMY_OPENAI_KEY,
    }


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
        key_secret = settings.provider_api_key(settings.runtime.provider)
        if key_secret is None:
            return None
        key = key_secret.get_secret_value()
        if key == _DUMMY_PROVIDER_KEYS[settings.runtime.provider]:
            return None
        return build_provider(settings)
    except Exception:
        return None


def default_zotero_api_key() -> str:
    return resolve_env_key("AGT_ZOTERO_API_KEY", "ZOTERO_API_KEY") or "zot-local"


def default_zotero_library_id() -> str:
    return resolve_env_key("AGT_ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_ID") or "local-library"
