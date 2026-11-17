from __future__ import annotations

import unittest
from pathlib import Path

from papertrading.autonomy import (
    AutonomyPolicy,
    average_true_range,
    plan_position,
    portfolio_halt,
    stop_price,
    trailing_stop,
)
from papertrading.data import Bar

ROOT = Path(__file__).resolve().parents[1]


def bars(count: int = 16) -> list[Bar]:
    return [
        Bar(
            date=f"2026-01-{i + 1:02d}",
            open=100.0,
            high=102.0,
            low=98.0,
            close=100.0,
            volume=1000,
        )
        for i in range(count)
    ]


class AutonomyPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = AutonomyPolicy.load(ROOT / "config" / "autonomy.json")

    def test_public_policy_loads_and_gates_modes(self):
        self.assertEqual(self.policy.max_new_buys_per_day, 2)
        self.assertEqual(self.policy.max_position_pct, 0.10)
        self.assertEqual(self.policy.per_trade_risk_pct, 0.01)
        self.assertEqual(self.policy.modes["delivery"]["status"], "enabled")
        self.assertEqual(self.policy.modes["intraday"]["status"], "paused")
        self.assertEqual(self.policy.modes["futures"]["status"], "paused")
        self.assertEqual(self.policy.modes["options"]["status"], "paused")

    def test_average_true_range_uses_latest_complete_window(self):
        self.assertEqual(average_true_range(bars(), 14), 4.0)
        self.assertIsNone(average_true_range(bars(14), 14))

    def test_stop_is_atr_based_and_bounded(self):
        stop = stop_price(100.0, bars(), self.policy)
        self.assertAlmostEqual(stop, 94.0)  # 1.5 * ATR 4 = 6%
        self.assertGreaterEqual(stop, 92.0)
        self.assertLessEqual(stop, 96.0)

    def test_position_plan_respects_risk_position_and_daily_caps(self):
        plan = plan_position(
            "TEST",
            100.0,
            bars(),
            self.policy,
            equity=100000.0,
            cash=100000.0,
            deployed_today_inr=15000.0,
        )
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.qty, 50)  # Rs 5,000 daily room remains
        self.assertLessEqual(plan.risk_inr, 1000.0)
        self.assertLessEqual(plan.exposure_inr, 10000.0)

    def test_position_plan_returns_none_when_limits_reached(self):
        self.assertIsNone(plan_position(
            "TEST", 100.0, bars(), self.policy,
            equity=100000.0, cash=100000.0, buys_today=2,
        ))
        self.assertIsNone(plan_position(
            "TEST", 100.0, bars(), self.policy,
            equity=100000.0, cash=100000.0, open_positions=4,
        ))

    def test_trailing_stop_never_moves_down(self):
        raised = trailing_stop(94.0, 110.0, bars(), self.policy)
        self.assertGreaterEqual(raised, 94.0)
        self.assertEqual(trailing_stop(104.0, 100.0, bars(), self.policy), 104.0)

    def test_overall_halt_threshold(self):
        self.assertFalse(portfolio_halt(100000.0, 60000.01, 40000.0))
        self.assertTrue(portfolio_halt(100000.0, 60000.0, 40000.0))
        self.assertTrue(portfolio_halt(100000.0, 59000.0, 40000.0))


if __name__ == "__main__":
    unittest.main()
