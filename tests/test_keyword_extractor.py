from __future__ import annotations

# ruff: noqa: I001, PLW0108

import pytest

from agt.tools import keyword_extractor


def test_extract_keywords_uses_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeModel:
        def extract_keywords(self, query: str, **kwargs: object) -> list[tuple[str, float]]:
            _ = query
            _ = kwargs
            return [("sports nutrition", 0.9), ("athlete diet", 0.8)]

    monkeypatch.setattr(keyword_extractor, "_load_model", lambda: _FakeModel())
    values = keyword_extractor.extract_keywords("nutrition in sport", top_n=2)
    assert values == ["sports nutrition", "athlete diet"]


def test_extract_keywords_handles_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise() -> object:
        raise RuntimeError()

    monkeypatch.setattr(keyword_extractor, "_load_model", _raise)
    assert keyword_extractor.extract_keywords("x") == []


def test_extract_keywords_empty_query() -> None:
    assert keyword_extractor.extract_keywords("   ") == []
