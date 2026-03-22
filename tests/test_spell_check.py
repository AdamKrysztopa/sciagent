from __future__ import annotations

import sys
import types

import pytest

from agt.tools.spell_check import correct_query


def test_correct_query_returns_input_when_package_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "spellchecker", raising=False)
    assert correct_query("trandign papers") in {"trandign papers", "trending papers"}


def test_correct_query_preserves_domain_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("spellchecker")

    class _FakeSpellChecker:
        def __init__(self, distance: int) -> None:
            _ = distance

        def correction(self, token: str) -> str:
            if token.lower() == "trandign":
                return "trending"
            if token.lower() == "rag":
                return "rag"
            return token

    setattr(fake_module, "SpellChecker", _FakeSpellChecker)
    monkeypatch.setitem(sys.modules, "spellchecker", fake_module)

    corrected = correct_query("trandign RAG")
    assert "trending" in corrected.lower()
    assert "RAG" in corrected


def test_correct_query_empty() -> None:
    assert correct_query("   ") == "   "
