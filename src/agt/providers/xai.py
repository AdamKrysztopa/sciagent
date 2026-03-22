"""xAI provider adapter hidden behind the internal LLMProvider protocol."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

import httpx
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agt.config import RuntimeConfig
from agt.guardrails import current_thread_id, get_guardrails
from agt.providers.protocol import (
    LLMProvider,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)

ModelFactory = Callable[..., Any]
ModelContent = str | list[object] | object
HTTP_RATE_LIMIT_STATUS = 429


@dataclass(slots=True)
class _ModelResponse:
    content: str
    usage_metadata: dict[str, int]


@dataclass(slots=True)
class _HTTPXAIModel:
    """Minimal OpenAI-compatible chat-completions client for xAI."""

    api_key: str
    model: str
    timeout: int
    max_retries: int
    temperature: float
    tools: list[dict[str, Any]]

    _base_url: str = "https://api.x.ai/v1"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        if self.tools:
            payload["tools"] = self.tools
        return payload

    @staticmethod
    def _parse_response(payload: dict[str, Any]) -> _ModelResponse:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("xAI response missing choices")

        first_choice = cast(object, choices[0])
        if not isinstance(first_choice, dict):
            raise RuntimeError("xAI response choice is malformed")
        first_choice_mapping = cast(dict[str, Any], first_choice)

        message = first_choice_mapping.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("xAI response missing message")
        message_mapping = cast(dict[str, Any], message)

        raw_content = message_mapping.get("content", "")
        content = str(raw_content)

        usage_data = payload.get("usage")
        usage_mapping = cast(dict[str, Any], usage_data) if isinstance(usage_data, dict) else {}
        prompt_tokens = int(usage_mapping.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage_mapping.get("completion_tokens", 0) or 0)

        return _ModelResponse(
            content=content,
            usage_metadata={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
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
                        "/chat/completions",
                        headers=self._headers(),
                        json=self._payload(prompt),
                    )
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ProviderResponseError("xAI response payload must be a JSON object")
                    return self._parse_response(cast(dict[str, Any], data))
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("xAI request timed out") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTP_RATE_LIMIT_STATUS:
                raise ProviderRateLimitError("xAI rate limited") from exc
            raise ProviderResponseError(f"xAI returned HTTP {exc.response.status_code}") from exc
        except httpx.NetworkError as exc:
            raise ProviderTimeoutError("xAI network request failed") from exc

        raise ProviderResponseError("xAI request failed after retries")

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
                            "/chat/completions",
                            headers=self._headers(),
                            json=self._payload(prompt),
                        )
                        response.raise_for_status()
                        data = response.json()
                        if not isinstance(data, dict):
                            raise ProviderResponseError(
                                "xAI response payload must be a JSON object"
                            )
                        return self._parse_response(cast(dict[str, Any], data))
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("xAI request timed out") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTP_RATE_LIMIT_STATUS:
                raise ProviderRateLimitError("xAI rate limited") from exc
            raise ProviderResponseError(f"xAI returned HTTP {exc.response.status_code}") from exc
        except httpx.NetworkError as exc:
            raise ProviderTimeoutError("xAI network request failed") from exc

        raise ProviderResponseError("xAI request failed after retries")

    def bind_tools(self, tools: Sequence[Any]) -> _HTTPXAIModel:
        serialized_tools: list[dict[str, Any]] = []
        for tool in tools:
            if isinstance(tool, dict):
                serialized_tools.append(cast(dict[str, Any], tool))
                continue
            if hasattr(tool, "model_dump"):
                serialized = tool.model_dump()
                if isinstance(serialized, dict):
                    serialized_tools.append(cast(dict[str, Any], serialized))
                continue
            if hasattr(tool, "dict"):
                serialized = tool.dict()
                if isinstance(serialized, dict):
                    serialized_tools.append(cast(dict[str, Any], serialized))

        return _HTTPXAIModel(
            api_key=self.api_key,
            model=self.model,
            timeout=self.timeout,
            max_retries=self.max_retries,
            temperature=self.temperature,
            tools=serialized_tools,
        )


@dataclass(frozen=True, slots=True)
class TokenPricing:
    """Cost rates used by workflow cost guardrails."""

    input_per_1k_tokens_usd: float = 0.005
    output_per_1k_tokens_usd: float = 0.015


class XAIProvider(LLMProvider):
    """Adapter around xAI chat completions via HTTPX."""

    def __init__(
        self,
        runtime: RuntimeConfig,
        api_key: str,
        pricing: TokenPricing | None = None,
        model_factory: ModelFactory | None = None,
        model: Any | None = None,
    ) -> None:
        self._runtime = runtime
        self._api_key = api_key
        self._pricing = pricing or TokenPricing()
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
        return _HTTPXAIModel(
            api_key=cast(str, kwargs["api_key"]),
            model=cast(str, kwargs["model"]),
            timeout=cast(int, kwargs["timeout"]),
            max_retries=cast(int, kwargs["max_retries"]),
            temperature=cast(float, kwargs["temperature"]),
            tools=[],
        )

    @staticmethod
    def _extract_content(response: Any) -> str:
        content: ModelContent = cast(ModelContent, getattr(response, "content", response))
        if isinstance(content, list):
            parts = cast(list[object], content)
            return "\n".join(str(part) for part in parts)
        return str(content)

    @staticmethod
    def _extract_token_usage(response: Any) -> tuple[int, int]:
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            usage_mapping = cast(dict[str, Any], usage)
            input_tokens = int(usage_mapping.get("input_tokens", 0) or 0)
            output_tokens = int(usage_mapping.get("output_tokens", 0) or 0)
            return input_tokens, output_tokens

        response_metadata = getattr(response, "response_metadata", None)
        if isinstance(response_metadata, dict):
            metadata_mapping = cast(dict[str, Any], response_metadata)
            token_usage = metadata_mapping.get("token_usage")
            if isinstance(token_usage, dict):
                token_usage_mapping = cast(dict[str, Any], token_usage)
                input_tokens = int(token_usage_mapping.get("prompt_tokens", 0) or 0)
                output_tokens = int(token_usage_mapping.get("completion_tokens", 0) or 0)
                return input_tokens, output_tokens

        return 0, 0

    def _record_usage_cost(self, response: Any) -> None:
        input_tokens, output_tokens = self._extract_token_usage(response)
        if input_tokens == 0 and output_tokens == 0:
            return

        input_cost = (input_tokens / 1000.0) * self._pricing.input_per_1k_tokens_usd
        output_cost = (output_tokens / 1000.0) * self._pricing.output_per_1k_tokens_usd
        get_guardrails().record_cost(current_thread_id(), input_cost + output_cost)

    def invoke(self, prompt: str) -> str:
        get_guardrails().acquire("llm", current_thread_id())
        response = self._model.invoke(prompt)
        self._record_usage_cost(response)
        return self._extract_content(response)

    async def ainvoke(self, prompt: str) -> str:
        get_guardrails().acquire("llm", current_thread_id())
        response = await self._model.ainvoke(prompt)
        self._record_usage_cost(response)
        return self._extract_content(response)

    def bind_tools(self, tools: Sequence[Any]) -> LLMProvider:
        if not hasattr(self._model, "bind_tools"):
            return self
        bound_model = self._model.bind_tools(tools)
        return cast(
            LLMProvider,
            XAIProvider(
                runtime=self._runtime,
                api_key=self._api_key,
                pricing=self._pricing,
                model=bound_model,
            ),
        )
