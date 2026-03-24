"""Internal provider protocol used to decouple workflow code from vendor SDKs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """Base class for provider invocation failures."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call times out."""


class ProviderRateLimitError(ProviderError):
    """Raised when a provider responds with rate limiting."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an invalid or non-retryable response."""


class LLMProvider(Protocol):
    """Provider contract for sync/async invocation and optional tool binding."""

    def invoke(self, prompt: str) -> str:
        """Invoke the model synchronously and return text content."""
        ...

    async def ainvoke(self, prompt: str) -> str:
        """Invoke the model asynchronously and return text content."""
        ...

    def bind_tools(self, tools: Sequence[Any]) -> LLMProvider:
        """Return a provider instance with tools bound for function-calling."""
        ...
