"""LLM-based keyword and filter extraction from a free-text query."""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field

from agt.providers.protocol import LLMProvider
from agt.tools.query_rewriter import extract_json

_EXTRACT_PROMPT = """\
You are a research assistant that reads a natural-language search request and extracts \
structured metadata for an academic paper search.

Given the user's query, identify ALL of the following fields:
1. include_keywords — terms that MUST appear in the results (concepts, methods, diseases, \
   algorithms, techniques, specific names). 2-6 short noun-phrases.
2. exclude_keywords — terms that must NOT appear (out-of-scope topics, unwanted populations, \
   competing methods). Empty list if nothing to exclude.
3. collection_name — a short, human-readable Zotero collection name (3-5 words, title-case). \
   null if the topic is too vague.
4. min_year — earliest publication year as an integer, or null. \
   "newer than 2023" / "after 2023" → 2024. "from 2020" / "since 2020" → 2020.
5. max_year — latest publication year as an integer, or null.
6. min_citations — minimum citation count as an integer, or null. \
   "more than 50 citations" → 50. "highly cited" alone → null.
7. max_citations — maximum citation count as an integer, or null.
8. open_access_only — true if the query explicitly asks for open-access papers, else false.

Rules:
- Keywords: standalone nouns or short noun-phrases only — no verbs, no stopwords.
- Do NOT repeat terms across include and exclude.
- Year/citation fields must be plain integers, never strings.
- Return ONLY a JSON object, no markdown, no explanation.

Examples:
Input: "deep learning for diabetic retinopathy detection, no GAN papers"
Output: {{"include_keywords": ["diabetic retinopathy", "deep learning", "detection"], \
"exclude_keywords": ["GAN", "generative adversarial"], "collection_name": "Retinopathy Deep Learning", \
"min_year": null, "max_year": null, "min_citations": null, "max_citations": null, "open_access_only": false}}

Input: "RAG techniques for legal documents, not medical, open access, newer than 2022, more than 30 citations"
Output: {{"include_keywords": ["retrieval augmented generation", "legal", "documents"], \
"exclude_keywords": ["medical", "clinical", "healthcare"], "collection_name": "Legal RAG Techniques", \
"min_year": 2023, "max_year": null, "min_citations": 30, "max_citations": null, "open_access_only": true}}

Input: "Vision Transformers surveys and review, newer than 2023. More than 50 citations."
Output: {{"include_keywords": ["Vision Transformer", "survey", "review"], \
"exclude_keywords": [], "collection_name": "Vision Transformer Surveys", \
"min_year": 2024, "max_year": null, "min_citations": 50, "max_citations": null, "open_access_only": false}}

Input: "CRISPR gene editing papers from 2018 to 2022"
Output: {{"include_keywords": ["CRISPR", "gene editing", "genome editing"], \
"exclude_keywords": [], "collection_name": "CRISPR Gene Editing", \
"min_year": 2018, "max_year": 2022, "min_citations": null, "max_citations": null, "open_access_only": false}}

Now process:
Input: "{query}"
Output: """


class KeywordExtraction(BaseModel):
    """All filter fields extracted from a free-text query."""

    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    collection_name: str | None = None
    min_year: int | None = None
    max_year: int | None = None
    min_citations: int | None = None
    max_citations: int | None = None
    open_access_only: bool = False


def _parse_string_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in cast(list[object], raw) if str(item).strip()]


def _parse_nullable_int(raw: object) -> int | None:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        try:
            return int(raw.strip())
        except ValueError:
            return None
    return None


async def extract_keywords(query: str, provider: LLMProvider) -> KeywordExtraction:
    """Ask the LLM to extract keywords, year/citation constraints, and a collection name."""
    prompt = _EXTRACT_PROMPT.format(query=query.replace('"', '\\"'))
    response = await provider.ainvoke(prompt)

    parsed: dict[str, Any] | None = extract_json(response)
    if parsed is None:
        return KeywordExtraction()

    raw_name = parsed.get("collection_name")
    collection_name: str | None = None
    if isinstance(raw_name, str) and raw_name.strip() and raw_name.strip().lower() != "null":
        collection_name = raw_name.strip()

    return KeywordExtraction(
        include_keywords=_parse_string_list(parsed.get("include_keywords")),
        exclude_keywords=_parse_string_list(parsed.get("exclude_keywords")),
        collection_name=collection_name,
        min_year=_parse_nullable_int(parsed.get("min_year")),
        max_year=_parse_nullable_int(parsed.get("max_year")),
        min_citations=_parse_nullable_int(parsed.get("min_citations")),
        max_citations=_parse_nullable_int(parsed.get("max_citations")),
        open_access_only=bool(parsed.get("open_access_only", False)),
    )
