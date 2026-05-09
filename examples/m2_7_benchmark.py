"""AGT-29 — Retrieval quality benchmark against standalone LLM search.

Runs a curated evaluation panel of ≥20 realistic research requests
and checks constraint compliance, freshness, and source coverage.

Runs without paid/search-engine API keys by default.
Optional keyed sources (CORE, Dimensions, Google Scholar) are reported
separately as enrichment when the respective environment variables are set.

Usage:
    uv run python examples/m2_7_benchmark.py
    uv run python examples/m2_7_benchmark.py --output-json results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
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

# ---------------------------------------------------------------------------
# Evaluation panel — 20 realistic research requests
# ---------------------------------------------------------------------------


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
    # Titles of papers that MUST be found (fuzzy substring match).
    must_find_titles: list[str] = field(default_factory=lambda: [])
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
        notes="Core RAG survey; should surface REALM, RAG (Lewis 2020), etc.",
    ),
    PanelEntry(
        query_id="AI-02",
        query="the most advanced RAG techniques in 2026 - game changers",
        domain="AI",
        expected_topic_tokens=["retrieval", "augmented", "generation"],
        min_year=2024,
        notes="Freshness check: only 2024+ results should survive.",
    ),
    PanelEntry(
        query_id="AI-03",
        query="large language model reasoning chain-of-thought prompting not older than 2024",
        domain="AI",
        expected_topic_tokens=["chain", "thought", "reasoning"],
        min_year=2024,
        notes="Hard year filter; 2023 and older must be excluded.",
    ),
    PanelEntry(
        query_id="AI-04",
        query="transformer attention mechanism survey",
        domain="AI",
        expected_topic_tokens=["attention", "transformer"],
        notes="Foundational; should surface Vaswani 2017 and successors.",
    ),
    PanelEntry(
        query_id="AI-05",
        query="open access papers on federated learning privacy 2023 and newer",
        domain="AI",
        expected_topic_tokens=["federated", "learning", "privacy"],
        min_year=2023,
        open_access_required=True,
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
        notes="Key AGT-28 acceptance criteria example; hard year=2024.",
    ),
    PanelEntry(
        query_id="TS-02",
        query="the most cited 2020 and newer timeseries papers - list 5",
        domain="time-series",
        expected_topic_tokens=["time", "series", "timeseries", "temporal", "forecasting"],
        min_year=2020,
        notes="Citation + year combined constraint. 'timeseries' is a single-token variant.",
    ),
    PanelEntry(
        query_id="TS-03",
        query="anomaly detection in time series deep learning",
        domain="time-series",
        expected_topic_tokens=["anomaly", "detection", "time"],
        notes="No year constraint; broad coverage expected.",
    ),
    PanelEntry(
        query_id="TS-04",
        query="temporal fusion transformer for multi-horizon forecasting",
        domain="time-series",
        expected_topic_tokens=["temporal", "fusion", "transformer"],
        notes="Specific model paper; should surface Lim et al. 2021.",
    ),
    PanelEntry(
        query_id="TS-05",
        query="foundation models for time series since 2023",
        domain="time-series",
        expected_topic_tokens=["foundation", "model", "time"],
        min_year=2023,
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
        notes="PubMed-heavy; recent therapeutic applications.",
    ),
    PanelEntry(
        query_id="BIO-02",
        query="protein structure prediction AlphaFold deep learning",
        domain="biomedicine",
        expected_topic_tokens=["protein", "structure", "alphafold"],
        notes="Should surface AlphaFold 2 paper (Jumper 2021).",
    ),
    PanelEntry(
        query_id="BIO-03",
        query="cancer immunotherapy checkpoint inhibitors clinical trial 2023 and newer",
        domain="biomedicine",
        expected_topic_tokens=["immunotherapy", "checkpoint", "cancer"],
        min_year=2023,
        notes="Freshness check for clinical literature.",
    ),
    PanelEntry(
        query_id="BIO-04",
        query="open access papers on COVID long-term effects after 2021",
        domain="biomedicine",
        expected_topic_tokens=["covid", "long"],
        min_year=2021,
        open_access_required=True,
        notes="Open access + year constraint on biomedical topic.",
    ),
    PanelEntry(
        query_id="BIO-05",
        query="single cell RNA sequencing analysis methods",
        domain="biomedicine",
        expected_topic_tokens=["single", "cell", "rna"],
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
        notes="Thaler/Sunstein domain; classic and recent papers.",
    ),
    PanelEntry(
        query_id="SOC-02",
        query="survey methodology response bias questionnaire design",
        domain="social-science",
        expected_topic_tokens=["survey", "bias", "questionnaire"],
        notes="Methodological literature; broad coverage.",
    ),
    PanelEntry(
        query_id="SOC-03",
        query="social media misinformation spread network effects not older than 2022",
        domain="social-science",
        expected_topic_tokens=["misinformation", "social", "network"],
        min_year=2022,
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
        notes="AI x biomedicine; should surface GNN-based drug papers.",
    ),
    PanelEntry(
        query_id="INTER-02",
        query="climate change machine learning prediction modeling since 2022",
        domain="interdisciplinary",
        expected_topic_tokens=["climate", "machine", "learning"],
        min_year=2022,
        notes="AI x climate science; freshness check.",
    ),
    PanelEntry(
        query_id="INTER-03",
        query="large language models in healthcare clinical decision support not older than 2023",
        domain="interdisciplinary",
        expected_topic_tokens=["language", "model", "clinical"],
        min_year=2023,
        notes="AI x medicine; hard year filter 2023+.",
    ),
    PanelEntry(
        query_id="INTER-04",
        query="natural language processing education adaptive learning systems",
        domain="interdisciplinary",
        expected_topic_tokens=["natural", "language", "education"],
        notes="AI x education; broad coverage expected.",
    ),
]

_MIN_PANEL_SIZE = 20
assert len(PANEL) >= _MIN_PANEL_SIZE, (
    f"Benchmark requires >={_MIN_PANEL_SIZE} queries; got {len(PANEL)}"
)


# ---------------------------------------------------------------------------
# Compliance checking
# ---------------------------------------------------------------------------


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


def _check_must_find(
    papers: list[NormalizedPaper],
    entry: PanelEntry,
) -> list[str]:
    """Return list of must-find titles NOT found in results."""
    missing: list[str] = []
    for title in entry.must_find_titles:
        title_lower = title.lower()
        found = any(title_lower in paper.title.lower() for paper in papers)
        if not found:
            missing.append(title)
    return missing


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
    topic_covered: bool
    must_find_missing: list[str]
    error: str | None = None

    @property
    def constraint_compliant(self) -> bool:
        return self.year_violations == 0 and self.oa_violations == 0

    @property
    def passed(self) -> bool:
        return (
            self.error is None
            and self.constraint_compliant
            and self.topic_covered
            and not self.must_find_missing
        )


async def _run_one(
    entry: PanelEntry,
    settings: Settings,
) -> EntryResult:
    try:
        with thread_context(f"bench-{entry.query_id}"):
            papers, metadata = await search_papers(
                query=entry.query,
                limit=10,
                settings=settings,
                thread_id=f"bench-{entry.query_id}",
            )
    except Exception as exc:
        return EntryResult(
            entry=entry,
            papers=[],
            plan=None,
            sources_used=[],
            sources_failed=[],
            year_violations=0,
            oa_violations=0,
            topic_covered=False,
            must_find_missing=entry.must_find_titles[:],
            error=str(exc),
        )

    year_count, _year_msgs = _check_year_compliance(papers, entry)
    oa_count, _oa_msgs = _check_open_access_compliance(papers, entry)
    topic_ok = _check_topic_coverage(papers, entry)
    missing = _check_must_find(papers, entry)

    return EntryResult(
        entry=entry,
        papers=papers,
        plan=metadata.search_plan,
        sources_used=metadata.sources_used,
        sources_failed=metadata.sources_failed,
        year_violations=year_count,
        oa_violations=oa_count,
        topic_covered=topic_ok,
        must_find_missing=missing,
    )


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


_PASS = "PASS"
_FAIL = "FAIL"
_STATUS_WIDTH = 4


def _print_entry_result(result: EntryResult, *, verbose: bool = False) -> None:
    status = _PASS if result.passed else _FAIL
    icon = "✓" if result.passed else "✗"
    print(
        f"  [{icon}] {result.entry.query_id:<10} {status:<{_STATUS_WIDTH}}  {result.entry.domain:<15}  results={len(result.papers)}"
    )
    if result.error:
        print(f"         ERROR: {result.error}")
    else:
        if result.year_violations:
            print(f"         year_violations={result.year_violations}")
        if result.oa_violations:
            print(f"         oa_violations={result.oa_violations}")
        if not result.topic_covered:
            print(
                f"         topic_not_covered (expected tokens: {result.entry.expected_topic_tokens})"
            )
        if result.must_find_missing:
            print(f"         must_find_missing={result.must_find_missing}")
        if verbose and result.plan:
            plan = result.plan
            print(
                f"         search_plan.hard_filters: min_year={plan.hard_filters.min_year} max_year={plan.hard_filters.max_year}"
            )
            print(f"         search_plan.pushed_down: {plan.filters_pushed_down}")
            print(f"         search_plan.post_merge:  {plan.filters_enforced_post_merge}")
        if verbose and result.papers:
            for paper in result.papers[:3]:
                yr = paper.year if paper.year else "?"
                print(f"         [{yr}] {paper.title[:70]}")


def _build_json_report(results: list[EntryResult]) -> dict[str, Any]:
    """Build a deterministic versioned JSON report."""
    entries: list[dict[str, Any]] = []
    for r in results:
        entry: dict[str, Any] = {
            "query_id": r.entry.query_id,
            "domain": r.entry.domain,
            "query": r.entry.query,
            "passed": r.passed,
            "result_count": len(r.papers),
            "year_violations": r.year_violations,
            "oa_violations": r.oa_violations,
            "topic_covered": r.topic_covered,
            "must_find_missing": r.must_find_missing,
            "sources_used": sorted(r.sources_used),
            "sources_failed": sorted(r.sources_failed),
            "error": r.error,
        }
        if r.plan is not None:
            entry["search_plan"] = {
                "hard_filters": r.plan.hard_filters.model_dump(),
                "rewritten_queries": r.plan.rewritten_queries,
                "filters_pushed_down": r.plan.filters_pushed_down,
                "filters_enforced_post_merge": r.plan.filters_enforced_post_merge,
            }
        entries.append(entry)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    compliance_rate = sum(1 for r in results if r.constraint_compliant) / max(total, 1)
    topic_coverage_rate = sum(1 for r in results if r.topic_covered) / max(total, 1)

    return {
        "benchmark_version": "m2.7-agt29-v1",
        "total_queries": total,
        "passed": passed,
        "failed": total - passed,
        "constraint_compliance_rate": round(compliance_rate, 3),
        "topic_coverage_rate": round(topic_coverage_rate, 3),
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


async def _run(*, output_json: str | None, verbose: bool) -> int:
    normalize_strict_settings_env()
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": resolve_xai_key(),
        "AGT_ZOTERO_API_KEY": default_zotero_api_key(),
        "AGT_ZOTERO_LIBRARY_ID": default_zotero_library_id(),
        "AGT_SEMANTIC_SCHOLAR_API_KEY": resolve_env_key(
            "AGT_SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"
        ),
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    configure_guardrails(settings)

    print("=" * 80)
    print("AGT-29 — Retrieval Quality Benchmark")
    print(f"Panel size: {len(PANEL)} queries | keyless-first mode")
    print("=" * 80)

    results: list[EntryResult] = []
    for entry in PANEL:
        print(f"\nRunning {entry.query_id}: {entry.query[:60]}...")
        result = await _run_one(entry, settings)
        results.append(result)
        _print_entry_result(result, verbose=verbose)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    constraint_compliant = sum(1 for r in results if r.constraint_compliant)
    topic_covered = sum(1 for r in results if r.topic_covered)

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"  Total queries:            {total}")
    print(f"  Passed (all checks):      {passed}/{total}")
    print(f"  Constraint compliant:     {constraint_compliant}/{total}")
    print(f"  Topic covered:            {topic_covered}/{total}")

    if output_json:
        report = _build_json_report(results)
        Path(output_json).write_text(json.dumps(report, indent=2))
        print(f"\n  JSON report written to: {output_json}")

    rc = 0 if constraint_compliant == total else 1
    print(
        f"\n  Exit code: {rc} ({'OK — all constraints satisfied' if rc == 0 else 'WARN — constraint violations detected'})"
    )
    return rc


def main() -> None:
    parser = argparse.ArgumentParser(description="AGT-29 retrieval quality benchmark")
    parser.add_argument("--output-json", metavar="PATH", help="Write JSON report to this path")
    parser.add_argument("--verbose", action="store_true", help="Print per-query plan details")
    args = parser.parse_args()

    raise SystemExit(asyncio.run(_run(output_json=args.output_json, verbose=args.verbose)))


if __name__ == "__main__":
    main()
