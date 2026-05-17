"""Query spell correction applied as a pre-processing hook before retrieval."""

from __future__ import annotations

import re

from spellchecker import SpellChecker

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")

# Terms that must not be spell-corrected: source names, acronyms, and domain vocabulary.
_DOMAIN_TERMS: frozenset[str] = frozenset({
    # Academic databases and services
    "arxiv",
    "pubmed",
    "openalex",
    "crossref",
    "europepmc",
    "semanticscholar",
    "europe",
    "pmc",
    "doi",
    "isbn",
    "issn",
    "preprint",
    "biorxiv",
    "medrxiv",
    "ssrn",
    # AI / ML / CS vocabulary
    "rag",
    "llm",
    "llms",
    "gpt",
    "bert",
    "gnn",
    "cnn",
    "rnn",
    "lstm",
    "gan",
    "vae",
    "mlp",
    "rl",
    "ppo",
    "dpo",
    "sft",
    "ai",
    "ml",
    "nlp",
    "cv",
    "transformer",
    "transformers",
    "attention",
    "retrieval",
    "augmented",
    "embeddings",
    "tokenizer",
    "tokenization",
    "finetuning",
    "finetune",
    "pretrained",
    "pretraining",
    "autoregressive",
    "multimodal",
    "hallucination",
    "hallucinations",
    "langgraph",
    "langchain",
    "timeseries",
    "reinforcement",
    "contrastive",
    "diffusion",
    # Biology / medicine vocabulary
    "crispr",
    "rna",
    "dna",
    "mrna",
    "pcr",
    "gwas",
    "snp",
    "genomics",
    "proteomics",
    "transcriptomics",
    "metabolomics",
    "epigenetics",
    "microbiome",
    "biomarker",
    "covid",
    "sars",
    "covid19",
    # General academic
    "meta",
    "bibliometric",
    "systematic",
    "longitudinal",
    "quantitative",
    "qualitative",
    "multivariate",
})

_checker = SpellChecker(distance=1)


def correct_query(query: str) -> str:
    """Fix obvious typos in the query while preserving domain terminology.

    Skips: uppercase acronyms, domain terms, short tokens (≤2 chars), numbers.
    Returns the original query unchanged when no corrections are needed.
    """
    if not query.strip():
        return query

    corrected = query
    for token in _WORD_RE.findall(query):
        lower = token.lower()
        if (
            lower in _DOMAIN_TERMS
            or token.isupper()  # ALL-CAPS acronym — skip
            or len(token) <= 2  # noqa: PLR2004
        ):
            continue
        suggestion = _checker.correction(lower)
        if suggestion is not None and suggestion != lower:
            if token[0].isupper():
                suggestion = suggestion.capitalize()
            corrected = re.sub(rf"\b{re.escape(token)}\b", suggestion, corrected)
    return corrected
