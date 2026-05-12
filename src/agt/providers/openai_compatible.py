"""Generic OpenAI-compatible provider adapter (SCI-0601).

Covers DeepSeek, Together AI, Anyscale, LM Studio, and any endpoint that
speaks the OpenAI /chat/completions protocol.
"""

from __future__ import annotations

from typing import Any, cast

from agt.config import RuntimeConfig
from agt.providers.xai import HTTPXAIModel, TokenPricing, XAIProvider


class OpenAICompatibleProvider(XAIProvider):
    """Adapter for any OpenAI-compatible /chat/completions endpoint.

    Pass ``base_url`` to target a custom API (e.g. ``https://api.deepseek.com/v1``).
    Pricing defaults to zero; supply ``TokenPricing`` for cost tracking.
    """

    def __init__(  # noqa: PLR0913
        self,
        runtime: RuntimeConfig,
        api_key: str,
        base_url: str,
        pricing: TokenPricing | None = None,
        model_factory: Any | None = None,
        model: Any | None = None,
    ) -> None:
        _base_url = base_url

        def _factory(**kwargs: Any) -> HTTPXAIModel:
            return HTTPXAIModel(
                api_key=cast(str, kwargs["api_key"]),
                model=cast(str, kwargs["model"]),
                timeout=cast(int, kwargs["timeout"]),
                max_retries=cast(int, kwargs["max_retries"]),
                temperature=cast(float, kwargs["temperature"]),
                tools=[],
                _base_url=_base_url,
            )

        super().__init__(
            runtime=runtime,
            api_key=api_key,
            pricing=pricing
            or TokenPricing(
                input_per_1k_tokens_usd=0.0,
                output_per_1k_tokens_usd=0.0,
            ),
            model_factory=model_factory or _factory,
            model=model,
        )
