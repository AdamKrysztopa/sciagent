from __future__ import annotations

import json
from typing import Any

import pytest

from agt.models import NormalizedPaper
from agt.tools.query_rewriter import (
    RewrittenQuery,
    ValidationResult,
    extract_json,
    rewrite_query,
    validate_results,
)

# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


def test_extract_json_parses_plain_json() -> None:
    raw = '{"search_query": "sports nutrition", "keywords": ["sports"]}'
    result = extract_json(raw)
    assert result is not None
    assert result["search_query"] == "sports nutrition"


def test_extract_json_parses_markdown_wrapped() -> None:
    raw = '```json\n{"search_query": "deep RL"}\n```'
    result = extract_json(raw)
    assert result is not None
    assert result["search_query"] == "deep RL"


def test_extract_json_parses_embedded_brace() -> None:
    raw = 'Here is the result: {"is_relevant": false, "reason": "off-topic"}'
    result = extract_json(raw)
    assert result is not None
    assert result["is_relevant"] is False


def test_extract_json_returns_none_for_garbage() -> None:
    assert extract_json("not json at all") is None


# ---------------------------------------------------------------------------
# rewrite_query
# ---------------------------------------------------------------------------


class _FakeProvider:
    """Minimal LLMProvider stub returning canned responses."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    def invoke(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response

    async def ainvoke(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response

    def bind_tools(self, tools: Any) -> _FakeProvider:
        return self


@pytest.mark.anyio
async def test_rewrite_query_extracts_search_query() -> None:
    llm_response = json.dumps({
        "search_query": "sports nutrition",
        "keywords": ["sports", "nutrition"],
        "topic": "nutrition in athletic performance",
    })
    provider = _FakeProvider(llm_response)
    result = await rewrite_query(
        "Most recent papers in nutrition in sport not older than 2024",
        provider,
    )
    assert isinstance(result, RewrittenQuery)
    assert result.search_query == "sports nutrition"
    assert "sports" in result.keywords
    assert result.topic == "nutrition in athletic performance"


@pytest.mark.anyio
async def test_rewrite_query_falls_back_on_bad_json() -> None:
    provider = _FakeProvider("I don't know how to answer that")
    result = await rewrite_query("some query", provider)
    assert result.search_query == "some query"


# ---------------------------------------------------------------------------
# validate_results
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_validate_results_accepts_relevant() -> None:
    llm_response = json.dumps({
        "is_relevant": True,
        "reason": "all papers are about sports nutrition",
        "suggested_query": None,
    })
    provider = _FakeProvider(llm_response)
    papers = [
        NormalizedPaper(title="Sports Nutrition Review", year=2024),
        NormalizedPaper(title="Dietary Intake in Athletes", year=2024),
    ]
    result = await validate_results("nutrition in sport", "sports nutrition", papers, provider)
    assert isinstance(result, ValidationResult)
    assert result.is_relevant is True
    assert result.suggested_query is None


@pytest.mark.anyio
async def test_validate_results_rejects_irrelevant_with_suggestion() -> None:
    llm_response = json.dumps({
        "is_relevant": False,
        "reason": "papers are about AI, not nutrition",
        "suggested_query": "sports nutrition diet athletes",
    })
    provider = _FakeProvider(llm_response)
    papers = [
        NormalizedPaper(title="AI in Nursing Care", year=2024),
        NormalizedPaper(title="Corporate Governance", year=2024),
    ]
    result = await validate_results("nutrition in sport", "sports nutrition", papers, provider)
    assert result.is_relevant is False
    assert result.suggested_query == "sports nutrition diet athletes"


@pytest.mark.anyio
async def test_validate_results_handles_empty_papers() -> None:
    provider = _FakeProvider("")
    result = await validate_results("query", "topic", [], provider)
    assert result.is_relevant is False


@pytest.mark.anyio
async def test_validate_results_defaults_relevant_on_bad_json() -> None:
    provider = _FakeProvider("unparseable response")
    papers = [NormalizedPaper(title="Some paper", year=2024)]
    result = await validate_results("query", "topic", papers, provider)
    assert result.is_relevant is True  # conservative default
