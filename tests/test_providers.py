from __future__ import annotations

from dataclasses import dataclass

import pytest

from agt.config import RuntimeConfig, Settings
from agt.providers import router
from agt.providers import xai as xai_module
from agt.providers.anthropic import AnthropicProvider
from agt.providers.groq import GroqProvider
from agt.providers.openai import OpenAIProvider
from agt.providers.openai_compatible import OpenAICompatibleProvider
from agt.providers.protocol import ProviderRateLimitError
from agt.providers.router import build_provider
from agt.providers.xai import XAIProvider


def _settings_from(data: dict[str, object]) -> Settings:
    return Settings(_env_file=None, **data)  # pyright: ignore[reportCallIssue]


@dataclass
class FakeResponse:
    content: str


class FakeModel:
    def __init__(self) -> None:
        self.bound_tools = None

    def invoke(self, prompt: str) -> FakeResponse:
        return FakeResponse(content=f"sync:{prompt}")

    async def ainvoke(self, prompt: str) -> FakeResponse:
        return FakeResponse(content=f"async:{prompt}")

    def bind_tools(self, tools: list[object]) -> FakeModel:
        self.bound_tools = tools
        return self


class _Guardrails:
    def acquire(self, service: str, thread_id: str) -> None:
        _ = service
        _ = thread_id

    def record_cost(self, thread_id: str, amount_usd: float) -> None:
        _ = thread_id
        _ = amount_usd


def _fake_get_guardrails() -> _Guardrails:
    return _Guardrails()


def _fake_thread_id() -> str:
    return "thread-1"


def test_xai_provider_invoke_and_ainvoke() -> None:
    xai_module.get_guardrails = _fake_get_guardrails  # type: ignore[method-assign]
    xai_module.current_thread_id = _fake_thread_id  # type: ignore[method-assign]

    provider = XAIProvider(
        runtime=RuntimeConfig(),
        api_key="x",
        model=FakeModel(),
    )

    assert provider.invoke("hello") == "sync:hello"


@pytest.mark.anyio
async def test_xai_provider_ainvoke() -> None:
    xai_module.get_guardrails = _fake_get_guardrails  # type: ignore[method-assign]
    xai_module.current_thread_id = _fake_thread_id  # type: ignore[method-assign]

    provider = XAIProvider(
        runtime=RuntimeConfig(),
        api_key="x",
        model=FakeModel(),
    )

    assert await provider.ainvoke("hello") == "async:hello"


def test_router_rejects_groq_without_key() -> None:
    settings = _settings_from({
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "groq",
    })

    with pytest.raises(RuntimeError, match="groq") as exc:
        build_provider(settings)

    text = str(exc.value)
    assert "AGT_GROQ_API_KEY" in text
    assert "GROQ_API_KEY" in text


def test_router_builds_groq_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_from({
        "AGT_GROQ_API_KEY": "groq-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "groq",
    })

    class _Built:
        pass

    built = _Built()

    def _build_stub(
        runtime: RuntimeConfig,
        api_key: str,
    ) -> _Built:
        _ = runtime
        _ = api_key
        return built

    monkeypatch.setattr(router, "GroqProvider", _build_stub)

    assert build_provider(settings) is built


def test_router_builds_xai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_from({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "xai",
    })

    class _Built:
        pass

    built = _Built()

    def _build_stub(
        runtime: RuntimeConfig,
        api_key: str,
        pricing: object,
    ) -> _Built:
        _ = runtime
        _ = api_key
        _ = pricing
        return built

    monkeypatch.setattr(router, "XAIProvider", _build_stub)

    assert build_provider(settings) is built


def test_router_builds_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_from({
        "AGT_OPENAI_API_KEY": "openai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "openai",
    })

    class _Built:
        pass

    built = _Built()

    def _build_stub(
        runtime: RuntimeConfig,
        api_key: str,
    ) -> _Built:
        _ = runtime
        _ = api_key
        return built

    monkeypatch.setattr(router, "OpenAIProvider", _build_stub)

    assert build_provider(settings) is built


def test_router_builds_anthropic_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_from({
        "AGT_ANTHROPIC_API_KEY": "anthropic-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "anthropic",
    })

    class _Built:
        pass

    built = _Built()

    def _build_stub(
        runtime: RuntimeConfig,
        api_key: str,
    ) -> _Built:
        _ = runtime
        _ = api_key
        return built

    monkeypatch.setattr(router, "AnthropicProvider", _build_stub)

    assert build_provider(settings) is built


def test_router_missing_key_error_names_provider_and_env_vars() -> None:
    settings = _settings_from({
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "anthropic",
    })

    with pytest.raises(RuntimeError, match="anthropic") as exc:
        build_provider(settings)

    text = str(exc.value)
    assert "AGT_ANTHROPIC_API_KEY" in text
    assert "ANTHROPIC_API_KEY" in text


