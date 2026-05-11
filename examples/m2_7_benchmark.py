"""AGT-29 — Retrieval quality benchmark against standalone LLM search.

Runs a curated evaluation panel of >=20 realistic research requests and checks:

- hard-filter contract preservation (plan + results)
- must-find recall@10 and recall@20 with DOI-first matching
- source coverage expectations
- topic / alternate coverage
- per-query latency and estimated runtime cost

Runs without paid/search-engine API keys by default.
Optional external baseline comparison uses a checked-in reviewed artifact rather
than a live paid dependency.

Usage:
    uv run python examples/m2_7_benchmark.py
    uv run python examples/m2_7_benchmark.py --measure-flags
    uv run python examples/m2_7_benchmark.py --output-json results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _shared_demo_helpers import (
    default_zotero_api_key,
    default_zotero_library_id,
    normalize_strict_settings_env,
    resolve_env_key,
    resolve_xai_key,
)

from agt.config import Settings
from agt.guardrails import configure_guardrails, thread_context
from agt.models import NormalizedPaper, SearchPlan
from agt.tools.search_papers import search_papers

BENCHMARK_VERSION = "m2.7-agt29-v3"
RESULT_LIMIT = 20
TOP_K_PRIMARY = 10
DEFAULT_MANUAL_BASELINE_PATH = (
    Path(__file__).resolve().parent / "benchmark_artifacts" / "manual_web_search_baseline.json"
)

# ---------------------------------------------------------------------------
# Evaluation panel — 20 realistic research requests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MustFindTarget:
    """A benchmark target tracked with DOI-first matching and title fallback."""

    label: str
    doi: str | None = None
    title_fragments: list[str] = field(default_factory=list)


def _target(label: str, doi: str | None = None, *title_fragments: str) -> MustFindTarget:
    return MustFindTarget(label=label, doi=doi, title_fragments=list(title_fragments))


@dataclass
class PanelEntry:
    """A single benchmark query with expected constraint checks."""

    query_id: str
    query: str
    domain: str
    # Substring tokens that should appear in at least one result title/abstract.
    expected_topic_tokens: list[str]
    # Hard constraint checks applied to every result.
    min_year: int | None = None
    max_year: int | None = None
    open_access_required: bool = False
    min_citations: int = 0
    # Sources that should appear in telemetry for this query family.
    expected_sources: list[str] = field(default_factory=list)
    # DOI-first must-find targets. Title fragments are used as fallback only.
    must_find: list[MustFindTarget] = field(default_factory=list)
    # Broad queries may accept any of these fragments when no single anchor is required.
    acceptable_alternate_fragments: list[str] = field(default_factory=list)
    # Notes for human reviewers.
    notes: str = ""


PANEL: list[PanelEntry] = [
    # -----------------------------------------------------------------------
    # AI — Retrieval-Augmented Generation
    # -----------------------------------------------------------------------
    PanelEntry(
        query_id="AI-01",
        query="retrieval augmented generation survey",
        domain="AI",
        expected_topic_tokens=["retrieval", "augmented", "generation"],
        expected_sources=["semantic_scholar", "openalex", "crossref", "arxiv"],
        must_find=[
            _target(
                "Lewis et al. RAG",
                "10.48550/arXiv.2005.11401",
                "retrieval-augmented generation for knowledge-intensive nlp tasks",
            ),
            _target(
                "REALM",
                "10.48550/arXiv.2002.08909",
                "realm: retrieval-augmented language model pre-training",
            ),
        ],
        notes="Core RAG survey; should surface REALM, RAG (Lewis 2020), etc.",
    ),
    PanelEntry(
        query_id="AI-02",
        query="the most advanced RAG techniques since 2024 - game changers",
        domain="AI",
        expected_topic_tokens=["retrieval", "augmented", "generation"],
        min_year=2024,
        min_citations=20,
        expected_sources=["semantic_scholar", "openalex", "arxiv"],
        acceptable_alternate_fragments=["retrieval-augmented generation", "rag", "survey"],
        notes="Freshness check: only 2024+ results should survive.",
    ),
    PanelEntry(
        query_id="AI-03",
        query="large language model reasoning chain-of-thought prompting not older than 2024",
        domain="AI",
        expected_topic_tokens=["chain", "thought", "reasoning"],
        min_year=2024,
        expected_sources=["semantic_scholar", "openalex", "arxiv"],
        acceptable_alternate_fragments=["chain-of-thought", "reasoning", "prompting"],
        notes="Hard year filter; 2023 and older must be excluded.",
    ),
    PanelEntry(
        query_id="AI-04",
        query="transformer attention mechanism survey",
        domain="AI",
        expected_topic_tokens=["attention", "transformer"],
        expected_sources=["semantic_scholar", "openalex", "crossref", "arxiv"],
        must_find=[
            _target(
                "Attention Is All You Need",
                "10.48550/arXiv.1706.03762",
                "attention is all you need",
            )
        ],
        notes="Foundational; should surface Vaswani 2017 and successors.",
    ),
    PanelEntry(
        query_id="AI-05",
        query="open access papers on federated learning privacy 2023 and newer",
        domain="AI",
        expected_topic_tokens=["federated", "learning", "privacy"],
        min_year=2023,
        open_access_required=True,
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        acceptable_alternate_fragments=["federated learning", "privacy", "differential privacy"],
        notes="Freshness + open access compound filter.",
    ),
    # -----------------------------------------------------------------------
    # Time-series
    # -----------------------------------------------------------------------
    PanelEntry(
        query_id="TS-01",
        query="time-series forecasting methods selection based on the data itself, not older than 2024",
        domain="time-series",
        expected_topic_tokens=["time", "series", "forecasting"],
        min_year=2024,
        expected_sources=["semantic_scholar", "openalex", "arxiv"],
        acceptable_alternate_fragments=["forecasting method selection", "time series forecasting"],
        notes="Key AGT-28 acceptance criteria example; hard year=2024.",
    ),
    PanelEntry(
        query_id="TS-02",
        query="the most cited 2020 and newer timeseries papers - list 5",
        domain="time-series",
        expected_topic_tokens=["time", "series", "timeseries", "temporal", "forecasting"],
        min_year=2020,
        min_citations=10,
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        must_find=[
            _target(
                "Temporal Fusion Transformer",
                "10.1016/j.ijforecast.2021.03.012",
                "temporal fusion transformers for interpretable multi-horizon time series forecasting",
            )
        ],
        acceptable_alternate_fragments=["time series forecasting", "transformer"],
        notes="Citation + year combined constraint. 'timeseries' is a single-token variant.",
    ),
    PanelEntry(
        query_id="TS-03",
        query="anomaly detection in time series deep learning",
        domain="time-series",
        expected_topic_tokens=["anomaly", "detection", "time"],
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        must_find=[
            _target(
                "DeepAnT",
                "10.1109/ACCESS.2018.2886457",
                "deepant",
            )
        ],
        notes="No year constraint; broad coverage expected.",
    ),
    PanelEntry(
        query_id="TS-04",
        query="temporal fusion transformer for multi-horizon forecasting",
        domain="time-series",
        expected_topic_tokens=["temporal", "fusion", "transformer"],
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        must_find=[
            _target(
                "Temporal Fusion Transformer",
                "10.1016/j.ijforecast.2021.03.012",
                "temporal fusion transformers for interpretable multi-horizon time series forecasting",
            )
        ],
        notes="Specific model paper; should surface Lim et al. 2021.",
    ),
    PanelEntry(
        query_id="TS-05",
        query="foundation models for time series since 2023",
        domain="time-series",
        expected_topic_tokens=["foundation", "model", "time"],
        min_year=2023,
        expected_sources=["semantic_scholar", "openalex", "arxiv"],
        must_find=[
            _target(
                "Lag-Llama",
                "10.48550/arXiv.2310.08278",
                "lag-llama: towards foundation models for probabilistic time series forecasting",
            )
        ],
        acceptable_alternate_fragments=["foundation model", "time series"],
        notes="Emerging area; 2023+ coverage.",
    ),
    # -----------------------------------------------------------------------
    # Biomedicine
    # -----------------------------------------------------------------------
    PanelEntry(
        query_id="BIO-01",
        query="CRISPR gene editing therapeutic applications not older than 2022",
        domain="biomedicine",
        expected_topic_tokens=["crispr", "gene"],
        min_year=2022,
        expected_sources=["pubmed", "europe_pmc", "semantic_scholar"],
        must_find=[
            _target(
                "Therapeutic genome editing by CRISPR-Cas systems",
                "10.1038/s41573-021-00284-7",
                "therapeutic genome editing by crispr-cas systems",
            )
        ],
        notes="PubMed-heavy; recent therapeutic applications.",
    ),
    PanelEntry(
        query_id="BIO-02",
        query="protein structure prediction AlphaFold deep learning",
        domain="biomedicine",
        expected_topic_tokens=["protein", "structure", "alphafold"],
        expected_sources=["pubmed", "europe_pmc", "semantic_scholar"],
        must_find=[
            _target(
                "AlphaFold 2",
                "10.1038/s41586-021-03819-2",
                "highly accurate protein structure prediction with alphafold",
            )
        ],
        notes="Should surface AlphaFold 2 paper (Jumper 2021).",
    ),
    PanelEntry(
        query_id="BIO-03",
        query="cancer immunotherapy checkpoint inhibitors clinical trial 2023 and newer",
        domain="biomedicine",
        expected_topic_tokens=["immunotherapy", "checkpoint", "cancer"],
        min_year=2023,
        expected_sources=["pubmed", "europe_pmc", "semantic_scholar"],
        acceptable_alternate_fragments=["checkpoint inhibitor", "clinical trial", "immunotherapy"],
        notes="Freshness check for clinical literature.",
    ),
    PanelEntry(
        query_id="BIO-04",
        query="open access papers on COVID long-term effects after 2021",
        domain="biomedicine",
        expected_topic_tokens=["covid", "long"],
        min_year=2021,
        open_access_required=True,
        expected_sources=["pubmed", "europe_pmc", "semantic_scholar"],
        must_find=[
            _target(
                "Long COVID review",
                "10.1038/s41579-022-00846-2",
                "long covid: major findings, mechanisms and recommendations",
            )
        ],
        notes="Open access + year constraint on biomedical topic.",
    ),
    PanelEntry(
        query_id="BIO-05",
        query="single cell RNA sequencing analysis methods",
        domain="biomedicine",
        expected_topic_tokens=["single", "cell", "rna"],
        expected_sources=["pubmed", "europe_pmc", "semantic_scholar"],
        must_find=[
            _target(
                "SCANPY",
                "10.1186/s13059-017-1382-0",
                "scanpy: large-scale single-cell gene expression data analysis",
            )
        ],
        notes="scRNA-seq methods; should surface Seurat, Scanpy etc.",
    ),
    # -----------------------------------------------------------------------
    # Social Science
    # -----------------------------------------------------------------------
    PanelEntry(
        query_id="SOC-01",
        query="behavioral economics nudge theory decision making",
        domain="social-science",
        expected_topic_tokens=["behavioral", "decision", "nudge"],
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        acceptable_alternate_fragments=["nudge", "choice architecture", "decision making"],
        notes="Thaler/Sunstein domain; classic and recent papers.",
    ),
    PanelEntry(
        query_id="SOC-02",
        query="survey methodology response bias questionnaire design",
        domain="social-science",
        expected_topic_tokens=["survey", "bias", "questionnaire"],
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        acceptable_alternate_fragments=[
            "response bias",
            "questionnaire design",
            "survey methodology",
        ],
        notes="Methodological literature; broad coverage.",
    ),
    PanelEntry(
        query_id="SOC-03",
        query="social media misinformation spread network effects not older than 2022",
        domain="social-science",
        expected_topic_tokens=["misinformation", "social", "network"],
        min_year=2022,
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        acceptable_alternate_fragments=["misinformation", "social media", "network effects"],
        notes="Freshness check; COVID and post-COVID misinformation era.",
    ),
    # -----------------------------------------------------------------------
    # Interdisciplinary
    # -----------------------------------------------------------------------
    PanelEntry(
        query_id="INTER-01",
        query="graph neural networks drug discovery molecular property prediction",
        domain="interdisciplinary",
        expected_topic_tokens=["graph", "neural", "drug"],
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        must_find=[
            _target(
                "Neural message passing for quantum chemistry",
                "10.48550/arXiv.1704.01212",
                "neural message passing for quantum chemistry",
            )
        ],
        notes="AI x biomedicine; should surface GNN-based drug papers.",
    ),
    PanelEntry(
        query_id="INTER-02",
        query="climate change machine learning prediction modeling since 2022",
        domain="interdisciplinary",
        expected_topic_tokens=["climate", "machine", "learning"],
        min_year=2022,
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        acceptable_alternate_fragments=["climatebench", "climate change", "machine learning"],
        notes="AI x climate science; freshness check.",
    ),
    PanelEntry(
        query_id="INTER-03",
        query="large language models in healthcare clinical decision support not older than 2023",
        domain="interdisciplinary",
        expected_topic_tokens=["language", "model", "clinical"],
        min_year=2023,
        expected_sources=["pubmed", "europe_pmc", "semantic_scholar", "openalex"],
        must_find=[
            _target(
                "Large language models in medicine",
                "10.1038/s41591-023-02448-8",
                "large language models in medicine",
            )
        ],
        notes="AI x medicine; hard year filter 2023+.",
    ),
    PanelEntry(
        query_id="INTER-04",
        query="natural language processing education adaptive learning systems",
        domain="interdisciplinary",
        expected_topic_tokens=["natural", "language", "education"],
        expected_sources=["semantic_scholar", "openalex", "crossref"],
        acceptable_alternate_fragments=["adaptive learning", "intelligent tutoring", "education"],
        notes="AI x education; broad coverage expected.",
    ),
]

_MIN_PANEL_SIZE = 20
_MIN_MUST_FIND_TARGETS = 12
assert len(PANEL) >= _MIN_PANEL_SIZE, (
    f"Benchmark requires >={_MIN_PANEL_SIZE} queries; got {len(PANEL)}"
)
assert sum(len(entry.must_find) for entry in PANEL) >= _MIN_MUST_FIND_TARGETS, (
    f"Benchmark needs >={_MIN_MUST_FIND_TARGETS} must-find targets"
)
assert all(entry.expected_sources for entry in PANEL), (
    "Every benchmark entry needs source expectations"
)
assert all(entry.must_find or entry.acceptable_alternate_fragments for entry in PANEL), (
    "Every benchmark entry needs must-find targets or alternate coverage"
)


# ---------------------------------------------------------------------------
# Compliance checking
# ---------------------------------------------------------------------------


def _normalize_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized or None


def _normalize_source_name(value: str) -> str:
    return value.split(":", 1)[0].strip().lower()


def _paper_text(paper: NormalizedPaper) -> str:
    return f"{paper.title} {paper.abstract or ''}".lower()


def _contains_any_fragment(text: str, fragments: list[str]) -> bool:
    return any(fragment.lower() in text for fragment in fragments)


def _paper_matches_target(paper: NormalizedPaper, target: MustFindTarget) -> bool:
    target_doi = _normalize_doi(target.doi)
    paper_doi = _normalize_doi(paper.doi)
    if target_doi is not None and paper_doi == target_doi:
        return True
    if not target.title_fragments:
        return False
    return _contains_any_fragment(_paper_text(paper), target.title_fragments)


def _matched_target_labels(
    papers: list[NormalizedPaper], targets: list[MustFindTarget]
) -> list[str]:
    matched: list[str] = []
    for target in targets:
        if any(_paper_matches_target(paper, target) for paper in papers):
            matched.append(target.label)
    return matched


def _check_year_compliance(
    papers: list[NormalizedPaper],
    entry: PanelEntry,
) -> tuple[int, list[str]]:
    """Return (violation_count, violation_messages)."""
    violations: list[str] = []
    for paper in papers:
        if entry.min_year is not None and (paper.year is None or paper.year < entry.min_year):
            violations.append(
                f"  YEAR VIOLATION [{paper.source}] '{paper.title}' year={paper.year} < min={entry.min_year}"
            )
        if entry.max_year is not None and (paper.year is None or paper.year > entry.max_year):
            violations.append(
                f"  YEAR VIOLATION [{paper.source}] '{paper.title}' year={paper.year} > max={entry.max_year}"
            )
    return len(violations), violations


def _check_open_access_compliance(
    papers: list[NormalizedPaper],
    entry: PanelEntry,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    if entry.open_access_required:
        for paper in papers:
            if not paper.open_access:
                violations.append(
                    f"  OA VIOLATION [{paper.source}] '{paper.title}' open_access=False"
                )
    return len(violations), violations


def _check_citation_compliance(
    papers: list[NormalizedPaper],
    entry: PanelEntry,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    if entry.min_citations > 0:
        for paper in papers:
            if paper.citation_count < entry.min_citations:
                violations.append(
                    f"  CITATION VIOLATION [{paper.source}] '{paper.title}' citations={paper.citation_count} < min={entry.min_citations}"
                )
    return len(violations), violations


def _check_topic_coverage(
    papers: list[NormalizedPaper],
    entry: PanelEntry,
) -> bool:
    """At least one paper must mention one of the expected topic tokens."""
    tokens = [t.lower() for t in entry.expected_topic_tokens]
    for paper in papers:
        text = f"{paper.title} {paper.abstract or ''}".lower()
        if any(token in text for token in tokens):
            return True
    return False


def _check_alternate_coverage(
    papers: list[NormalizedPaper],
    entry: PanelEntry,
) -> bool:
    if not entry.acceptable_alternate_fragments:
        return True
    return any(
        _contains_any_fragment(_paper_text(paper), entry.acceptable_alternate_fragments)
        for paper in papers
    )


def _check_expected_source_coverage(
    sources_used: list[str],
    entry: PanelEntry,
) -> list[str]:
    normalized_sources_used = {_normalize_source_name(source) for source in sources_used}
    return [
        source
        for source in entry.expected_sources
        if _normalize_source_name(source) not in normalized_sources_used
    ]


def _check_search_plan_contract(
    plan: SearchPlan | None,
    entry: PanelEntry,
) -> list[str]:
    if plan is None:
        return ["missing_search_plan"]

    mismatches: list[str] = []
    hard_filters = plan.hard_filters
    if entry.min_year is not None and hard_filters.min_year != entry.min_year:
        mismatches.append(f"min_year={hard_filters.min_year} expected={entry.min_year}")
    if entry.max_year is not None and hard_filters.max_year != entry.max_year:
        mismatches.append(f"max_year={hard_filters.max_year} expected={entry.max_year}")
    if entry.open_access_required and not hard_filters.open_access_only:
        mismatches.append("open_access_only=False expected=True")
    if entry.min_citations > 0 and hard_filters.min_citations < entry.min_citations:
        mismatches.append(
            f"min_citations={hard_filters.min_citations} expected>={entry.min_citations}"
        )
    return mismatches


# ---------------------------------------------------------------------------
# Per-query runner
# ---------------------------------------------------------------------------


@dataclass
class EntryResult:
    entry: PanelEntry
    papers: list[NormalizedPaper]
    plan: SearchPlan | None
    sources_used: list[str]
    sources_failed: list[str]
    year_violations: int
    oa_violations: int
    citation_violations: int
    topic_covered: bool
    alternate_covered: bool
    must_find_hits_at_10: list[str]
    must_find_hits_at_20: list[str]
    must_find_missing_at_20: list[str]
    expected_sources_missing: list[str]
    plan_filter_mismatches: list[str]
    latency_ms: float
    estimated_cost_usd: float
    error: str | None = None

    @property
    def must_find_target_count(self) -> int:
        return len(self.entry.must_find)

    @property
    def result_hard_filter_compliant(self) -> bool:
        return (
            self.year_violations == 0 and self.oa_violations == 0 and self.citation_violations == 0
        )

    @property
    def hard_filter_contract_compliant(self) -> bool:
        return self.result_hard_filter_compliant and not self.plan_filter_mismatches

    @property
    def source_coverage_compliant(self) -> bool:
        return not self.expected_sources_missing

    @property
    def recall_at_10(self) -> float | None:
        if self.must_find_target_count == 0:
            return None
        return len(self.must_find_hits_at_10) / self.must_find_target_count

    @property
    def recall_at_20(self) -> float | None:
        if self.must_find_target_count == 0:
            return None
        return len(self.must_find_hits_at_20) / self.must_find_target_count

    @property
    def passed(self) -> bool:
        return (
            self.error is None
            and self.hard_filter_contract_compliant
            and self.topic_covered
            and self.alternate_covered
            and self.source_coverage_compliant
            and not self.must_find_missing_at_20
        )


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    description: str
    settings_overrides: dict[str, Any]


@dataclass(frozen=True)
class ScenarioSummary:
    total_queries: int
    passed: int
    hard_filter_contract_rate: float
    result_hard_filter_rate: float
    topic_coverage_rate: float
    alternate_coverage_rate: float
    source_coverage_rate: float
    must_find_target_count: int
    must_find_recall_at_10: float | None
    must_find_recall_at_20: float | None
    average_latency_ms: float
    estimated_cost_usd_total: float
    source_usage_count: dict[str, int]


@dataclass
class ScenarioResult:
    config: ScenarioConfig
    results: list[EntryResult]
    summary: ScenarioSummary


async def _run_one(
    entry: PanelEntry,
    settings: Settings,
    *,
    scenario_name: str,
) -> EntryResult:
    start = perf_counter()
    try:
        thread_id = f"bench-{scenario_name}-{entry.query_id}"
        with thread_context(thread_id):
            papers, metadata = await search_papers(
                query=entry.query,
                limit=RESULT_LIMIT,
                settings=settings,
                thread_id=thread_id,
            )
        latency_ms = round((perf_counter() - start) * 1000, 2)
    except Exception as exc:
        return EntryResult(
            entry=entry,
            papers=[],
            plan=None,
            sources_used=[],
            sources_failed=[],
            year_violations=0,
            oa_violations=0,
            citation_violations=0,
            topic_covered=False,
            alternate_covered=False,
            must_find_hits_at_10=[],
            must_find_hits_at_20=[],
            must_find_missing_at_20=[target.label for target in entry.must_find],
            expected_sources_missing=entry.expected_sources[:],
            plan_filter_mismatches=["search_failed"],
            latency_ms=round((perf_counter() - start) * 1000, 2),
            estimated_cost_usd=0.0,
            error=str(exc),
        )

    year_count, _ = _check_year_compliance(papers, entry)
    oa_count, _ = _check_open_access_compliance(papers, entry)
    citation_count, _ = _check_citation_compliance(papers, entry)
    topic_ok = _check_topic_coverage(papers, entry)
    alternate_ok = _check_alternate_coverage(papers[:RESULT_LIMIT], entry)
    must_find_hits_at_10 = _matched_target_labels(papers[:TOP_K_PRIMARY], entry.must_find)
    must_find_hits_at_20 = _matched_target_labels(papers[:RESULT_LIMIT], entry.must_find)
    missing = [
        target.label for target in entry.must_find if target.label not in must_find_hits_at_20
    ]
    expected_sources_missing = _check_expected_source_coverage(metadata.sources_used, entry)
    plan_filter_mismatches = _check_search_plan_contract(metadata.search_plan, entry)

    return EntryResult(
        entry=entry,
        papers=papers,
        plan=metadata.search_plan,
        sources_used=metadata.sources_used,
        sources_failed=metadata.sources_failed,
        year_violations=year_count,
        oa_violations=oa_count,
        citation_violations=citation_count,
        topic_covered=topic_ok,
        alternate_covered=alternate_ok,
        must_find_hits_at_10=must_find_hits_at_10,
        must_find_hits_at_20=must_find_hits_at_20,
        must_find_missing_at_20=missing,
        expected_sources_missing=expected_sources_missing,
        plan_filter_mismatches=plan_filter_mismatches,
        latency_ms=latency_ms,
        estimated_cost_usd=0.0,
    )


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


_PASS = "PASS"
_FAIL = "FAIL"
_STATUS_WIDTH = 4


def _entry_messages(result: EntryResult) -> list[str]:
    messages: list[str] = []
    if result.year_violations:
        messages.append(f"year_violations={result.year_violations}")
    if result.oa_violations:
        messages.append(f"oa_violations={result.oa_violations}")
    if result.citation_violations:
        messages.append(f"citation_violations={result.citation_violations}")
    if result.plan_filter_mismatches:
        messages.append(f"plan_filter_mismatches={result.plan_filter_mismatches}")
    if not result.topic_covered:
        messages.append(
            f"topic_not_covered (expected tokens: {result.entry.expected_topic_tokens})"
        )
    if not result.alternate_covered:
        messages.append(
            "alternate_not_covered "
            f"(expected fragments: {result.entry.acceptable_alternate_fragments})"
        )
    if result.expected_sources_missing:
        messages.append(f"expected_sources_missing={result.expected_sources_missing}")
    if result.must_find_missing_at_20:
        messages.append(f"must_find_missing_at_20={result.must_find_missing_at_20}")
    return messages


def _print_entry_result(result: EntryResult, *, verbose: bool = False) -> None:
    status = _PASS if result.passed else _FAIL
    icon = "✓" if result.passed else "✗"
    recall20 = "n/a" if result.recall_at_20 is None else f"{result.recall_at_20:.2f}"
    print(
        f"  [{icon}] {result.entry.query_id:<10} {status:<{_STATUS_WIDTH}}  {result.entry.domain:<15}  results={len(result.papers):<2}  recall@20={recall20:<4}  latency_ms={result.latency_ms:>7.1f}"
    )
    if result.error:
        print(f"         ERROR: {result.error}")
    else:
        for message in _entry_messages(result):
            print(f"         {message}")
        if verbose and result.plan:
            plan = result.plan
            print(
                f"         search_plan.hard_filters: min_year={plan.hard_filters.min_year} max_year={plan.hard_filters.max_year}"
            )
            print(f"         search_plan.pushed_down: {plan.filters_pushed_down}")
            print(f"         search_plan.post_merge:  {plan.filters_enforced_post_merge}")
            print(f"         source_timings: {sorted(result.sources_used)}")
        if verbose and result.papers:
            for paper in result.papers[:3]:
                yr = paper.year if paper.year else "?"
                print(f"         [{yr}] {paper.title[:70]}")


def _summarize_results(results: list[EntryResult]) -> ScenarioSummary:
    total = len(results)
    target_count = sum(result.must_find_target_count for result in results)
    hits_at_10 = sum(len(result.must_find_hits_at_10) for result in results)
    hits_at_20 = sum(len(result.must_find_hits_at_20) for result in results)
    source_usage = Counter[str]()
    for result in results:
        source_usage.update(result.sources_used)

    return ScenarioSummary(
        total_queries=total,
        passed=sum(1 for result in results if result.passed),
        hard_filter_contract_rate=round(
            sum(1 for result in results if result.hard_filter_contract_compliant) / max(total, 1),
            3,
        ),
        result_hard_filter_rate=round(
            sum(1 for result in results if result.result_hard_filter_compliant) / max(total, 1),
            3,
        ),
        topic_coverage_rate=round(
            sum(1 for result in results if result.topic_covered) / max(total, 1),
            3,
        ),
        alternate_coverage_rate=round(
            sum(1 for result in results if result.alternate_covered) / max(total, 1),
            3,
        ),
        source_coverage_rate=round(
            sum(1 for result in results if result.source_coverage_compliant) / max(total, 1),
            3,
        ),
        must_find_target_count=target_count,
        must_find_recall_at_10=None if target_count == 0 else round(hits_at_10 / target_count, 3),
        must_find_recall_at_20=None if target_count == 0 else round(hits_at_20 / target_count, 3),
        average_latency_ms=round(
            sum(result.latency_ms for result in results) / max(total, 1),
            2,
        ),
        estimated_cost_usd_total=round(
            sum(result.estimated_cost_usd for result in results),
            6,
        ),
        source_usage_count=dict(sorted(source_usage.items())),
    )


def _scenario_to_dict(scenario: ScenarioResult) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for result in scenario.results:
        entry: dict[str, Any] = {
            "query_id": result.entry.query_id,
            "domain": result.entry.domain,
            "query": result.entry.query,
            "passed": result.passed,
            "result_count": len(result.papers),
            "latency_ms": result.latency_ms,
            "estimated_cost_usd": result.estimated_cost_usd,
            "year_violations": result.year_violations,
            "oa_violations": result.oa_violations,
            "citation_violations": result.citation_violations,
            "topic_covered": result.topic_covered,
            "alternate_covered": result.alternate_covered,
            "hard_filter_contract_compliant": result.hard_filter_contract_compliant,
            "result_hard_filter_compliant": result.result_hard_filter_compliant,
            "source_coverage_compliant": result.source_coverage_compliant,
            "must_find_target_count": result.must_find_target_count,
            "must_find_hits_at_10": result.must_find_hits_at_10,
            "must_find_hits_at_20": result.must_find_hits_at_20,
            "must_find_missing_at_20": result.must_find_missing_at_20,
            "recall_at_10": result.recall_at_10,
            "recall_at_20": result.recall_at_20,
            "expected_sources": result.entry.expected_sources,
            "expected_sources_missing": result.expected_sources_missing,
            "acceptable_alternate_fragments": result.entry.acceptable_alternate_fragments,
            "sources_used": sorted(result.sources_used),
            "sources_failed": sorted(result.sources_failed),
            "plan_filter_mismatches": result.plan_filter_mismatches,
            "must_find_targets": [
                {
                    "label": target.label,
                    "doi": target.doi,
                    "title_fragments": target.title_fragments,
                }
                for target in result.entry.must_find
            ],
            "error": result.error,
        }
        if result.plan is not None:
            entry["search_plan"] = {
                "hard_filters": result.plan.hard_filters.model_dump(),
                "rewritten_queries": result.plan.rewritten_queries,
                "filters_pushed_down": result.plan.filters_pushed_down,
                "filters_enforced_post_merge": result.plan.filters_enforced_post_merge,
            }
        entries.append(entry)

    return {
        "scenario": scenario.config.name,
        "description": scenario.config.description,
        "settings_overrides": scenario.config.settings_overrides,
        "summary": {
            "total_queries": scenario.summary.total_queries,
            "passed": scenario.summary.passed,
            "failed": scenario.summary.total_queries - scenario.summary.passed,
            "hard_filter_contract_rate": scenario.summary.hard_filter_contract_rate,
            "result_hard_filter_rate": scenario.summary.result_hard_filter_rate,
            "topic_coverage_rate": scenario.summary.topic_coverage_rate,
            "alternate_coverage_rate": scenario.summary.alternate_coverage_rate,
            "source_coverage_rate": scenario.summary.source_coverage_rate,
            "must_find_target_count": scenario.summary.must_find_target_count,
            "must_find_recall_at_10": scenario.summary.must_find_recall_at_10,
            "must_find_recall_at_20": scenario.summary.must_find_recall_at_20,
            "average_latency_ms": scenario.summary.average_latency_ms,
            "estimated_cost_usd_total": scenario.summary.estimated_cost_usd_total,
            "source_usage_count": scenario.summary.source_usage_count,
        },
        "entries": entries,
    }


def _load_baseline_artifact(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("Baseline artifact must contain a JSON object")
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Baseline artifact must define an entries list")
    return raw


def _compare_scenario_to_baseline(
    scenario: ScenarioResult,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    baseline_entries_raw = baseline.get("entries", [])
    baseline_entries: dict[str, dict[str, Any]] = {}
    for item in baseline_entries_raw:
        if isinstance(item, dict):
            query_id = item.get("query_id")
            if isinstance(query_id, str):
                baseline_entries[query_id] = item

    below_baseline: list[dict[str, Any]] = []
    for result in scenario.results:
        expected = baseline_entries.get(result.entry.query_id)
        if expected is None:
            continue
        failures: list[str] = []
        minimum_recall_at_10 = expected.get("minimum_recall_at_10")
        minimum_recall_at_20 = expected.get("minimum_recall_at_20")
        if isinstance(minimum_recall_at_10, (int, float)):
            observed = result.recall_at_10 or 0.0
            if observed < float(minimum_recall_at_10):
                failures.append("recall_at_10")
        if isinstance(minimum_recall_at_20, (int, float)):
            observed = result.recall_at_20 or 0.0
            if observed < float(minimum_recall_at_20):
                failures.append("recall_at_20")
        if (
            expected.get("requires_hard_filter_contract")
            and not result.hard_filter_contract_compliant
        ):
            failures.append("hard_filter_contract")
        if expected.get("requires_source_coverage") and not result.source_coverage_compliant:
            failures.append("source_coverage")
        if failures:
            below_baseline.append({
                "query_id": result.entry.query_id,
                "metrics": failures,
                "notes": expected.get("notes"),
            })

    return {
        "baseline_name": baseline.get("baseline_name", "manual-reviewed-baseline"),
        "baseline_version": baseline.get("baseline_version"),
        "scenario": scenario.config.name,
        "matched_or_exceeded": scenario.summary.total_queries - len(below_baseline),
        "below_baseline": below_baseline,
    }


def _build_json_report(
    scenarios: list[ScenarioResult],
    baseline_comparisons: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "panel_size": len(PANEL),
        "result_limit": RESULT_LIMIT,
        "scenarios": [_scenario_to_dict(scenario) for scenario in scenarios],
        "baseline_comparisons": baseline_comparisons,
    }


async def _run_scenario(
    config: ScenarioConfig,
    base_settings: Settings,
    *,
    verbose: bool,
) -> ScenarioResult:
    settings = base_settings.model_copy(update=config.settings_overrides)
    print("\n" + "-" * 80)
    print(f"SCENARIO: {config.name} — {config.description}")
    print("-" * 80)

    results: list[EntryResult] = []
    for entry in PANEL:
        print(f"\nRunning {entry.query_id}: {entry.query[:60]}...")
        result = await _run_one(entry, settings, scenario_name=config.name)
        results.append(result)
        _print_entry_result(result, verbose=verbose)

    summary = _summarize_results(results)
    recall10 = (
        "n/a" if summary.must_find_recall_at_10 is None else f"{summary.must_find_recall_at_10:.3f}"
    )
    recall20 = (
        "n/a" if summary.must_find_recall_at_20 is None else f"{summary.must_find_recall_at_20:.3f}"
    )
    print("\nSCENARIO SUMMARY")
    print(f"  Passed (all checks):      {summary.passed}/{summary.total_queries}")
    print(f"  Hard-filter contract:     {summary.hard_filter_contract_rate:.3f}")
    print(f"  Result hard-filters:      {summary.result_hard_filter_rate:.3f}")
    print(f"  Topic covered:            {summary.topic_coverage_rate:.3f}")
    print(f"  Source coverage:          {summary.source_coverage_rate:.3f}")
    print(f"  Alternate coverage:       {summary.alternate_coverage_rate:.3f}")
    print(f"  Must-find recall@10:      {recall10}")
    print(f"  Must-find recall@20:      {recall20}")
    print(f"  Avg latency (ms):         {summary.average_latency_ms:.2f}")
    print(f"  Estimated cost (USD):     {summary.estimated_cost_usd_total:.6f}")
    print(f"  Source usage:             {summary.source_usage_count}")

    return ScenarioResult(config=config, results=results, summary=summary)


def _print_flag_delta_summary(scenarios: list[ScenarioResult]) -> None:
    if len(scenarios) <= 1:
        return
    base = scenarios[0].summary
    print("\nFLAG DELTAS VS DEFAULT")
    for scenario in scenarios[1:]:
        recall20_delta = None
        if (
            base.must_find_recall_at_20 is not None
            and scenario.summary.must_find_recall_at_20 is not None
        ):
            recall20_delta = scenario.summary.must_find_recall_at_20 - base.must_find_recall_at_20
        recall20_text = "n/a" if recall20_delta is None else f"{recall20_delta:+.3f}"
        print(
            f"  {scenario.config.name:<18} recall@20={recall20_text:<7} "
            f"hard-filter={scenario.summary.hard_filter_contract_rate:.3f} "
            f"avg_latency_ms={scenario.summary.average_latency_ms:.2f}"
        )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


async def _run(
    *,
    output_json: str | None,
    verbose: bool,
    measure_flags: bool,
    compare_baseline: str | None,
) -> int:
    normalize_strict_settings_env()
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": resolve_xai_key(),
        "AGT_ZOTERO_API_KEY": default_zotero_api_key(),
        "AGT_ZOTERO_LIBRARY_ID": default_zotero_library_id(),
        "AGT_SEMANTIC_SCHOLAR_API_KEY": resolve_env_key(
            "AGT_SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"
        ),
        "AGT_SUMMARIZATION_USE_LLM": False,
        "AGT_SEMANTIC_SCHOLAR_LIMIT": RESULT_LIMIT,
    })
    configure_guardrails(settings)

    print("=" * 80)
    print("AGT-29 — Retrieval Quality Benchmark")
    print(f"Panel size: {len(PANEL)} queries | keyless-first mode | top_k={RESULT_LIMIT}")
    print("=" * 80)

    scenarios = [
        ScenarioConfig(
            name="default",
            description="Keyless-first default retrieval surface",
            settings_overrides={},
        )
    ]
    if measure_flags:
        scenarios.extend([
            ScenarioConfig(
                name="flag_keybert",
                description="Enable AGT_USE_KEYBERT only",
                settings_overrides={"use_keybert": True},
            ),
            ScenarioConfig(
                name="flag_reranker",
                description="Enable AGT_USE_RERANKER only",
                settings_overrides={"use_reranker": True},
            ),
        ])

    scenario_results = [
        await _run_scenario(scenario, settings, verbose=verbose) for scenario in scenarios
    ]
    _print_flag_delta_summary(scenario_results)

    baseline_comparisons: list[dict[str, Any]] = []
    if compare_baseline is not None:
        baseline_path = Path(compare_baseline)
        baseline = _load_baseline_artifact(baseline_path)
        comparison = _compare_scenario_to_baseline(scenario_results[0], baseline)
        baseline_comparisons.append(comparison)
        below_baseline = comparison["below_baseline"]
        print("\nBASELINE COMPARISON")
        print(
            f"  Baseline: {comparison['baseline_name']} ({comparison.get('baseline_version') or 'n/a'})"
        )
        print(
            f"  Queries meeting/exceeding baseline: {comparison['matched_or_exceeded']}/{scenario_results[0].summary.total_queries}"
        )
        if below_baseline:
            print("  Queries below baseline:")
            for item in below_baseline:
                print(f"    - {item['query_id']}: {item['metrics']}")

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    default_summary = scenario_results[0].summary
    recall10 = (
        "n/a"
        if default_summary.must_find_recall_at_10 is None
        else f"{default_summary.must_find_recall_at_10:.3f}"
    )
    recall20 = (
        "n/a"
        if default_summary.must_find_recall_at_20 is None
        else f"{default_summary.must_find_recall_at_20:.3f}"
    )
    print(f"  Total queries:            {default_summary.total_queries}")
    print(f"  Passed (all checks):      {default_summary.passed}/{default_summary.total_queries}")
    print(f"  Hard-filter contract:     {default_summary.hard_filter_contract_rate:.3f}")
    print(f"  Topic covered:            {default_summary.topic_coverage_rate:.3f}")
    print(f"  Source coverage:          {default_summary.source_coverage_rate:.3f}")
    print(f"  Must-find recall@10:      {recall10}")
    print(f"  Must-find recall@20:      {recall20}")
    print(f"  Avg latency (ms):         {default_summary.average_latency_ms:.2f}")
    print(f"  Estimated cost (USD):     {default_summary.estimated_cost_usd_total:.6f}")

    if output_json:
        report = _build_json_report(scenario_results, baseline_comparisons)
        Path(output_json).write_text(json.dumps(report, indent=2))
        print(f"\n  JSON report written to: {output_json}")

    baseline_regression = any(comparison["below_baseline"] for comparison in baseline_comparisons)
    rc = 0 if default_summary.hard_filter_contract_rate == 1.0 and not baseline_regression else 1
    print(
        f"\n  Exit code: {rc} ({'OK — hard filters preserved and baseline met' if rc == 0 else 'WARN — benchmark contract regression detected'})"
    )
    return rc


def main() -> None:
    parser = argparse.ArgumentParser(description="AGT-29 retrieval quality benchmark")
    parser.add_argument("--output-json", metavar="PATH", help="Write JSON report to this path")
    parser.add_argument("--verbose", action="store_true", help="Print per-query plan details")
    parser.add_argument(
        "--measure-flags",
        action="store_true",
        help="Run opt-in feature-flag scenarios against the same panel",
    )
    parser.add_argument(
        "--compare-baseline",
        metavar="PATH",
        default=str(DEFAULT_MANUAL_BASELINE_PATH)
        if DEFAULT_MANUAL_BASELINE_PATH.exists()
        else None,
        help="Compare the default scenario against a checked-in reviewed baseline artifact",
    )
    args = parser.parse_args()

    raise SystemExit(
        asyncio.run(
            _run(
                output_json=args.output_json,
                verbose=args.verbose,
                measure_flags=args.measure_flags,
                compare_baseline=args.compare_baseline,
            )
        )
    )


if __name__ == "__main__":
    main()
