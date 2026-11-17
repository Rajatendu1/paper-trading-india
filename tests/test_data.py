import tempfile
import unittest
from pathlib import Path

from papertrading.data import _scalar, bhavcopy_url, load_bhavcopy_csv
from datetime import date

NEW_FORMAT = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,"
    "XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,"
    "LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,"
    "ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,"
    "Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
    "2026-11-13,2026-11-13,CM,NSE,STK,2885,INE002A01018,RELIANCE,EQ,,,,,"
    "Reliance Industries Ltd,1500.00,1512.00,1495.00,1508.50,1508.00,"
    "1498.00,,1508.50,,,5000000,7542500000.00,250000,F1,1,,,,,\n"
    "2026-11-13,2026-11-13,CM,NSE,STK,9999,INE999X01011,SMALLCAP,BE,,,,,"
    "Small Co,50.00,51.00,49.00,50.50,50.50,50.00,,50.50,,,1000,50500.00,"
    "50,F1,1,,,,,\n"
)

OLD_FORMAT = (
    "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,"
    "TIMESTAMP,TOTALTRADES,ISIN\n"
    "RELIANCE,EQ,1490.00,1505.00,1485.00,1498.00,1498.00,1480.00,4000000,"
    "5992000000.00,12-Nov-2024,200000,INE002A01018\n"
)


class TestBhavcopyParser(unittest.TestCase):
    def _write(self, tmp, content):
        p = Path(tmp) / "bhav.csv"
        p.write_text(content)
        return p

    def test_new_format_eq_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = load_bhavcopy_csv(self._write(tmp, NEW_FORMAT))
        self.assertIn("RELIANCE", out)
        self.assertNotIn("SMALLCAP", out)  # BE series filtered out
        b = out["RELIANCE"][0]
        self.assertEqual(b.date, "2026-11-13")
        self.assertEqual(b.open, 1500.00)
        self.assertEqual(b.close, 1508.50)
        self.assertEqual(b.volume, 5_000_000)

    def test_old_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = load_bhavcopy_csv(self._write(tmp, OLD_FORMAT))
        b = out["RELIANCE"][0]
        self.assertEqual(b.date, "2024-11-12")
        self.assertEqual(b.close, 1498.00)

    def test_archive_url(self):
        self.assertEqual(
            bhavcopy_url(date(2026, 11, 13)),
            "https://nsearchives.nseindia.com/content/cm/"
            "BhavCopy_NSE_CM_0_0_0_20261113_F_0000.csv.zip")

    def test_yfinance_scalar_compatibility(self):
        class Wrapped:
            def __init__(self, value):
                self.iloc = [value]

        self.assertEqual(_scalar(12.5), 12.5)
        self.assertEqual(_scalar(Wrapped(12.5)), 12.5)


if __name__ == "__main__":
    unittest.main()
