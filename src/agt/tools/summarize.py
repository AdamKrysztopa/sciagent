"""Deterministic bounded summarization for presentation output."""

from __future__ import annotations

import re

from agt.models import NormalizedPaper
from agt.providers.protocol import LLMProvider

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    if not text.strip():
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text.strip()) if part.strip()]


def _bound_summary(text: str, *, max_sentences: int) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    return " ".join(sentences[:max_sentences])


def deterministic_summary(paper: NormalizedPaper, *, max_sentences: int = 4) -> str:
    """Create deterministic 3-4 sentence summary without external calls."""

    sentences: list[str] = []
    if paper.year is not None:
        sentences.append(f"{paper.title} was published in {paper.year}.")
    else:
        sentences.append(f"{paper.title} has no reported publication year.")

    if paper.authors:
        lead = paper.authors[0]
        if len(paper.authors) > 1:
            sentences.append(f"The lead listed author is {lead} and collaborators.")
        else:
            sentences.append(f"The listed author is {lead}.")
    else:
        sentences.append("No author metadata is available in the retrieved record.")

    if paper.abstract and paper.abstract.strip():
        abstract_sentences = _split_sentences(paper.abstract)
        if abstract_sentences:
            sentences.extend(abstract_sentences[:2])
        else:
            sentences.append("The abstract text is present but could not be segmented.")
    else:
        sentences.append("No abstract was provided by the retrieval source.")

    if paper.open_access:
        sentences.append("The source marks this paper as open access.")
    else:
        sentences.append("The source does not mark this paper as open access.")

    return " ".join(sentences[:max_sentences])


async def summarize_papers(
    papers: list[NormalizedPaper],
    *,
    provider: LLMProvider | None,
    use_llm: bool,
    max_sentences: int,
) -> list[NormalizedPaper]:
    """Attach bounded deterministic summaries, with optional LLM attempt."""

    summarized: list[NormalizedPaper] = []
    for paper in papers:
        summary = deterministic_summary(paper, max_sentences=max_sentences)
        if use_llm and provider is not None and paper.abstract:
            prompt = (
                "Summarize this paper in exactly 3 to 4 short sentences. "
                "Use plain text with no bullets. "
                f"Title: {paper.title}\n"
                f"Year: {paper.year}\n"
                f"Abstract: {paper.abstract}"
            )
            try:
                generated = await provider.ainvoke(prompt)
                bounded = _bound_summary(generated, max_sentences=max_sentences)
                if bounded:
                    summary = bounded
            except Exception:
                # Deterministic fallback is already computed and intentionally retained.
                pass

        summarized.append(paper.model_copy(update={"summary": summary}))

    return summarized
