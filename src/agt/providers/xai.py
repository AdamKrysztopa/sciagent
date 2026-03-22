"""xAI provider adapter hidden behind the internal LLMProvider protocol."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast

try:
    from langchain_xai import ChatXAI
except ImportError:  # pragma: no cover - handled during provider construction
    ChatXAI = None

from agt.config import RuntimeConfig
from agt.providers.protocol import LLMProvider

ModelFactory = Callable[..., Any]
ModelContent = str | list[object] | object


class XAIProvider(LLMProvider):
    """Adapter around langchain-xai ChatXAI."""

    def __init__(
        self,
        runtime: RuntimeConfig,
        api_key: str,
        model_factory: ModelFactory | None = None,
        model: Any | None = None,
    ) -> None:
        self._runtime = runtime
        self._api_key = api_key
        if model is not None:
            self._model = model
            return

        factory = model_factory or self._default_model_factory
        self._model = factory(
            api_key=api_key,
            model=runtime.model_name,
            timeout=runtime.timeout_seconds,
            max_retries=runtime.retries,
            temperature=runtime.temperature,
        )

    @staticmethod
    def _default_model_factory(**kwargs: Any) -> Any:
        if ChatXAI is None:
            raise RuntimeError("langchain-xai is required for xAI provider support")

        return ChatXAI(**kwargs)

    @staticmethod
    def _extract_content(response: Any) -> str:
        content: ModelContent = cast(ModelContent, getattr(response, "content", response))
        if isinstance(content, list):
            parts = cast(list[object], content)
            return "\n".join(str(part) for part in parts)
        return str(content)

    def invoke(self, prompt: str) -> str:
        return self._extract_content(self._model.invoke(prompt))

    async def ainvoke(self, prompt: str) -> str:
        return self._extract_content(await self._model.ainvoke(prompt))

    def bind_tools(self, tools: Sequence[Any]) -> LLMProvider:
        if not hasattr(self._model, "bind_tools"):
            return self
        bound_model = self._model.bind_tools(tools)
        return cast(
            LLMProvider,
            XAIProvider(
                runtime=self._runtime,
                api_key=self._api_key,
                model=bound_model,
            ),
        )
