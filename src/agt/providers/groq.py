"""Groq provider adapter hidden behind the internal LLMProvider protocol."""

from __future__ import annotations

from typing import Any, cast

from agt.config import RuntimeConfig
from agt.providers.xai import HTTPXAIModel, TokenPricing, XAIProvider

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(XAIProvider):
    """Adapter around the Groq chat-completions API via HTTPX.

    Groq exposes an OpenAI-compatible ``/chat/completions`` endpoint, so the
    implementation reuses ``_HTTPXAIModel`` with a different ``_base_url``.
    Pricing defaults to zero because Groq's free tier has no per-token cost;
    callers that want cost tracking can supply a ``TokenPricing`` instance.
    """

    def __init__(
        self,
        runtime: RuntimeConfig,
        api_key: str,
        pricing: TokenPricing | None = None,
        model_factory: Any | None = None,
        model: Any | None = None,
    ) -> None:
        super().__init__(
            runtime=runtime,
            api_key=api_key,
            pricing=pricing
            or TokenPricing(
                input_per_1k_tokens_usd=0.0,
                output_per_1k_tokens_usd=0.0,
            ),
            model_factory=model_factory or _groq_model_factory,
            model=model,
        )


def _groq_model_factory(**kwargs: Any) -> HTTPXAIModel:
    return HTTPXAIModel(
        api_key=cast(str, kwargs["api_key"]),
        model=cast(str, kwargs["model"]),
        timeout=cast(int, kwargs["timeout"]),
        max_retries=cast(int, kwargs["max_retries"]),
        temperature=cast(float, kwargs["temperature"]),
        tools=[],
        _base_url=_GROQ_BASE_URL,
    )
