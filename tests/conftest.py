from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_unmodeled_provider_env(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep settings tests deterministic under strict extra='forbid'."""

    for name in (
        "OPENAI_API_KEY",
        "AGT_OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AGT_ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "AGT_GROQ_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
