from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from papertrading.config import Config
from papertrading.ledger import Decision, Ledger, Position
from papertrading.live import (
    LiveSessionPolicy,
    Quote,
    in_normal_session,
    is_trading_day,
    quote_rejection_reasons,
    run_session_decisions,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-11-18T10:00:05+05:30"


def quote(**overrides) -> Quote:
    values = {
        "symbol": "TEST.NS",
        "price": 100.0,
        "quoted_at": "2026-11-18T10:00:00+05:30",
        "retrieved_at": "2026-11-18T10:00:02+05:30",
        "source": "unit-test-snapshot",
        "exchange": "NSE",
        "source_delay_seconds": 0,
    }
    values.update(overrides)
    return Quote.from_mapping(values)


def decision(side: str = "buy", qty: int = 2) -> Decision:
    return Decision(
        date="2026-11-17",
        decision_id="test-live-0001",
        symbol="TEST",
        side=side,
        qty=qty,
        rule="unit-test-live-rule",
        rationale="test decision recorded before session execution",
    )


class LiveSessionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = LiveSessionPolicy.load(ROOT / "config" / "live-session.json")
        cls.config = Config(slippage_bps=10.0, segment="delivery")

    def test_loads_nse_session_and_2026_holidays(self):
        self.assertEqual(self.policy.status, "prepared_not_activated")
        self.assertEqual(self.policy.timezone, "Asia/Kolkata")
        self.assertEqual(self.policy.session_open.strftime("%H:%M"), "09:15")
        self.assertEqual(self.policy.session_close.strftime("%H:%M"), "15:30")
        self.assertIn("2026-01-15", self.policy.holidays)
        self.assertIn("2026-11-24", self.policy.holidays)

    def test_session_guard_rejects_weekend_and_holiday(self):
        self.assertFalse(is_trading_day("2026-11-21", self.policy))
        self.assertFalse(is_trading_day("2026-11-24", self.policy))
        self.assertTrue(in_normal_session(quote().quoted_at, self.policy))

    def test_quote_fails_closed_when_stale_or_outside_session(self):
        stale = quote(quoted_at="2026-11-18T09:50:00+05:30")
        outside = quote(
            quoted_at="2026-11-18T16:00:00+05:30",
            retrieved_at="2026-11-18T16:00:02+05:30",
        )
        stale_reasons = quote_rejection_reasons(
            stale, self.policy, now=quote().retrieved_at
        )
        outside_reasons = quote_rejection_reasons(
            outside, self.policy, now=outside.retrieved_at
        )
        self.assertTrue(any("stale" in reason for reason in stale_reasons))
        self.assertTrue(any("outside" in reason for reason in outside_reasons))

    def test_bse_delayed_quote_is_not_enabled(self):
        delayed = quote(exchange="BSE", source_delay_seconds=900)
        reasons = quote_rejection_reasons(
            delayed, self.policy, now=quote().retrieved_at
        )
        self.assertTrue(any("not enabled" in reason for reason in reasons))

    def test_dry_run_plans_virtual_buy_without_mutating_ledger(self):
        ledger = Ledger(cash=1000.0, positions={})
        result = run_session_decisions(
            [decision()],
            {"TEST": quote()},
            ledger,
            self.config,
            self.policy,
            now=quote().retrieved_at,
            dry_run=True,
        )
        self.assertEqual(result["status"], "session_plan_not_executed")
        self.assertEqual(len(result["fills"]), 1)
        fill = result["fills"][0]
        self.assertEqual(fill["virtual_fill_price"], 100.1)
        self.assertLess(result["cash_after_virtual_fills"], 1000.0)
        self.assertEqual(result["positions_after_virtual_fills"], {"TEST": 2})
        self.assertEqual(ledger.cash, 1000.0)
        self.assertEqual(ledger.positions, {})
        self.assertIn("no quote polling or scheduling was activated", result["not_done"])

    def test_dry_run_plans_virtual_sell_from_held_position(self):
        ledger = Ledger(
            cash=100.0,
            positions={"TEST": Position(symbol="TEST", qty=2, avg_price=90.0)},
        )
        result = run_session_decisions(
            [decision(side="sell", qty=2)],
            {"TEST": quote()},
            ledger,
            self.config,
            self.policy,
            now=quote().retrieved_at,
            dry_run=True,
        )
        self.assertEqual(len(result["fills"]), 1)
        self.assertEqual(result["positions_after_virtual_fills"], {})
        self.assertEqual(ledger.positions["TEST"].qty, 2)

    def test_live_execution_cannot_activate_itself(self):
        with self.assertRaisesRegex(ValueError, "prepared_not_activated"):
            run_session_decisions(
                [decision()],
                {"TEST": quote()},
                Ledger(cash=1000.0),
                self.config,
                self.policy,
                now=quote().retrieved_at,
                dry_run=False,
            )


class LiveSessionScriptTests(unittest.TestCase):
    def test_prepare_live_session_writes_gap_safe_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plan_path = tmp_path / "plan.json"
            quotes_path = tmp_path / "quotes.json"
            output_path = tmp_path / "out.json"
            plan_path.write_text(json.dumps({
                "status": "prepared_not_executed",
                "decisions": [{
                    "date": "2026-11-17",
                    "decision_id": "forward-2026-11-17-0001",
                    "symbol": "TEST",
                    "side": "buy",
                    "qty": 1,
                    "rule": "test-rule",
                    "rationale": "test decision",
                }],
            }))
            quotes_path.write_text(json.dumps({"quotes": [{
                "symbol": "TEST.NS",
                "price": 100.0,
                "quoted_at": "2026-11-18T10:00:00+05:30",
                "retrieved_at": "2026-11-18T10:00:02+05:30",
                "source": "unit-test-snapshot",
                "exchange": "NSE",
                "source_delay_seconds": 0,
            }]}))
            subprocess.run(
                [
                    "python3",
                    "scripts/prepare_live_session.py",
                    "--plan", str(plan_path),
                    "--quotes", str(quotes_path),
                    "--output", str(output_path),
                    "--now", NOW,
                ],
                cwd=ROOT,
                check=True,
            )
            payload = json.loads(output_path.read_text())
            self.assertEqual(payload["status"], "session_plan_not_executed")
            self.assertEqual(payload["activation_status"], "prepared_not_activated")
            self.assertEqual(len(payload["fills"]), 1)
            self.assertEqual(payload["fills"][0]["symbol"], "TEST")
            self.assertIn("not a broker order", payload["not_done"])


if __name__ == "__main__":
    unittest.main()
