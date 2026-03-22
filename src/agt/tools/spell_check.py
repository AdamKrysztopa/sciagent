"""Optional query spell correction for retrieval pre-processing."""

# ruff: noqa: PLC0415, PLR2004
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_DOMAIN_TERMS = {
    "arxiv",
    "pubmed",
    "openalex",
    "crossref",
    "europepmc",
    "europe",
    "pmc",
    "rag",
    "timeseries",
    "transformer",
    "retrieval",
    "augmented",
    "langgraph",
    "doi",
}


def correct_query(query: str) -> str:
    """Correct obvious misspellings while preserving known domain terms."""

    if not query.strip():
        return query

    try:
        from spellchecker import SpellChecker  # type: ignore[import-not-found]
    except Exception:
        return query

    checker = SpellChecker(distance=1)
    corrected = query
    for token in _WORD_RE.findall(query):
        lower = token.lower()
        if lower in _DOMAIN_TERMS or token.isupper() or len(token) <= 2:
            continue
        suggestion = checker.correction(token)
        if suggestion and suggestion.lower() != lower:
            corrected = re.sub(rf"\b{re.escape(token)}\b", suggestion, corrected)
    return corrected
