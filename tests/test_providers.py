from __future__ import annotations

from dataclasses import dataclass

import pytest

from agt.config import RuntimeConfig, Settings
from agt.providers import router
from agt.providers import xai as xai_module
from agt.providers.router import build_provider
from agt.providers.xai import XAIProvider


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


def test_router_rejects_unimplemented_provider() -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_LLM_PROVIDER": "openai",
    })

    with pytest.raises(RuntimeError):
        build_provider(settings)


def test_router_builds_xai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings.model_validate({
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
