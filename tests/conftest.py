from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "provider_snapshot: snapshot tests that pin provider normalization behavior",
    )
    config.addinivalue_line(
        "markers",
        "live_api: tests that exercise real network endpoints (skipped in CI by default)",
    )
    config.addinivalue_line(
        "markers",
        "regression_gate: tests that verify the benchmark regression threshold is structurally correct",
    )


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
