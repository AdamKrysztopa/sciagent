"""LLM-based keyword and collection-name extraction from a free-text query."""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field

from agt.providers.protocol import LLMProvider
from agt.tools.query_rewriter import extract_json

_EXTRACT_PROMPT = """\
You are a research assistant that reads a natural-language search request and extracts \
structured metadata for an academic paper search.

Given the user's query, identify:
1. include_keywords — terms that MUST appear in the results (concepts, methods, diseases, \
   drugs, algorithms, techniques, specific names). 2-6 short strings.
2. exclude_keywords — terms that must NOT appear (out-of-scope topics, unwanted populations, \
   competing methods). Empty list if nothing to exclude.
3. collection_name — a short, human-readable Zotero collection name for these papers \
   (3-5 words, title-case). null if the topic is too vague.

Rules:
- Keywords should be standalone nouns or short noun-phrases — no verbs, no stopwords.
- Do NOT repeat terms across include and exclude.
- Return ONLY a JSON object, no markdown, no explanation.

Examples:
Input: "deep learning for diabetic retinopathy detection, no GAN papers"
Output: {{"include_keywords": ["diabetic retinopathy", "deep learning", "detection"], \
"exclude_keywords": ["GAN", "generative adversarial"], \
"collection_name": "Retinopathy Deep Learning"}}

Input: "RAG techniques for legal documents, not medical"
Output: {{"include_keywords": ["retrieval augmented generation", "legal", "documents"], \
"exclude_keywords": ["medical", "clinical", "healthcare"], \
"collection_name": "Legal RAG Techniques"}}

Input: "papers on CRISPR gene editing published after 2020"
Output: {{"include_keywords": ["CRISPR", "gene editing", "genome editing"], \
"exclude_keywords": [], \
"collection_name": "CRISPR Gene Editing"}}

Now process:
Input: "{query}"
Output: """


class KeywordExtraction(BaseModel):
    """Structured keywords extracted from a free-text query."""

    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    collection_name: str | None = None


def _parse_string_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in cast(list[object], raw) if str(item).strip()]


async def extract_keywords(query: str, provider: LLMProvider) -> KeywordExtraction:
    """Ask the LLM to extract include/exclude keywords and a collection name."""
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
    )
