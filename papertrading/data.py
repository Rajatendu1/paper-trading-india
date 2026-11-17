"""Price data loaders.

Data sources (all free, verified 2026-11-14):
- NSE bhavcopy archives: official end-of-day files. The cash-market format
  changed on 2024-07-08 (NSE circular 62424), so this module parses both the
  current CM-UDiFF layout and the pre-2024-07 layout. Bhavcopy prices are RAW
  (not adjusted for splits/bonuses/dividends).
- yfinance (optional): unofficial Yahoo Finance wrapper. Prices are adjusted
  by default; we request auto_adjust=False to stay on the raw convention.

Convention rule: never mix adjusted and raw series in one run - the seam
creates fake gaps that look like crashes.

Files are downloaded locally and never redistributed; data/ is gitignored.
NSE rate-limits clients that hammer the site, so downloads are cached.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

ARCHIVE_BASE = "https://nsearchives.nseindia.com/content"
USER_AGENT = "paper-trading-india/0.1 (local research; one file at a time)"


@dataclass(frozen=True)
class Bar:
    date: str  # ISO yyyy-mm-dd
    open: float
    high: float
    low: float
    close: float
    volume: int


# Column candidates per logical field: current CM-UDiFF names first,
# pre-2024-07 names second.
_COLUMNS = {
    "symbol": ["TckrSymb", "SYMBOL"],
    "series": ["SctySrs", "SERIES"],
    "date": ["TradDt", "TIMESTAMP"],
    "open": ["OpnPric", "OPEN"],
    "high": ["HghPric", "HIGH"],
    "low": ["LwPric", "LOW"],
    "close": ["ClsPric", "CLOSE"],
    "volume": ["TtlTradgVol", "TOTTRDQTY"],
}


def _pick(header: list[str], field: str) -> str:
    for name in _COLUMNS[field]:
        if name in header:
            return name
    raise ValueError(f"No known column for {field!r} in header: {header}")


def _parse_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date {raw!r}")


def load_bhavcopy_csv(path: str | Path, series: str = "EQ") -> dict[str, list[Bar]]:
    """Parse one NSE cash-market bhavcopy (either format era).

    Returns {symbol: [Bar]} filtered to the given series (default EQ).
    """
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    col = {field: header.index(_pick(header, field)) for field in _COLUMNS}

    out: dict[str, list[Bar]] = {}
    for r in body:
        if not r or r[col["series"]].strip() != series:
            continue
        try:
            bar = Bar(
                date=_parse_date(r[col["date"]]),
                open=float(r[col["open"]]),
                high=float(r[col["high"]]),
                low=float(r[col["low"]]),
                close=float(r[col["close"]]),
                volume=int(float(r[col["volume"]] or 0)),
            )
        except (ValueError, IndexError):
            continue  # skip malformed rows rather than invent data
        out.setdefault(r[col["symbol"]].strip(), []).append(bar)
    return out


def bhavcopy_url(d: date) -> str:
    """Current-format archive URL for a trading date (works back to 2010)."""
    return (f"{ARCHIVE_BASE}/cm/BhavCopy_NSE_CM_0_0_0_"
            f"{d:%Y%m%d}_F_0000.csv.zip")


def fetch_bhavcopy(d: date, cache_dir: str | Path = "data") -> Path:
    """Download (once, with caching) and extract one day's bhavcopy."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv"
    if target.exists():
        return target
    req = urllib.request.Request(bhavcopy_url(d), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = resp.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(cache)
    if not target.exists():
        raise FileNotFoundError(f"Expected {target} after extract")
    return target


def _scalar(value):
    """Return a plain scalar from pandas' current Series-wrapped row values."""
    if hasattr(value, "iloc"):
        value = value.iloc[0]
    return value


def load_yfinance(symbol: str, start: str, end: str) -> list[Bar]:
    """Daily bars via yfinance (optional dependency, unofficial source).

    auto_adjust=False keeps raw prices, matching the bhavcopy convention.
    Yahoo lists NSE stocks as e.g. RELIANCE.NS and NIFTY 50 as ^NSEI.
    """
    try:
        import yfinance as yf
    except ImportError as e:
        raise ImportError("pip install yfinance to use load_yfinance") from e
    df = yf.download(symbol, start=start, end=end,
                     auto_adjust=False, progress=False)
    bars = []
    for idx, row in df.iterrows():
        bars.append(Bar(
            date=idx.date().isoformat(),
            open=float(_scalar(row["Open"])),
            high=float(_scalar(row["High"])),
            low=float(_scalar(row["Low"])),
            close=float(_scalar(row["Close"])),
            volume=int(_scalar(row["Volume"]) or 0),
        ))
    return bars
