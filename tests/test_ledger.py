import tempfile
import unittest
from pathlib import Path

from papertrading.ledger import Decision, DecisionLog, Fill, Ledger, Position


def dec(decision_id="d1", date="2026-11-10", symbol="SYM", side="buy",
        qty=10, rule="rule-1", rationale="test"):
    return Decision(date, decision_id, symbol, side, qty, rule, rationale)


class TestDecisionLog(unittest.TestCase):
    def test_append_only_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = DecisionLog(Path(tmp) / "log.csv")
            log.append(dec())
            log.append(dec(decision_id="d2", side="sell", qty=5))
            entries = log.entries()
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["rule"], "rule-1")

    def test_duplicate_id_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = DecisionLog(Path(tmp) / "log.csv")
            log.append(dec())
            with self.assertRaises(ValueError):
                log.append(dec())

    def test_decision_requires_rule(self):
        with self.assertRaises(ValueError):
            dec(rule="  ")


class TestLedger(unittest.TestCase):
    def test_buy_then_sell_cash_flows(self):
        l = Ledger(cash=100_000.0)
        l.apply_fill(Fill("2026-11-11", "SYM", "buy", 10, 100.0, 1.19))
        self.assertAlmostEqual(l.cash, 100_000 - 1000 - 1.19)
        l.apply_fill(Fill("2026-11-12", "SYM", "sell", 10, 104.0, 17.46))
        self.assertAlmostEqual(l.cash, 100_000 - 1000 - 1.19 + 1040 - 17.46)
        self.assertEqual(l.positions["SYM"].qty, 0)

    def test_oversell_rejected(self):
        l = Ledger(cash=100_000.0)
        l.apply_fill(Fill("2026-11-11", "SYM", "buy", 10, 100.0, 1.19))
        with self.assertRaises(ValueError):
            l.apply_fill(Fill("2026-11-12", "SYM", "sell", 11, 104.0, 0.0))

    def test_insufficient_cash_rejected(self):
        l = Ledger(cash=500.0)
        with self.assertRaises(ValueError):
            l.apply_fill(Fill("2026-11-11", "SYM", "buy", 10, 100.0, 1.19))

    def test_average_price(self):
        p = Position("SYM")
        p.buy(10, 100.0)
        p.buy(10, 110.0)
        self.assertAlmostEqual(p.avg_price, 105.0)


if __name__ == "__main__":
    unittest.main()
