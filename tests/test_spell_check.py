from __future__ import annotations

from agt.tools.spell_check import correct_query


def test_correct_query_fixes_obvious_typo() -> None:
    result = correct_query("wrod papers")
    assert "word" in result


def test_correct_query_preserves_domain_terms() -> None:
    result = correct_query("best RAG techniques")
    assert "RAG" in result


def test_correct_query_preserves_arxiv() -> None:
    result = correct_query("arxiv preprints")
    assert "arxiv" in result


def test_correct_query_preserves_llm() -> None:
    result = correct_query("LLM alignment")
    assert "LLM" in result


def test_correct_query_empty() -> None:
    assert correct_query("   ") == "   "


def test_correct_query_no_changes_for_clean_input() -> None:
    assert correct_query("attention mechanism") == "attention mechanism"


def test_correct_query_preserves_short_tokens() -> None:
    result = correct_query("in AI systems")
    assert "AI" in result


def test_correct_query_returns_string() -> None:
    assert isinstance(correct_query("musg be eliminated"), str)
