"""Optional KeyBERT-based keyword extraction fallback."""

# ruff: noqa: PLC0415
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _load_model() -> object:
    from keybert import KeyBERT  # type: ignore[import-not-found]

    return KeyBERT("all-MiniLM-L6-v2")


def extract_keywords(query: str, top_n: int = 5) -> list[str]:
    """Extract keywords from free text, returning unique tokens preserving order."""

    if not query.strip():
        return []

    try:
        model = _load_model()
        keywords = model.extract_keywords(  # type: ignore[attr-defined]
            query,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            top_n=top_n,
        )
    except Exception:
        return []

    normalized: list[str] = []
    for item in keywords:
        if not isinstance(item, tuple) or len(item) < 1:
            continue
        text = str(item[0]).strip().lower()
        if text and text not in normalized:
            normalized.append(text)
    return normalized
