"""LLM-based query rewriting and result validation for academic search."""

from __future__ import annotations

import json
import re
from typing import Any, cast

from pydantic import BaseModel, Field

from agt.models import NormalizedPaper
from agt.providers.protocol import LLMProvider


class RewrittenQuery(BaseModel):
    """LLM-extracted academic search query and keywords."""

    search_query: str
    keywords: list[str] = Field(default_factory=list)
    topic: str = ""
    synonyms: list[str] = Field(default_factory=list)
    pubmed_query: str | None = None
    arxiv_categories: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """LLM assessment of search-result relevance."""

    is_relevant: bool = True
    reason: str = ""
    suggested_query: str | None = None


_REWRITE_PROMPT = """\
You are an academic search query optimizer. Given a user's request for research \
papers, extract a focused search query for academic databases.

Rules:
- Output ONLY topic keywords suitable for Semantic Scholar / OpenAlex search APIs
- Do NOT include year constraints, citation counts, limits, or meta-instructions
- Use standard academic terminology
- Be concise: 2-5 keywords or a short phrase
- Think about what terms would appear in paper titles and abstracts
- Return 2-4 useful synonym queries for expansion
- Optionally include a PubMed-oriented query and arXiv categories when useful

Examples:
Input: "Most recent, and highest quoted papers in nutrition in sport. not older than 2024"
Output: {{"search_query": "sports nutrition", "keywords": ["sports", "nutrition"], \
"topic": "nutrition in sports and athletic performance", "synonyms": ["athlete nutrition", \
"exercise nutrition"], "pubmed_query": "sports nutrition[Title/Abstract]", \
"arxiv_categories": ["q-bio.QM"]}}

Input: "the most cited 2020 and newer timeseries papers - list 5"
Output: {{"search_query": "time series analysis", "keywords": ["time", "series", \
"analysis"], "topic": "time series analysis methods", "synonyms": ["time-series forecasting", \
"temporal modeling"], "pubmed_query": null, "arxiv_categories": ["cs.LG", "stat.ML"]}}

Input: "the most advanced RAG techniques in 2026 - game changers"
Output: {{"search_query": "retrieval augmented generation", "keywords": ["retrieval", \
"augmented", "generation"], "topic": "retrieval-augmented generation techniques", \
"synonyms": ["RAG", "retrieval-enhanced generation"], "pubmed_query": null, \
"arxiv_categories": ["cs.CL", "cs.AI"]}}

Now process this request:
Input: "{query}"
Output: """

_VALIDATE_PROMPT = """\
You are validating academic search results for topic relevance.

Original request: "{original_query}"
Expected topic: "{topic}"

Papers found:
{paper_list}

Are at least half of these papers clearly relevant to the expected topic? \
A paper is relevant only if its title directly relates to the topic.

Respond with ONLY a JSON object (no markdown, no explanation):
{{"is_relevant": true or false, "reason": "brief explanation", \
"suggested_query": "alternative search query if not relevant, otherwise null"}}"""

_MAX_PAPERS_IN_VALIDATION = 10
_ABSTRACT_SNIPPET_LEN = 150


def extract_json(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from LLM output, handling markdown wrapping."""
    stripped = text.strip()
    try:
        obj: object = json.loads(stripped)
        if isinstance(obj, dict):
            return cast(dict[str, Any], obj)
    except json.JSONDecodeError:
        pass

    code_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
    if code_match:
        try:
            obj = json.loads(code_match.group(1).strip())
            if isinstance(obj, dict):
                return cast(dict[str, Any], obj)
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"\{[^{}]*\}", stripped)
    if brace_match:
        try:
            obj = json.loads(brace_match.group(0))
            if isinstance(obj, dict):
                return cast(dict[str, Any], obj)
        except json.JSONDecodeError:
            pass

    return None


async def rewrite_query(query: str, provider: LLMProvider) -> RewrittenQuery:
    """Use LLM to extract an optimized academic search query."""
    prompt = _REWRITE_PROMPT.format(query=query)
    response = await provider.ainvoke(prompt)

    parsed = extract_json(response)
    if parsed is None:
        return RewrittenQuery(search_query=query, topic=query)

    search_query = str(parsed.get("search_query", query)).strip()
    keywords_raw = parsed.get("keywords", [])
    keywords = (
        [str(k) for k in cast(list[object], keywords_raw)] if isinstance(keywords_raw, list) else []
    )
    topic = str(parsed.get("topic", search_query)).strip()
    synonyms_raw = parsed.get("synonyms", [])
    synonyms = (
        [str(value).strip() for value in cast(list[object], synonyms_raw)]
        if isinstance(synonyms_raw, list)
        else []
    )
    pubmed_query_raw = parsed.get("pubmed_query")
    pubmed_query = str(pubmed_query_raw).strip() if isinstance(pubmed_query_raw, str) else None
    arxiv_categories_raw = parsed.get("arxiv_categories", [])
    arxiv_categories = (
        [str(value).strip() for value in cast(list[object], arxiv_categories_raw)]
        if isinstance(arxiv_categories_raw, list)
        else []
    )

    if not search_query:
        search_query = query

    return RewrittenQuery(
        search_query=search_query,
        keywords=keywords,
        topic=topic,
        synonyms=[value for value in synonyms if value],
        pubmed_query=pubmed_query if pubmed_query else None,
        arxiv_categories=[value for value in arxiv_categories if value],
    )


async def validate_results(
    original_query: str,
    topic: str,
    papers: list[NormalizedPaper],
    provider: LLMProvider,
) -> ValidationResult:
    """Use LLM to check if search results are relevant to the original query."""
    if not papers:
        return ValidationResult(is_relevant=False, reason="no results to validate")

    lines: list[str] = []
    for i, paper in enumerate(papers[:_MAX_PAPERS_IN_VALIDATION]):
        snippet = ""
        if paper.abstract:
            snippet = f" - {paper.abstract[:_ABSTRACT_SNIPPET_LEN]}"
        lines.append(f"{i + 1}. {paper.title}{snippet}")

    prompt = _VALIDATE_PROMPT.format(
        original_query=original_query,
        topic=topic,
        paper_list="\n".join(lines),
    )

    response = await provider.ainvoke(prompt)
    parsed = extract_json(response)

    if parsed is None:
        return ValidationResult(is_relevant=True, reason="could not parse validation response")

    is_relevant = bool(parsed.get("is_relevant", True))
    reason = str(parsed.get("reason", "")).strip()
    raw_suggested = parsed.get("suggested_query")
    suggested_query: str | None = None
    if raw_suggested and str(raw_suggested).strip() not in ("", "null", "None"):
        suggested_query = str(raw_suggested).strip()

    return ValidationResult(is_relevant=is_relevant, reason=reason, suggested_query=suggested_query)
