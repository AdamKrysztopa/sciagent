"""Provider factory and routing logic."""

from __future__ import annotations

from agt.config import Settings
from agt.providers.protocol import LLMProvider
from agt.providers.xai import XAIProvider


def build_provider(settings: Settings) -> LLMProvider:
    """Build provider implementation based on runtime settings."""

    runtime = settings.runtime
    if runtime.provider == "xai":
        return XAIProvider(runtime=runtime, api_key=settings.xai_api_key.get_secret_value())

    raise RuntimeError(
        "Configured provider is not implemented yet. Use AGT_LLM_PROVIDER=xai for now. "
        "Swap path for openai/anthropic/groq is documented in docs/settings.md."
    )
