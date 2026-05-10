"""Anthropic provider adapter hidden behind the internal LLMProvider protocol."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

import httpx
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agt.config import RuntimeConfig
from agt.providers.protocol import (
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from agt.providers.xai import TokenPricing, XAIProvider

ModelFactory = Callable[..., object]
HTTP_RATE_LIMIT_STATUS = 429
_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_MAX_TOKENS = 1024


def _serialize_tool(tool: object) -> dict[str, object] | None:
    if isinstance(tool, dict):
        return cast(dict[str, object], tool)

    model_dump = getattr(tool, "model_dump", None)
    if callable(model_dump):
        serialized: object = model_dump()
        if isinstance(serialized, dict):
            return cast(dict[str, object], serialized)

    dict_method = getattr(tool, "dict", None)
    if callable(dict_method):
        serialized = dict_method()
        if isinstance(serialized, dict):
            return cast(dict[str, object], serialized)

    return None


def _serialize_tools(tools: Sequence[object]) -> list[dict[str, object]]:
    serialized_tools: list[dict[str, object]] = []
    for tool in tools:
        serialized = _serialize_tool(tool)
        if serialized is not None:
            serialized_tools.append(serialized)
    return serialized_tools


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


@dataclass(slots=True)
class _ModelResponse:
    content: str
    usage_metadata: dict[str, int]


@dataclass(slots=True)
class _HTTPAnthropicMessagesModel:
    """Minimal Anthropic Messages API client."""

    api_key: str
    model: str
    timeout: int
    max_retries: int
    temperature: float
    tools: list[dict[str, object]]
    max_tokens: int = _DEFAULT_MAX_TOKENS

    _base_url: str = "https://api.anthropic.com"

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }

    def _payload(self, prompt: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        if self.tools:
            payload["tools"] = self.tools
        return payload

    @staticmethod
    def _parse_response(payload: dict[str, object]) -> _ModelResponse:
        content_blocks = payload.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            raise ProviderResponseError("Anthropic response missing content blocks")

        parts: list[str] = []
        content_block_items = cast(list[object], content_blocks)
        for block_obj in content_block_items:
            if not isinstance(block_obj, dict):
                continue
            block = cast(dict[str, object], block_obj)
            if block.get("type") != "text":
                continue
            text = block.get("text")
            if isinstance(text, str) and text:
                parts.append(text)

        content = "\n".join(parts).strip()
        if not content:
            raise ProviderResponseError("Anthropic response missing text output")

        usage_data = payload.get("usage")
        usage_mapping = cast(dict[str, object], usage_data) if isinstance(usage_data, dict) else {}
        return _ModelResponse(
            content=content,
            usage_metadata={
                "input_tokens": _int_value(usage_mapping.get("input_tokens", 0)),
                "output_tokens": _int_value(usage_mapping.get("output_tokens", 0)),
            },
        )

    def invoke(self, prompt: str) -> _ModelResponse:
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self.max_retries + 1),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                retry=retry_if_exception_type((
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.HTTPStatusError,
                )),
                reraise=True,
            ):
                with attempt, httpx.Client(timeout=self.timeout, base_url=self._base_url) as client:
                    response = client.post(
                        "/v1/messages",
                        headers=self._headers(),
                        json=self._payload(prompt),
                    )
                    response.raise_for_status()
                    data: object = response.json()
                    if not isinstance(data, dict):
                        raise ProviderResponseError(
                            "Anthropic response payload must be a JSON object"
                        )
                    return self._parse_response(cast(dict[str, object], data))
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Anthropic request timed out") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTP_RATE_LIMIT_STATUS:
                raise ProviderRateLimitError("Anthropic rate limited") from exc
            raise ProviderResponseError(
                f"Anthropic returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderTimeoutError("Anthropic network request failed") from exc

        raise ProviderResponseError("Anthropic request failed after retries")

    async def ainvoke(self, prompt: str) -> _ModelResponse:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_retries + 1),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                retry=retry_if_exception_type((
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.HTTPStatusError,
                )),
                reraise=True,
            ):
                with attempt:
                    async with httpx.AsyncClient(
                        timeout=self.timeout, base_url=self._base_url
                    ) as client:
                        response = await client.post(
                            "/v1/messages",
                            headers=self._headers(),
                            json=self._payload(prompt),
                        )
                        response.raise_for_status()
                        data: object = response.json()
                        if not isinstance(data, dict):
                            raise ProviderResponseError(
                                "Anthropic response payload must be a JSON object"
                            )
                        return self._parse_response(cast(dict[str, object], data))
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Anthropic request timed out") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTP_RATE_LIMIT_STATUS:
                raise ProviderRateLimitError("Anthropic rate limited") from exc
            raise ProviderResponseError(
                f"Anthropic returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderTimeoutError("Anthropic network request failed") from exc

        raise ProviderResponseError("Anthropic request failed after retries")

    def bind_tools(self, tools: Sequence[object]) -> _HTTPAnthropicMessagesModel:
        return _HTTPAnthropicMessagesModel(
            api_key=self.api_key,
            model=self.model,
            timeout=self.timeout,
            max_retries=self.max_retries,
            temperature=self.temperature,
            tools=_serialize_tools(tools),
            max_tokens=self.max_tokens,
        )


class AnthropicProvider(XAIProvider):
    """Adapter around the Anthropic Messages API via HTTPX."""

    def __init__(
        self,
        runtime: RuntimeConfig,
        api_key: str,
        pricing: TokenPricing | None = None,
        model_factory: ModelFactory | None = None,
        model: object | None = None,
    ) -> None:
        super().__init__(
            runtime=runtime,
            api_key=api_key,
            pricing=pricing
            or TokenPricing(input_per_1k_tokens_usd=0.0, output_per_1k_tokens_usd=0.0),
            model_factory=model_factory or self._default_model_factory,
            model=model,
        )

    @staticmethod
    def _default_model_factory(**kwargs: object) -> object:
        return _HTTPAnthropicMessagesModel(
            api_key=cast(str, kwargs["api_key"]),
            model=cast(str, kwargs["model"]),
            timeout=cast(int, kwargs["timeout"]),
            max_retries=cast(int, kwargs["max_retries"]),
            temperature=cast(float, kwargs["temperature"]),
            tools=[],
        )
