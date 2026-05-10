# pyright: reportPrivateUsage=false

from __future__ import annotations

import sys
from pathlib import Path

from agt.models import HardFilters, NormalizedPaper, SearchPlan, SoftPreferences, SourceCapability
from agt.tools.query_constraints import parse_query_constraints

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import examples.m2_7_benchmark as benchmark


def _sample_entry() -> benchmark.PanelEntry:
    return benchmark.PanelEntry(
        query_id="TEST-01",
        query="retrieval augmented generation survey",
        domain="AI",
        expected_topic_tokens=["retrieval"],
        min_year=2024,
        open_access_required=True,
        min_citations=10,
        expected_sources=["semantic_scholar"],
        must_find=[
            benchmark.MustFindTarget(
                label="Anchor",
                doi="10.1234/anchor",
                title_fragments=["anchor paper"],
            )
        ],
        acceptable_alternate_fragments=["anchor"],
    )


def test_panel_has_expected_coverage_shape() -> None:
    assert len(benchmark.PANEL) >= benchmark._MIN_PANEL_SIZE
    assert all(entry.expected_sources for entry in benchmark.PANEL)
    assert all(entry.must_find or entry.acceptable_alternate_fragments for entry in benchmark.PANEL)
    assert (
        sum(len(entry.must_find) for entry in benchmark.PANEL) >= benchmark._MIN_MUST_FIND_TARGETS
    )


def test_paper_matches_target_uses_doi_first() -> None:
    paper = NormalizedPaper(
        title="Completely different title",
        doi="https://doi.org/10.1234/anchor",
        abstract="No title fragment overlap",
    )
    target = benchmark.MustFindTarget(
        label="Anchor",
        doi="10.1234/anchor",
        title_fragments=["anchor paper"],
    )

    assert benchmark._paper_matches_target(paper, target)


def test_check_search_plan_contract_reports_mismatches() -> None:
    entry = _sample_entry()
    plan = SearchPlan(
        original_query=entry.query,
        topic_query=entry.query,
        rewritten_queries=[entry.query],
        hard_filters=HardFilters(min_year=2023, open_access_only=False, min_citations=5),
        soft_preferences=SoftPreferences(),
        source_policy=[SourceCapability(name="semantic_scholar", tier="primary", enabled=True)],
    )

    mismatches = benchmark._check_search_plan_contract(plan, entry)

    assert "min_year=2023 expected=2024" in mismatches
    assert "open_access_only=False expected=True" in mismatches
    assert "min_citations=5 expected>=10" in mismatches


def test_check_expected_source_coverage_normalizes_tier_suffixes() -> None:
    entry = _sample_entry()

    missing = benchmark._check_expected_source_coverage(
        ["semantic_scholar:primary"],
        entry,
    )

    assert missing == []


def test_panel_queries_align_with_expected_hard_filters() -> None:
    for entry in benchmark.PANEL:
        constraints = parse_query_constraints(
            entry.query,
            default_limit=benchmark.RESULT_LIMIT,
        )

        assert constraints.year.min_year == entry.min_year
        assert constraints.year.max_year == entry.max_year
        assert constraints.quality.open_access_only is entry.open_access_required
        assert constraints.citations.min_citations == entry.min_citations


def test_build_json_report_includes_recall_and_comparison_metrics() -> None:
    entry = _sample_entry()
    result = benchmark.EntryResult(
        entry=entry,
        papers=[
            NormalizedPaper(
                title="Anchor paper for retrieval",
                doi="10.1234/anchor",
                year=2024,
                citation_count=25,
                open_access=True,
                source="semantic_scholar",
            )
        ],
        plan=SearchPlan(
            original_query=entry.query,
            topic_query=entry.query,
            rewritten_queries=[entry.query],
            hard_filters=HardFilters(min_year=2024, open_access_only=True, min_citations=10),
            soft_preferences=SoftPreferences(),
            source_policy=[SourceCapability(name="semantic_scholar", tier="primary", enabled=True)],
        ),
        sources_used=["semantic_scholar"],
        sources_failed=[],
        year_violations=0,
        oa_violations=0,
        citation_violations=0,
        topic_covered=True,
        alternate_covered=True,
        must_find_hits_at_10=["Anchor"],
        must_find_hits_at_20=["Anchor"],
        must_find_missing_at_20=[],
        expected_sources_missing=[],
        plan_filter_mismatches=[],
        latency_ms=12.5,
        estimated_cost_usd=0.0,
    )
    scenario = benchmark.ScenarioResult(
        config=benchmark.ScenarioConfig(
            name="default",
            description="default",
            settings_overrides={},
        ),
        results=[result],
        summary=benchmark._summarize_results([result]),
    )

    report = benchmark._build_json_report(
        [scenario],
        [
            {
                "baseline_name": "manual",
                "baseline_version": "v1",
                "scenario": "default",
                "matched_or_exceeded": 1,
                "below_baseline": [],
            }
        ],
    )

    assert report["benchmark_version"] == benchmark.BENCHMARK_VERSION
    assert report["scenarios"][0]["summary"]["must_find_recall_at_10"] == 1.0
    assert report["scenarios"][0]["summary"]["hard_filter_contract_rate"] == 1.0
    assert report["baseline_comparisons"][0]["baseline_name"] == "manual"


def test_compare_scenario_to_baseline_flags_regressions() -> None:
    entry = _sample_entry()
    result = benchmark.EntryResult(
        entry=entry,
        papers=[],
        plan=None,
        sources_used=[],
        sources_failed=[],
        year_violations=1,
        oa_violations=0,
        citation_violations=0,
        topic_covered=False,
        alternate_covered=False,
        must_find_hits_at_10=[],
        must_find_hits_at_20=[],
        must_find_missing_at_20=["Anchor"],
        expected_sources_missing=["semantic_scholar"],
        plan_filter_mismatches=["missing_search_plan"],
        latency_ms=100.0,
        estimated_cost_usd=0.0,
    )
    scenario = benchmark.ScenarioResult(
        config=benchmark.ScenarioConfig(
            name="default",
            description="default",
            settings_overrides={},
        ),
        results=[result],
        summary=benchmark._summarize_results([result]),
    )
    baseline = {
        "baseline_name": "manual",
        "baseline_version": "v1",
        "entries": [
            {
                "query_id": "TEST-01",
                "minimum_recall_at_10": 1.0,
                "minimum_recall_at_20": 1.0,
                "requires_hard_filter_contract": True,
                "requires_source_coverage": True,
            }
        ],
    }

    comparison = benchmark._compare_scenario_to_baseline(scenario, baseline)

    assert comparison["matched_or_exceeded"] == 0
    assert comparison["below_baseline"][0]["query_id"] == "TEST-01"
    assert set(comparison["below_baseline"][0]["metrics"]) == {
        "recall_at_10",
        "recall_at_20",
        "hard_filter_contract",
        "source_coverage",
    }