def test_router_fails_over_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_from({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "xai",
        "AGT_LLM_FALLBACK_PROVIDER": "openai",
    })

    class _Primary:
        def invoke(self, prompt: str) -> str:
            _ = prompt
            raise ProviderRateLimitError("rate limited")

        async def ainvoke(self, prompt: str) -> str:
            _ = prompt
            raise ProviderRateLimitError("rate limited")

        def bind_tools(self, tools: list[object]) -> _Primary:
            _ = tools
            return self

    class _Fallback:
        def invoke(self, prompt: str) -> str:
            return f"fallback:{prompt}"

        async def ainvoke(self, prompt: str) -> str:
            return f"fallback:{prompt}"

        def bind_tools(self, tools: list[object]) -> _Fallback:
            _ = tools
            return self

    _ = monkeypatch
    original_xai = router.get_provider_builder("xai")
    original_openai = router.get_provider_builder("openai")
    router.register_provider_builder("xai", lambda _settings: _Primary())
    router.register_provider_builder("openai", lambda _settings: _Fallback())
    try:
        provider = build_provider(settings)
        assert provider.invoke("hello") == "fallback:hello"
    finally:
        if original_xai is not None:
            router.register_provider_builder("xai", original_xai)
        if original_openai is None:
            router.unregister_provider_builder("openai")
        else:
            router.register_provider_builder("openai", original_openai)


def test_router_skips_failover_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_from({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "xai",
        "AGT_LLM_FALLBACK_PROVIDER": "openai",
        "AGT_LLM_FAILOVER_ON_RATE_LIMIT": False,
    })

    class _Primary:
        def invoke(self, prompt: str) -> str:
            _ = prompt
            raise ProviderRateLimitError("rate limited")

        async def ainvoke(self, prompt: str) -> str:
            _ = prompt
            raise ProviderRateLimitError("rate limited")

        def bind_tools(self, tools: list[object]) -> _Primary:
            _ = tools
            return self

    class _Fallback:
        def invoke(self, prompt: str) -> str:
            return f"fallback:{prompt}"

        async def ainvoke(self, prompt: str) -> str:
            return f"fallback:{prompt}"

        def bind_tools(self, tools: list[object]) -> _Fallback:
            _ = tools
            return self

    _ = monkeypatch
    original_xai = router.get_provider_builder("xai")
    original_openai = router.get_provider_builder("openai")
    router.register_provider_builder("xai", lambda _settings: _Primary())
    router.register_provider_builder("openai", lambda _settings: _Fallback())
    try:
        provider = build_provider(settings)
        with pytest.raises(ProviderRateLimitError):
            provider.invoke("hello")
    finally:
        if original_xai is not None:
            router.register_provider_builder("xai", original_xai)
        if original_openai is None:
            router.unregister_provider_builder("openai")
        else:
            router.register_provider_builder("openai", original_openai)


def test_openai_provider_bind_tools_preserves_provider_type() -> None:
    provider = OpenAIProvider(
        runtime=RuntimeConfig(provider="openai", model_name="gpt-5.4"),
        api_key="openai-secret",
        model=FakeModel(),
    )

    bound = provider.bind_tools([{"type": "function", "name": "lookup"}])

    assert isinstance(bound, OpenAIProvider)


def test_anthropic_provider_bind_tools_preserves_provider_type() -> None:
    provider = AnthropicProvider(
        runtime=RuntimeConfig(provider="anthropic", model_name="claude-opus-4-6"),
        api_key="anthropic-secret",
        model=FakeModel(),
    )

    bound = provider.bind_tools([{"name": "lookup", "input_schema": {"type": "object"}}])

    assert isinstance(bound, AnthropicProvider)


def test_groq_provider_bind_tools_preserves_provider_type() -> None:
    provider = GroqProvider(
        runtime=RuntimeConfig(provider="groq", model_name="llama-3.3-70b-versatile"),
        api_key="groq-secret",
        model=FakeModel(),
    )

    bound = provider.bind_tools([{"type": "function", "name": "lookup"}])

    assert isinstance(bound, GroqProvider)


# --- SCI-0601 / SCI-0602 provider tests ---


def test_router_builds_openai_compatible_provider() -> None:
    settings = _settings_from({
        "AGT_LLM_PROVIDER": "openai-compatible",
        "AGT_LLM_BASE_URL": "https://api.deepseek.com/v1",
        "AGT_LLM_API_KEY": "ds-secret",
        "AGT_LLM_MODEL": "deepseek-chat",
    })

    provider = build_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)


def test_router_openai_compatible_requires_base_url() -> None:
    settings = _settings_from({
        "AGT_LLM_PROVIDER": "openai-compatible",
    })

    with pytest.raises(RuntimeError, match="AGT_LLM_BASE_URL"):
        build_provider(settings)


def test_router_builds_ollama_provider() -> None:
    settings = _settings_from({
        "AGT_LLM_PROVIDER": "ollama",
    })

    provider = build_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)


def test_router_auto_detects_openai_compatible_when_base_url_set() -> None:
    settings = _settings_from({
        "AGT_LLM_BASE_URL": "https://api.deepseek.com/v1",
    })

    assert settings.resolved_llm_provider == "openai-compatible"


def test_ollama_uses_custom_base_url_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    class _CapturingProvider(OpenAICompatibleProvider):
        def __init__(
            self, runtime: RuntimeConfig, api_key: str, base_url: str, **kwargs: object
        ) -> None:
            captured.append(base_url)
            super().__init__(runtime=runtime, api_key=api_key, base_url=base_url, model=FakeModel())

    monkeypatch.setattr(router, "OpenAICompatibleProvider", _CapturingProvider)

    settings = _settings_from({
        "AGT_LLM_PROVIDER": "ollama",
        "AGT_LLM_BASE_URL": "http://custom:11434/v1",
    })
    build_provider(settings)

    assert captured == ["http://custom:11434/v1"]
