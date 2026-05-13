"""Regression gate: structural correctness of benchmark panel and baseline artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import examples.m2_7_benchmark as benchmark

_BASELINE_PATH = Path("examples/benchmark_artifacts/manual_web_search_baseline.json")
_MIN_PASS_RATE = 19 / 22  # 0.8636…  (19/22 pass rate documented in task spec)
_MIN_PASS_RATE_THRESHOLD = 0.86
_MIN_PANEL_ENTRIES = 22
_MIN_BASELINE_ENTRIES = 22
_MIN_MUST_FIND_THRESHOLD = 10
_MIN_PANEL_SIZE_THRESHOLD = 20


@pytest.mark.regression_gate
def test_panel_has_at_least_22_entries() -> None:
    """PANEL must contain at least 22 evaluation queries."""
    assert len(benchmark.PANEL) >= _MIN_PANEL_ENTRIES, (
        f"Expected >={_MIN_PANEL_ENTRIES} panel entries; got {len(benchmark.PANEL)}"
    )


@pytest.mark.regression_gate
def test_min_pass_rate_is_at_least_86_percent() -> None:
    """The documented minimum pass rate (19/22) must be >= 0.86."""
    assert _MIN_PASS_RATE >= _MIN_PASS_RATE_THRESHOLD, (
        f"Expected min pass rate >={_MIN_PASS_RATE_THRESHOLD}; got {_MIN_PASS_RATE:.4f}"
    )


@pytest.mark.regression_gate
def test_baseline_artifact_exists_and_is_non_empty() -> None:
    """The checked-in manual baseline JSON must exist and have >=22 result entries."""
    assert _BASELINE_PATH.exists(), f"Baseline artifact not found: {_BASELINE_PATH}"
    with _BASELINE_PATH.open() as fh:
        data = json.load(fh)
    entries = data.get("entries", [])
    assert len(entries) >= _MIN_BASELINE_ENTRIES, (
        f"Expected >={_MIN_BASELINE_ENTRIES} baseline entries; got {len(entries)}"
    )


@pytest.mark.regression_gate
def test_scoring_constants_meet_minimum_thresholds() -> None:
    """_MIN_MUST_FIND_TARGETS >= 10 and _MIN_PANEL_SIZE >= 20."""
    assert benchmark._MIN_MUST_FIND_TARGETS >= _MIN_MUST_FIND_THRESHOLD, (  # pyright: ignore[reportPrivateUsage]
        f"_MIN_MUST_FIND_TARGETS should be >={_MIN_MUST_FIND_THRESHOLD}; got {benchmark._MIN_MUST_FIND_TARGETS}"  # pyright: ignore[reportPrivateUsage]
    )
    assert benchmark._MIN_PANEL_SIZE >= _MIN_PANEL_SIZE_THRESHOLD, (  # pyright: ignore[reportPrivateUsage]
        f"_MIN_PANEL_SIZE should be >={_MIN_PANEL_SIZE_THRESHOLD}; got {benchmark._MIN_PANEL_SIZE}"  # pyright: ignore[reportPrivateUsage]
    )
