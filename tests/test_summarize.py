from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pytest

from agt.models import NormalizedPaper
from agt.tools.summarize import deterministic_summary, summarize_papers

MAX_SENTENCES = 4


@dataclass
class _FakeProvider:
    response: str

    def invoke(self, prompt: str) -> str:
        _ = prompt
        return self.response

    async def ainvoke(self, prompt: str) -> str:
        _ = prompt
        return self.response

    def bind_tools(self, tools: Sequence[Any]) -> _FakeProvider:
        _ = tools
        return self


def _sentence_count(text: str) -> int:
    return text.count(".") + text.count("!") + text.count("?")


def test_deterministic_summary_bounded() -> None:
    paper = NormalizedPaper(
        title="Paper",
        year=2026,
        authors=["A", "B"],
        abstract="First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence.",
        open_access=True,
    )

    summary = deterministic_summary(paper, max_sentences=MAX_SENTENCES)

    assert _sentence_count(summary) <= MAX_SENTENCES


@pytest.mark.anyio
async def test_summarize_papers_uses_llm_but_clamps() -> None:
    paper = NormalizedPaper(title="Paper", abstract="alpha")
    provider = _FakeProvider(response=("S1. S2. S3. S4. S5."))

    summarized = await summarize_papers(
        [paper],
        provider=provider,
        use_llm=True,
        max_sentences=MAX_SENTENCES,
    )

    assert summarized[0].summary is not None
    assert _sentence_count(summarized[0].summary or "") <= MAX_SENTENCES
