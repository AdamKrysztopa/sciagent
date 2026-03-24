from __future__ import annotations

import pytest

from agt.guardrails import Guardrails, RateLimitExceededError, WorkflowCostExceededError


def test_guardrails_rate_limit_per_thread() -> None:
    guardrails = Guardrails(
        semantic_scholar_rate_per_minute=1,
        zotero_rate_per_minute=1,
        llm_rate_per_minute=1,
        workflow_max_cost_usd=0.5,
    )

    guardrails.acquire("semantic_scholar", "thread-a")
    with pytest.raises(RateLimitExceededError):
        guardrails.acquire("semantic_scholar", "thread-a")

    # Different thread keeps an independent bucket.
    guardrails.acquire("semantic_scholar", "thread-b")


def test_guardrails_cost_limit() -> None:
    guardrails = Guardrails(
        semantic_scholar_rate_per_minute=100,
        zotero_rate_per_minute=60,
        llm_rate_per_minute=100,
        workflow_max_cost_usd=0.5,
    )

    guardrails.record_cost("thread-a", 0.4)
    with pytest.raises(WorkflowCostExceededError):
        guardrails.record_cost("thread-a", 0.2)


@pytest.mark.anyio
async def test_wait_for_token_times_out() -> None:
    guardrails = Guardrails(
        semantic_scholar_rate_per_minute=1,
        zotero_rate_per_minute=1,
        llm_rate_per_minute=1,
        workflow_max_cost_usd=0.5,
    )
    guardrails.acquire("semantic_scholar", "thread-a")
    ok = await guardrails.wait_for_token(
        "semantic_scholar",
        "thread-a",
        timeout_seconds=0.01,
    )
    assert ok is False


@pytest.mark.anyio
async def test_wait_for_token_succeeds_immediately_when_available() -> None:
    guardrails = Guardrails(
        semantic_scholar_rate_per_minute=100,
        zotero_rate_per_minute=1,
        llm_rate_per_minute=1,
        workflow_max_cost_usd=0.5,
    )
    ok = await guardrails.wait_for_token("semantic_scholar", "thread-a", timeout_seconds=0.2)
    assert ok is True
