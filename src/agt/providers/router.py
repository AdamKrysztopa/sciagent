"""Provider factory and routing logic."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from agt.config import LLMProviderName, Settings, provider_env_aliases
from agt.providers.anthropic import AnthropicProvider
from agt.providers.openai import OpenAIProvider
from agt.providers.protocol import LLMProvider, ProviderRateLimitError, ProviderTimeoutError
from agt.providers.xai import TokenPricing, XAIProvider

ProviderBuilder = Callable[[Settings], LLMProvider]


def _required_env_message(provider_name: LLMProviderName) -> str:
    env_names = provider_env_aliases(provider_name)
    return " or ".join(env_names)


def _missing_provider_key_error(provider_name: LLMProviderName) -> RuntimeError:
    return RuntimeError(
        f"Selected provider '{provider_name}' requires {_required_env_message(provider_name)}. "
        "Set one of those env vars or choose a different provider with AGT_LLM_PROVIDER."
    )


def _unimplemented_provider_error(provider_name: LLMProviderName) -> RuntimeError:
    supported = ", ".join(sorted(_PROVIDER_BUILDERS))
    return RuntimeError(
        f"Selected provider '{provider_name}' is not implemented in this runtime. "
        f"Supported providers: {supported}. Required env var(s): {_required_env_message(provider_name)}."
    )


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
    if settings.xai_api_key is None:
        raise _missing_provider_key_error("xai")
    return XAIProvider(
        runtime=settings.runtime,
        api_key=settings.xai_api_key.get_secret_value(),
        pricing=TokenPricing(
            input_per_1k_tokens_usd=settings.xai_input_cost_per_1k_tokens_usd,
            output_per_1k_tokens_usd=settings.xai_output_cost_per_1k_tokens_usd,
        ),
    )


def _build_openai(settings: Settings) -> LLMProvider:
    if settings.openai_api_key is None:
        raise _missing_provider_key_error("openai")
    return OpenAIProvider(
        runtime=settings.runtime,
        api_key=settings.openai_api_key.get_secret_value(),
    )


def _build_anthropic(settings: Settings) -> LLMProvider:
    if settings.anthropic_api_key is None:
        raise _missing_provider_key_error("anthropic")
    return AnthropicProvider(
        runtime=settings.runtime,
        api_key=settings.anthropic_api_key.get_secret_value(),
    )


_PROVIDER_BUILDERS: dict[str, ProviderBuilder] = {
    "anthropic": _build_anthropic,
    "openai": _build_openai,
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


def _build_single_provider(settings: Settings, provider_name: LLMProviderName) -> LLMProvider:
    builder = _PROVIDER_BUILDERS.get(provider_name)
    if builder is None:
        raise _unimplemented_provider_error(provider_name)
    return builder(settings)


def build_provider(settings: Settings) -> LLMProvider:
    """Build provider implementation based on runtime settings."""

    primary_name = settings.runtime.provider
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
