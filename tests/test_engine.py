"""Engine tests on synthetic bars (offline, no network).

Hand-computed expectations:
- Buy 10 SYM decided 2026-11-10 executes at 2026-11-11 open 100 + 10bps
  = 100.1; value 1001; delivery buy costs ~= 1.1886; cash 98997.8114.
- Mark 2026-11-11 at close 105 -> equity 100047.81.
- Sell 10 decided 2026-11-11 executes at 2026-11-12 open 104 - 10bps
  = 103.896; proceeds 1038.96; delivery sell costs ~= 16.4178.
- Final cash (flat) ~= 100020.35.
"""
import unittest

from papertrading.config import Config
from papertrading.data import Bar
from papertrading.engine import PaperEngine
from papertrading.ledger import Decision


def bars(rows):
    return [Bar(date=d, open=o, high=h, low=l, close=c, volume=v)
            for d, o, h, l, c, v in rows]


SYM_BARS = bars([
    ("2026-11-10", 100.0, 101.0, 99.0, 100.0, 1000),
    ("2026-11-11", 100.0, 106.0, 99.5, 105.0, 1200),
    ("2026-11-12", 104.0, 104.5, 103.0, 104.0, 900),
])


class TestExecution(unittest.TestCase):
    def test_next_open_execution_roundtrip(self):
        cfg = Config()
        eng = PaperEngine(cfg, {"SYM": SYM_BARS})
        decisions = [
            Decision("2026-11-10", "b1", "SYM", "buy", 10, "rule-1", "enter"),
            Decision("2026-11-11", "s1", "SYM", "sell", 10, "rule-1", "exit"),
        ]
        result = eng.run(decisions)

        # decision made on a day executes the NEXT trading day, not same day
        mark10 = result.marks[0]
        self.assertEqual(mark10.date, "2026-11-10")
        self.assertAlmostEqual(mark10.equity, 100_000.0)  # nothing executed yet

        buy_fill = eng.ledger.fills[0]
        self.assertEqual(buy_fill.date, "2026-11-11")
        self.assertAlmostEqual(buy_fill.price, 100.1)     # open + slippage
        self.assertAlmostEqual(buy_fill.cost_total, 1.1886, places=3)

        mark11 = result.marks[1]
        self.assertAlmostEqual(mark11.equity, 100_047.81, places=2)

        sell_fill = eng.ledger.fills[1]
        self.assertEqual(sell_fill.date, "2026-11-12")
        self.assertAlmostEqual(sell_fill.price, 103.896)  # open - slippage
        self.assertAlmostEqual(sell_fill.cost_total, 16.4178, places=3)

        self.assertAlmostEqual(result.final_equity, 100_020.35, places=2)
        self.assertEqual(result.skipped, [])

    def test_oversell_is_skipped_not_fatal(self):
        cfg = Config()
        eng = PaperEngine(cfg, {"SYM": SYM_BARS})
        result = eng.run([
            Decision("2026-11-10", "s1", "SYM", "sell", 10, "rule-1", "short?")])
        self.assertEqual(len(result.skipped), 1)
        self.assertAlmostEqual(result.final_equity, 100_000.0)


class TestLossLimit(unittest.TestCase):
    def test_halt_then_liquidate_next_open(self):
        cfg = Config(max_loss_inr=50.0)
        falling = bars([
            ("2026-11-10", 100.0, 101.0, 99.0, 100.0, 1000),
            ("2026-11-11", 100.0, 100.5, 89.0, 90.0, 1500),
            ("2026-11-12", 95.0, 95.5, 94.0, 95.0, 800),
            ("2026-11-13", 92.0, 93.0, 91.0, 92.5, 700),
        ])
        eng = PaperEngine(cfg, {"SYM": falling})
        result = eng.run([
            Decision("2026-11-10", "b1", "SYM", "buy", 10, "rule-1", "enter"),
            Decision("2026-11-11", "b2", "SYM", "buy", 10, "rule-1", "add"),
        ])
        # breach at 11-11 close (equity 99897.81, loss 102.19 >= 50)
        self.assertEqual(result.halted_on, "2026-11-11")
        # forced liquidation at next trading day's open (11-12)
        self.assertEqual(result.liquidated_on, "2026-11-12")
        liq = eng.ledger.fills[-1]
        self.assertEqual(liq.reason, "loss-limit-liquidation")
        self.assertEqual(liq.side, "sell")
        self.assertEqual(liq.qty, 10)
        self.assertAlmostEqual(liq.price, 95.0 * (1 - 0.001))  # open - slippage
        # flat afterwards; the queued strategy buy never executed
        self.assertEqual(eng.ledger.positions["SYM"].qty, 0)
        self.assertEqual(len(eng.ledger.fills), 2)
        self.assertTrue(any("halted" in why for _, why in result.skipped))
        # equity is cash-only from liquidation day onward
        self.assertAlmostEqual(result.marks[-1].equity, result.marks[-1].cash)

    def test_limit_is_not_a_hard_cap(self):
        # price gaps down overnight: liquidation fills well below the limit
        cfg = Config(max_loss_inr=50.0)
        gapping = bars([
            ("2026-11-10", 100.0, 101.0, 99.0, 100.0, 1000),
            ("2026-11-11", 100.0, 100.5, 89.0, 90.0, 1500),   # breach at close
            ("2026-11-12", 50.0, 51.0, 49.0, 50.0, 5000),     # overnight gap
        ])
        eng = PaperEngine(cfg, {"SYM": gapping})
        result = eng.run([
            Decision("2026-11-10", "b1", "SYM", "buy", 10, "rule-1", "enter")])
        self.assertEqual(result.halted_on, "2026-11-11")
        self.assertEqual(result.liquidated_on, "2026-11-12")
        final_loss = 100_000.0 - result.final_equity
        self.assertGreater(final_loss, 50.0)  # loss exceeded the limit: documented, not a cap


if __name__ == "__main__":
    unittest.main()
