"""Internal provider protocol used to decouple workflow code from vendor SDKs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol


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
