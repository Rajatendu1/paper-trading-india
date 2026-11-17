from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data" / "exp001.json"


class AppDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["python3", "scripts/build_app_data.py"], cwd=ROOT, check=True)
        cls.data = json.loads(DATA.read_text())

    def test_verified_summary_values(self):
        summary = self.data["summary"]
        self.assertEqual(summary["starting_capital_inr"], 100000.0)
        self.assertEqual(summary["final_equity_inr"], 111150.78)
        self.assertEqual(summary["total_return_pct"], 11.15)
        self.assertEqual(summary["max_drawdown_inr"], 14627.16)
        self.assertEqual(summary["trades_executed"], 96)
        self.assertEqual(summary["skipped_decisions"], 86)
        self.assertEqual(summary["benchmark_nifty50_return_pct"], 27.8)
        self.assertEqual(summary["cash_inr"], 3264.68)

    def test_terminal_decomposition_recomposes(self):
        summary = self.data["summary"]
        total = summary["cash_inr"] + sum(summary["open_position_values_inr"].values())
        self.assertAlmostEqual(total, summary["final_equity_inr"], places=2)
        self.assertEqual(
            summary["open_positions_at_end"],
            {"ADANIPORTS": 14, "TECHM": 14, "BSE": 7, "DRREDDY": 21},
        )

    def test_decision_aggregates_match_rows(self):
        decisions = self.data["decisions"]
        self.assertEqual(len(decisions), 182)
        self.assertEqual(sum(row["side"] == "buy" for row in decisions), 136)
        self.assertEqual(sum(row["side"] == "sell" for row in decisions), 46)
        self.assertEqual(sum(row["buy"] + row["sell"] for row in self.data["monthly_activity"]), 182)
        self.assertEqual(sum(row["decisions"] for row in self.data["symbol_activity"]), 182)

    def test_current_state_is_gap_labelled(self):
        timeline = self.data["timeline"]
        self.assertEqual(timeline["experiment_started_on"], "2026-11-14")
        self.assertEqual(timeline["forward_tracking_started_on"], "2026-11-16")
        self.assertEqual(timeline["latest_verified_mark_date"], "2026-11-13")
        self.assertIn("could not be recovered", timeline["current_state"])
        self.assertIn("not today's live state", timeline["current_state"])
        self.assertIn("No real-money trading is taking place.", self.data["caveats"])

    def test_autonomy_policy_is_visible_and_gated(self):
        autonomy = self.data["autonomy"]
        self.assertEqual(autonomy["risk"]["max_loss_inr"], 40000)
        self.assertEqual(autonomy["risk"]["max_new_buys_per_day"], 2)
        self.assertEqual(autonomy["modes"]["delivery"]["status"], "enabled")
        self.assertEqual(autonomy["modes"]["intraday"]["status"], "paused")
        self.assertEqual(autonomy["modes"]["futures"]["status"], "paused")
        self.assertEqual(autonomy["modes"]["options"]["status"], "paused")
        self.assertIn("not a guaranteed fill", autonomy["stops"]["limit"])

    def test_static_app_has_no_external_dependencies(self):
        html = (ROOT / "app" / "index.html").read_text()
        js = (ROOT / "app" / "app.js").read_text()
        self.assertIn("No real-money trades", html)
        self.assertIn("Checkpoint gap visible", html)
        self.assertIn("No autonomous trades recorded yet", html)
        self.assertIn("Live-session execution: prepared, not activated", html)
        self.assertIn("script-src 'self'", html)
        self.assertNotIn("https://cdn", html)
        self.assertNotIn("fetch('http", js)
        self.assertIn("data/exp001.json", js)


if __name__ == "__main__":
    unittest.main()
