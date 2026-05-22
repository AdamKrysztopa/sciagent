from __future__ import annotations

import pytest

from agt.guardrails import SharedBudgetExhaustedError, SharedBudgetTracker


class TestSharedBudgetTracker:
    def test_record_cost_under_budget(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=2.00)
        tracker.record_cost("alice", 0.50)
        assert tracker.get_spend("alice") == pytest.approx(0.50)  # pyright: ignore[reportUnknownMemberType]

    def test_record_cost_exceeds_budget_raises(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=1.00)
        tracker.record_cost("alice", 0.80)
        with pytest.raises(SharedBudgetExhaustedError):
            tracker.record_cost("alice", 0.30)

    def test_per_user_budget_override(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=1.00)
        tracker.record_cost("alice", 0.80, budget_override=5.00)
        tracker.record_cost("alice", 0.80, budget_override=5.00)  # total 1.60, under 5.00
        assert tracker.get_spend("alice") == pytest.approx(1.60)  # pyright: ignore[reportUnknownMemberType]

    def test_separate_user_budgets(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=1.00)
        tracker.record_cost("alice", 0.90)
        tracker.record_cost("bob", 0.90)  # bob has his own budget
        assert tracker.get_spend("alice") == pytest.approx(0.90)  # pyright: ignore[reportUnknownMemberType]
        assert tracker.get_spend("bob") == pytest.approx(0.90)  # pyright: ignore[reportUnknownMemberType]

    def test_get_spend_unknown_user(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=2.00)
        assert tracker.get_spend("unknown") == 0.0

    def test_get_all_usage(self) -> None:
        tracker = SharedBudgetTracker(default_budget_usd=2.00)
        tracker.record_cost("alice", 0.50)
        tracker.record_cost("bob", 1.20)
        tracker.record_request("alice")
        tracker.record_request("alice")
        tracker.record_request("bob")
        usage = tracker.get_all_usage(default_budget=2.00)
        assert usage["alice"]["spend_usd"] == pytest.approx(0.50)  # pyright: ignore[reportUnknownMemberType]
        assert usage["alice"]["requests"] == 2  # noqa: PLR2004
        assert usage["bob"]["spend_usd"] == pytest.approx(1.20)  # pyright: ignore[reportUnknownMemberType]
