#!/usr/bin/env python3
"""Run EXP-001 locally: swing SMA(20/60) crossover on NIFTY 50 stocks.

Data is cached to data/ (gitignored - downloaded for local computation,
never redistributed). Prints an honest summary and appends the result to
experiments/log.md (append-only).

Usage: python3 scripts/run_experiment.py
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from papertrading.config import Config
from papertrading.data import Bar
from papertrading.engine import PaperEngine
from papertrading.ledger import Decision, DecisionLog
from papertrading.report import summarize
from papertrading.strategy import RULE_NAME, generate_signals

# Universe: current NIFTY 50 constituents, official NSE Indices CSV
# downloaded 2026-11-14 (survivorship bias documented in docs/experiment.md).
UNIVERSE = """ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BSE BAJAJ-AUTO
BAJFINANCE BAJAJFINSV BEL BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT
ETERNAL GRASIM HCLTECH HDFCBANK HDFCLIFE HINDALCO HINDUNILVR ICICIBANK ITC
INFY INDIGO JSWSTEEL JIOFIN KOTAKBANK LT M&M MARUTI MAXHEALTH NTPC NESTLEIND
ONGC POWERGRID RELIANCE SBILIFE SHRIRAMFIN SBIN SUNPHARMA TCS TATACONSUM
TMPV TATASTEEL TECHM TITAN TRENT ULTRACEMCO""".split()

START, END = "2023-11-14", "2026-11-14"  # yfinance end is exclusive
MAX_POSITIONS = 4
POSITION_FRACTION = 0.25
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "yf"


def load_bars(symbol: str) -> list[Bar]:
    cache = DATA_DIR / f"{symbol}.csv"
    if cache.exists():
        with cache.open() as f:
            rows = list(csv.DictReader(f))
        return [Bar(r["date"], float(r["open"]), float(r["high"]),
                    float(r["low"]), float(r["close"]), int(float(r["volume"])))
                for r in rows]
    import yfinance as yf
    ticker = symbol if symbol.startswith("^") else f"{symbol}.NS"
    df = yf.download(ticker, start=START, end=END,
                     auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"no data for {symbol}")
    if hasattr(df.columns, "get_level_values"):  # MultiIndex columns
        df.columns = df.columns.get_level_values(0)
    bars = []
    for idx, row in df.iterrows():
        bars.append(Bar(idx.date().isoformat(), float(row["Open"]),
                        float(row["High"]), float(row["Low"]),
                        float(row["Close"]), int(row["Volume"] or 0)))
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow([b.date, b.open, b.high, b.low, b.close, b.volume])
    return bars


def main() -> None:
    config = Config()
    prices = {}
    failed = []
    for sym in UNIVERSE:
        try:
            prices[sym] = load_bars(sym)
        except Exception as e:  # record and continue; report every failure
            failed.append((sym, str(e)))

    # Pre-compute crossover signal dates per symbol (dates/sides only;
    # sizing happens at signal time inside the strategy callback).
    signals = {s: dict(generate_signals(bars)) for s, bars in prices.items()}

    counters = {"n": 0}
    decision_log = DecisionLog(Path(__file__).resolve().parents[1]
                               / "decisions" / "log.csv")

    def strategy(day, eng, equity):
        out = []
        open_syms = {s for s, p in eng.ledger.positions.items() if p.qty > 0}
        for sym, sig in signals.items():
            side = sig.get(day)
            if side is None:
                continue
            if side == "buy":
                if sym in open_syms or len(open_syms) >= MAX_POSITIONS:
                    continue
                close = eng.prices[sym][day].close
                qty = int(POSITION_FRACTION * equity // close)
                if qty <= 0:
                    continue
                counters["n"] += 1
                d = Decision(day, f"exp001-{date.today().isoformat()}-{counters['n']:04d}", sym,
                             "buy", qty, RULE_NAME,
                             f"SMA20 crossed above SMA60; 25% sizing")
                decision_log.append(d)
                out.append(d)
            else:
                if sym not in open_syms:
                    continue
                counters["n"] += 1
                d = Decision(day, f"exp001-{date.today().isoformat()}-{counters['n']:04d}", sym,
                             "sell", eng.ledger.positions[sym].qty,
                             RULE_NAME, "SMA20 crossed below SMA60")
                decision_log.append(d)
                out.append(d)
        return out

    eng = PaperEngine(config, prices)
    result = eng.run(strategy=strategy)

    summary = summarize(config, result)
    summary["trades_executed"] = len(eng.ledger.fills)
    summary["symbols_failed_download"] = failed
    summary["open_positions_at_end"] = {
        s: p.qty for s, p in eng.ledger.positions.items() if p.qty > 0}

    # Benchmark: NIFTY 50 buy-and-hold over the same days (price return).
    bench = load_bars("^NSEI")
    if bench:
        b0 = next((b.close for b in bench if b.date >= result.marks[0].date),
                  bench[0].close)
        b1 = bench[-1].close
        summary["benchmark_nifty50_return_pct"] = round((b1 / b0 - 1) * 100, 2)

    for k, v in summary.items():
        print(f"{k}: {v}")

    entry = (f"\n## EXP-001 run {date.today().isoformat()} - {RULE_NAME}, "
             f"NIFTY 50 universe (2026-11-14 snapshot), {START}..{END}\n")
    for k, v in summary.items():
        entry += f"- {k}: {v}\n"
    entry += ("- notes: adjusted Yahoo daily data; survivorship-biased "
              "universe; delivery cost assumption of 2026-11-14 applied to "
              "whole period; benchmark is price return. Historical "
              "simulation only - no future-performance claim.\n")
    log = Path(__file__).resolve().parents[1] / "experiments" / "log.md"
    with log.open("a") as f:
        f.write(entry)
    print(f"\nappended to {log}")


if __name__ == "__main__":
    main()
