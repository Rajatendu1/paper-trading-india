"""Cost-model tests. Expected values are hand-computed from the published
rates in costs.py (source URL and retrieval date recorded there)."""
import unittest

from papertrading.costs import ChargeModel, charges


class TestDeliveryCharges(unittest.TestCase):
    def test_buy_10_at_1000(self):
        c = charges("buy", 10, 1000.0, "delivery")
        self.assertEqual(c["brokerage"], 0.0)
        self.assertAlmostEqual(c["stt"], 10.0)          # 0.1% of 10000
        self.assertAlmostEqual(c["txn"], 0.307)         # 0.00307%
        self.assertAlmostEqual(c["sebi"], 0.01)         # Rs10/crore
        self.assertAlmostEqual(c["gst"], 0.317 * 0.18)  # 18% of (0+0.01+0.307)
        self.assertAlmostEqual(c["stamp"], 1.5)         # 0.015% buy side
        self.assertEqual(c["dp"], 0.0)
        self.assertAlmostEqual(c["total"], 11.87406)

    def test_sell_10_at_1000_has_dp_charge(self):
        c = charges("sell", 10, 1000.0, "delivery")
        self.assertAlmostEqual(c["stt"], 10.0)          # delivery STT both sides
        self.assertEqual(c["stamp"], 0.0)               # stamp is buy side only
        self.assertAlmostEqual(c["dp"], 15.34)          # per scrip per sell day
        self.assertAlmostEqual(c["total"], 25.71406)


class TestIntradayCharges(unittest.TestCase):
    def test_buy_10_at_1000(self):
        c = charges("buy", 10, 1000.0, "intraday")
        self.assertAlmostEqual(c["brokerage"], 3.0)     # min(20, 0.03% of 10000)
        self.assertEqual(c["stt"], 0.0)                 # intraday STT sell only
        self.assertAlmostEqual(c["stamp"], 0.3)         # 0.003% buy side
        self.assertEqual(c["dp"], 0.0)                  # no DP on intraday
        self.assertAlmostEqual(c["gst"], 3.317 * 0.18)
        self.assertAlmostEqual(c["total"], 4.21406)

    def test_sell_10_at_1000(self):
        c = charges("sell", 10, 1000.0, "intraday")
        self.assertAlmostEqual(c["stt"], 2.5)           # 0.025% sell side
        self.assertAlmostEqual(c["total"], 6.41406)

    def test_brokerage_capped_at_20(self):
        c = charges("buy", 100, 1000.0, "intraday")     # 0.03% of 1L = 30
        self.assertAlmostEqual(c["brokerage"], 20.0)

    def test_model_overridable(self):
        m = ChargeModel(stt_delivery=0.0)
        c = charges("buy", 10, 1000.0, "delivery", m)
        self.assertEqual(c["stt"], 0.0)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            charges("hold", 10, 1000.0, "delivery")
        with self.assertRaises(ValueError):
            charges("buy", 0, 1000.0, "delivery")


if __name__ == "__main__":
    unittest.main()
