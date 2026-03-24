"""Provider factory and routing logic."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from agt.config import Settings
from agt.providers.protocol import LLMProvider, ProviderRateLimitError, ProviderTimeoutError
from agt.providers.xai import TokenPricing, XAIProvider

ProviderBuilder = Callable[[Settings], LLMProvider]


class RoutedProvider(LLMProvider):
    """Provider wrapper that applies failover policy to a fallback provider."""

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        *,
        failover_on_timeout: bool,
        failover_on_rate_limit: bool,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._failover_on_timeout = failover_on_timeout
        self._failover_on_rate_limit = failover_on_rate_limit

    def _should_failover(self, exc: Exception) -> bool:
        if isinstance(exc, ProviderTimeoutError):
            return self._failover_on_timeout
        if isinstance(exc, ProviderRateLimitError):
            return self._failover_on_rate_limit
        return False

    def invoke(self, prompt: str) -> str:
        try:
            return self._primary.invoke(prompt)
        except Exception as exc:
            if not self._should_failover(exc):
                raise
            return self._fallback.invoke(prompt)

    async def ainvoke(self, prompt: str) -> str:
        try:
            return await self._primary.ainvoke(prompt)
        except Exception as exc:
            if not self._should_failover(exc):
                raise
            return await self._fallback.ainvoke(prompt)

    def bind_tools(self, tools: Sequence[Any]) -> LLMProvider:
        return RoutedProvider(
            primary=self._primary.bind_tools(tools),
            fallback=self._fallback.bind_tools(tools),
            failover_on_timeout=self._failover_on_timeout,
            failover_on_rate_limit=self._failover_on_rate_limit,
        )


def _build_xai(settings: Settings) -> LLMProvider:
    return XAIProvider(
        runtime=settings.runtime,
        api_key=settings.xai_api_key.get_secret_value(),
        pricing=TokenPricing(
            input_per_1k_tokens_usd=settings.xai_input_cost_per_1k_tokens_usd,
            output_per_1k_tokens_usd=settings.xai_output_cost_per_1k_tokens_usd,
        ),
    )


_PROVIDER_BUILDERS: dict[str, ProviderBuilder] = {
    "xai": _build_xai,
}


def register_provider_builder(provider_name: str, builder: ProviderBuilder) -> None:
    """Register or override a provider builder by name."""

    _PROVIDER_BUILDERS[provider_name] = builder


def get_provider_builder(provider_name: str) -> ProviderBuilder | None:
    """Get a provider builder if present."""

    return _PROVIDER_BUILDERS.get(provider_name)


def unregister_provider_builder(provider_name: str) -> None:
    """Remove a provider builder if present."""

    _PROVIDER_BUILDERS.pop(provider_name, None)


def _build_single_provider(settings: Settings, provider_name: str) -> LLMProvider:
    builder = _PROVIDER_BUILDERS.get(provider_name)
    if builder is None:
        raise RuntimeError(
            "Configured provider is not implemented yet. Use AGT_LLM_PROVIDER=xai for now. "
            "Swap path for openai/anthropic/groq is documented in docs/settings.md."
        )
    return builder(settings)


def build_provider(settings: Settings) -> LLMProvider:
    """Build provider implementation based on runtime settings."""

    primary_name = settings.llm_provider
    primary = _build_single_provider(settings, primary_name)
    fallback_name = settings.llm_fallback_provider
    if fallback_name is None:
        return primary

    if fallback_name == primary_name:
        return primary

    fallback = _build_single_provider(settings, fallback_name)
    return RoutedProvider(
        primary=primary,
        fallback=fallback,
        failover_on_timeout=settings.llm_failover_on_timeout,
        failover_on_rate_limit=settings.llm_failover_on_rate_limit,
    )
