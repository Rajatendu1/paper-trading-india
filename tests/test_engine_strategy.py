"""Engine strategy-callback tests: decisions generated during a run must
execute at the next open, and history() must not leak future bars."""
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


class TestStrategyCallback(unittest.TestCase):
    def test_callback_decision_executes_next_open(self):
        calls = []

        def strat(day, eng, equity):
            calls.append(day)
            if day == "2026-11-10":
                return [Decision(day, "cb1", "SYM", "buy", 10,
                                 "test-rule", "callback buy")]
            return []

        eng = PaperEngine(Config(), {"SYM": SYM_BARS})
        result = eng.run(strategy=strat)

        fill = eng.ledger.fills[0]
        self.assertEqual(fill.date, "2026-11-11")       # next trading day
        self.assertAlmostEqual(fill.price, 100.1)        # open + slippage
        self.assertEqual(fill.reason, "strategy")
        self.assertEqual(calls, ["2026-11-10", "2026-11-11", "2026-11-12"])

    def test_callback_not_called_after_halt(self):
        days_seen = []

        def strat(day, eng, equity):
            days_seen.append(day)
            return []

        cfg = Config(max_loss_inr=50.0)
        falling = bars([
            ("2026-11-10", 100.0, 101.0, 99.0, 100.0, 1000),
            ("2026-11-11", 100.0, 100.5, 89.0, 90.0, 1500),
            ("2026-11-12", 95.0, 95.5, 94.0, 95.0, 800),
        ])
        eng = PaperEngine(cfg, {"SYM": falling})
        eng.run([Decision("2026-11-10", "b1", "SYM", "buy", 10,
                          "rule-1", "enter")], strategy=strat)
        self.assertEqual(days_seen, ["2026-11-10"])  # halt at 11-11 close

    def test_history_excludes_future(self):
        eng = PaperEngine(Config(), {"SYM": SYM_BARS})
        h = eng.history("SYM", "2026-11-10")
        self.assertEqual([b.date for b in h], ["2026-11-10"])

    def test_decision_must_be_signal_day(self):
        def bad(day, eng, equity):
            return [Decision("2026-01-01", "x1", "SYM", "buy", 1, "r", "bad")]
        eng = PaperEngine(Config(), {"SYM": SYM_BARS})
        with self.assertRaises(ValueError):
            eng.run(strategy=bad)


if __name__ == "__main__":
    unittest.main()
