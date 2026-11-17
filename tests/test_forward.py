from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from papertrading.autonomy import AutonomyPolicy
from papertrading.data import Bar
from papertrading.forward import ForwardState, load_verified_state, prepare_forward_plan

ROOT = Path(__file__).resolve().parents[1]


def crossover_bars(count: int = 61) -> list[Bar]:
    bars = []
    start = date(2026, 9, 1)
    for index in range(count):
        close = 100.0
        if index == count - 2:
            close = 90.0
        elif index == count - 1:
            close = 300.0
        bars.append(Bar(
            date=(start + timedelta(days=index)).isoformat(),
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=1000,
        ))
    return bars


def flat_bars(count: int = 61) -> list[Bar]:
    start = date(2026, 9, 1)
    return [
        Bar(
            date=(start + timedelta(days=index)).isoformat(),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000,
        )
        for index in range(count)
    ]


class ForwardPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = AutonomyPolicy.load(ROOT / "config" / "autonomy.json")
        cls.state = ForwardState(
            as_of="2026-11-13",
            cash_inr=100000.0,
            positions={},
            source="tests",
        )

    def test_prepares_gap_labelled_buy_without_logging_or_execution(self):
        plan = prepare_forward_plan(
            {"TEST": crossover_bars()},
            self.state,
            self.policy,
            decision_date="2026-11-17",
            data_through="2026-10-31",
        )
        self.assertEqual(plan["status"], "prepared_not_executed")
        self.assertEqual(plan["gap"]["missing_checkpoint_date"], "2026-11-16")
        self.assertEqual(len(plan["decisions"]), 1)
        decision = plan["decisions"][0]
        self.assertEqual(decision["symbol"], "TEST")
        self.assertEqual(decision["side"], "buy")
        self.assertEqual(decision["date"], "2026-11-17")
        self.assertIn("not appended to decisions/log.csv", plan["not_done"])

    def test_no_latest_crossover_is_valid_no_trade(self):
        plan = prepare_forward_plan(
            {"TEST": flat_bars()},
            self.state,
            self.policy,
            decision_date="2026-11-17",
            data_through="2026-10-31",
        )
        self.assertEqual(plan["decisions"], [])
        self.assertIn("no crossover signal", plan["notes"][0])

    def test_rejects_same_day_data_for_no_lookahead_boundary(self):
        with self.assertRaisesRegex(ValueError, "after data_through"):
            prepare_forward_plan(
                {"TEST": flat_bars()},
                self.state,
                self.policy,
                decision_date="2026-10-30",
                data_through="2026-10-31",
            )

    def test_open_position_requires_current_bar(self):
        state = ForwardState("2026-11-13", 1000.0, {"TEST": 1}, "tests")
        with self.assertRaisesRegex(ValueError, "open positions"):
            prepare_forward_plan(
                {},
                state,
                self.policy,
                decision_date="2026-11-17",
                data_through="2026-10-31",
            )

    def test_loads_verified_state_from_public_app_bundle(self):
        state = load_verified_state(ROOT / "app" / "data" / "exp001.json")
        self.assertEqual(state.as_of, "2026-11-13")
        self.assertAlmostEqual(state.cash_inr, 3264.68)
        self.assertEqual(state.positions["ADANIPORTS"], 14)
        self.assertEqual(state.positions["TECHM"], 14)
        self.assertEqual(state.positions["BSE"], 7)
        self.assertEqual(state.positions["DRREDDY"], 21)


if __name__ == "__main__":
    unittest.main()

class ForwardManifestTests(unittest.TestCase):
    def test_committed_2026_11_17_preparation_is_honest(self):
        manifest = json.loads((ROOT / "experiments" / "forward-prep-2026-11-17.json").read_text())
        self.assertEqual(manifest["status"], "prepared_not_executed")
        self.assertEqual(manifest["decision_date"], "2026-11-17")
        self.assertEqual(manifest["data_through"], "2026-11-16")
        self.assertEqual(manifest["gap"]["missing_checkpoint_date"], "2026-11-16")
        self.assertEqual(manifest["decisions"], [])
        self.assertEqual(manifest["planning_equity_inr_reconstructed"], 110783.98)
        self.assertIn("not appended to decisions/log.csv", manifest["not_done"])
        self.assertIn("not a repaired 2026-11-16 checkpoint", manifest["not_done"])
