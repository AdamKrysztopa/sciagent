"""Provider factory and routing logic."""

from __future__ import annotations

from agt.config import Settings
from agt.providers.protocol import LLMProvider
from agt.providers.xai import TokenPricing, XAIProvider


def build_provider(settings: Settings) -> LLMProvider:
    """Build provider implementation based on runtime settings."""

    runtime = settings.runtime
    if runtime.provider == "xai":
        return XAIProvider(
            runtime=runtime,
            api_key=settings.xai_api_key.get_secret_value(),
            pricing=TokenPricing(
                input_per_1k_tokens_usd=settings.xai_input_cost_per_1k_tokens_usd,
                output_per_1k_tokens_usd=settings.xai_output_cost_per_1k_tokens_usd,
            ),
        )

    raise RuntimeError(
        "Configured provider is not implemented yet. Use AGT_LLM_PROVIDER=xai for now. "
        "Swap path for openai/anthropic/groq is documented in docs/settings.md."
    )
