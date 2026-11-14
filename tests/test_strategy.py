import unittest

from papertrading.data import Bar
from papertrading.strategy import generate_signals, sma


def series(closes):
    return [Bar(f"2026-01-{i+1:02d}", c, c, c, c, 100)
            for i, c in enumerate(closes)]


class TestSMA(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(sma([1.0, 2.0, 3.0], 2), [None, 1.5, 2.5])

    def test_short_series_all_none(self):
        self.assertEqual(sma([1.0], 3), [None])


class TestSignals(unittest.TestCase):
    def test_cross_up_then_down(self):
        # fast crosses above slow, then back below
        closes = [10.0] * 6 + [10.0, 20.0, 20.0, 10.0, 10.0, 10.0]
        sigs = generate_signals(series(closes), fast=2, slow=3)
        sides = [s for _, s in sigs]
        self.assertEqual(sides, ["buy", "sell"])
        # buy recorded on the spike day (close 20), sell on the drop back
        self.assertEqual(closes[int(sigs[0][0][-2:]) - 1], 20.0)
        self.assertEqual(closes[int(sigs[1][0][-2:]) - 1], 10.0)

    def test_flat_series_no_signals(self):
        self.assertEqual(generate_signals(series([5.0] * 10), 2, 3), [])

    def test_no_duplicate_sides_in_a_row(self):
        closes = [10.0, 10.0, 10.0, 30.0, 10.0, 30.0, 10.0, 10.0]
        sigs = generate_signals(series(closes), fast=2, slow=3)
        sides = [s for _, s in sigs]
        self.assertEqual(sides, sorted(sides, reverse=True) if sides == [] else sides)
        for a, b in zip(sides, sides[1:]):
            self.assertNotEqual(a, b)

    def test_fast_must_be_shorter(self):
        with self.assertRaises(ValueError):
            generate_signals(series([1.0] * 5), fast=3, slow=2)


if __name__ == "__main__":
    unittest.main()
