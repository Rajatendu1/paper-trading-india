#!/usr/bin/env python3
"""Integrity and reproducibility review of the EXP-001 run.

Checks, independent of the engine's own arithmetic where feasible:
  1. data sanity (bar counts, duplicate dates, missing days vs ^NSEI)
  2. reproducibility: re-running the experiment reproduces the recorded
     numbers in experiments/log.md exactly
  3. execution timing: every fill executes at the NEXT trading day's open
     after its decision, at open +/- slippage
  4. terminal decomposition: final cash + open positions at terminal close
     recomposes the recorded final equity
  5. independent replay of the fill list (cash arithmetic, no engine code)
  6. equity-series sanity: cash never negative; drawdown recomputed
  7. benchmark comparability statement

Run from the repo root:  python3 scripts/verify_exp001.py
"""
from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from papertrading.config import Config
from papertrading.costs import charges
from papertrading.data import Bar
from papertrading.engine import PaperEngine
from papertrading.ledger import Decision
from papertrading.strategy import RULE_NAME, generate_signals

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "yf"

UNIVERSE = """ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BSE BAJAJ-AUTO
BAJFINANCE BAJAJFINSV BEL BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT
ETERNAL GRASIM HCLTECH HDFCBANK HDFCLIFE HINDALCO HINDUNILVR ICICIBANK ITC
INFY INDIGO JSWSTEEL JIOFIN KOTAKBANK LT M&M MARUTI MAXHEALTH NTPC NESTLEIND
ONGC POWERGRID RELIANCE SBILIFE SHRIRAMFIN SBIN SUNPHARMA TCS TATACONSUM
TMPV TATASTEEL TECHM TITAN TRENT ULTRACEMCO""".split()

MAX_POSITIONS = 4
POSITION_FRACTION = 0.25

# Recorded in experiments/log.md for the first (and only) run.
RECORDED = {
    "final_equity_inr": 111150.78,
    "max_drawdown_inr": 14627.16,
    "trades_executed": 96,
    "skipped_decisions": 86,
    "benchmark_nifty50_return_pct": 27.8,
    "open_positions_at_end": {"ADANIPORTS": 14, "TECHM": 14, "BSE": 7, "DRREDDY": 21},
}

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    if not ok:
        failures.append(name)


def load_cache(symbol: str) -> list[Bar]:
    with (DATA_DIR / f"{symbol}.csv").open() as f:
        rows = list(csv.DictReader(f))
    return [Bar(r["date"], float(r["open"]), float(r["high"]),
                float(r["low"]), float(r["close"]), int(float(r["volume"])))
            for r in rows]


print("== 1. data sanity ==")
prices = {}
for sym in UNIVERSE:
    bars = load_cache(sym)
    days = [b.date for b in bars]
    check(f"sorted, no duplicate dates: {sym}", days == sorted(set(days)))
    prices[sym] = bars
bench = load_cache("^NSEI")
bench_days = {b.date for b in bench}
counts = [len(b) for b in prices.values()]
check("bar counts uniform across symbols", min(counts) == max(counts),
      f"min={min(counts)} max={max(counts)}")
for sym in UNIVERSE:
    missing = bench_days - {b.date for b in prices[sym]}
    if missing:
        print(f"      note: {sym} missing {len(missing)} index trading days "
              f"(earliest {min(missing)}) - engine skips fills on missing bars")

print("== 2. reproducibility vs experiments/log.md ==")
config = Config()
signals = {s: dict(generate_signals(bars)) for s, bars in prices.items()}
counters = {"n": 0}
logged_decisions: list[Decision] = []


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
            out.append(Decision(day, f"exp001-{counters['n']:04d}", sym,
                                "buy", qty, RULE_NAME,
                                "SMA20 crossed above SMA60; 25% sizing"))
        else:
            if sym not in open_syms:
                continue
            counters["n"] += 1
            out.append(Decision(day, f"exp001-{counters['n']:04d}", sym,
                                "sell", eng.ledger.positions[sym].qty,
                                RULE_NAME, "SMA20 crossed below SMA60"))
    logged_decisions.extend(out)
    return out


eng = PaperEngine(config, prices)
result = eng.run(strategy=strategy)

final_eq = result.final_equity
max_dd = max(m.drawdown for m in result.marks)
check("final equity reproduces recorded value",
      math.isclose(final_eq, RECORDED["final_equity_inr"], abs_tol=0.01),
      f"rerun={final_eq:.2f} recorded={RECORDED['final_equity_inr']:.2f}")
check("max drawdown reproduces recorded value",
      math.isclose(max_dd, RECORDED["max_drawdown_inr"], abs_tol=0.01),
      f"rerun={max_dd:.2f} recorded={RECORDED['max_drawdown_inr']:.2f}")
check("fill count reproduces", len(eng.ledger.fills) == RECORDED["trades_executed"],
      f"rerun={len(eng.ledger.fills)} recorded={RECORDED['trades_executed']}")
check("skipped count reproduces", len(result.skipped) == RECORDED["skipped_decisions"],
      f"rerun={len(result.skipped)} recorded={RECORDED['skipped_decisions']}")
open_pos = {s: p.qty for s, p in eng.ledger.positions.items() if p.qty > 0}
check("open positions reproduce", open_pos == RECORDED["open_positions_at_end"],
      f"rerun={open_pos}")
check("loss limit not hit", result.halted_on is None)

print("== 3. execution timing and price basis ==")
# Map each symbol's bars: date -> index
day_index = {s: {b.date: i for i, b in enumerate(bars)} for s, bars in prices.items()}
decision_by_key = {(d.symbol, d.side, d.date): d for d in logged_decisions}
slip = config.slippage_bps / 10_000
for f in eng.ledger.fills:
    idx = day_index[f.symbol].get(f.date)
    check(f"fill day has a bar: {f.symbol} {f.date}", idx is not None)
    if idx is None:
        continue
    prev = prices[f.symbol][idx - 1].date if idx > 0 else None
    d = decision_by_key.get((f.symbol, f.side, prev))
    check(f"fill follows decision by one session: {f.symbol} {f.side} {f.date}",
          d is not None, f"signal_day={prev}")
    if d is not None:
        check(f"fill qty == decision qty: {f.symbol} {f.date}", f.qty == d.qty,
              f"fill={f.qty} decision={d.qty}")
    expected = prices[f.symbol][idx].open * (1 + slip if f.side == "buy" else 1 - slip)
    check(f"fill price == open +/- slippage: {f.symbol} {f.date}",
          math.isclose(f.price, expected, rel_tol=1e-9),
          f"fill={f.price:.4f} expected={expected:.4f}")

print("== 4. terminal decomposition ==")
last_day = result.marks[-1].date
decomp = eng.ledger.cash
print(f"      final day {last_day}; cash Rs {eng.ledger.cash:,.2f}")
for s, p in sorted((s, p) for s, p in eng.ledger.positions.items() if p.qty > 0):
    close = eng.prices[s][last_day].close
    decomp += p.qty * close
    print(f"      open {s}: {p.qty} @ avg {p.avg_price:,.2f}; close {close:,.2f}; "
          f"value Rs {p.qty * close:,.2f}")
check("cash + terminal market value == final equity",
      math.isclose(decomp, final_eq, abs_tol=0.01),
      f"recomposed={decomp:.2f} vs equity={final_eq:.2f}")

print("== 5. independent fill replay (no engine code) ==")
cash = config.starting_capital_inr
qty = defaultdict(int)
for f in eng.ledger.fills:
    if f.side == "buy":
        cash -= f.qty * f.price + f.cost_total
        qty[f.symbol] += f.qty
    else:
        cash += f.qty * f.price - f.cost_total
        qty[f.symbol] -= f.qty
replay_eq = cash + sum(q * eng.prices[s][last_day].close
                       for s, q in qty.items() if q > 0)
check("replay quantities match engine positions",
      {s: q for s, q in qty.items() if q > 0} == open_pos)
check("replay equity matches engine equity",
      math.isclose(replay_eq, final_eq, abs_tol=0.01),
      f"replay={replay_eq:.2f} engine={final_eq:.2f}")
check("no symbol ever net-negative in replay", all(q >= 0 for q in qty.values()))
# cost spot-check: recompute charges independently for every fill
bad_costs = sum(
    1 for f in eng.ledger.fills
    if not math.isclose(f.cost_total,
                        charges(f.side, f.qty, f.price, config.segment)["total"],
                        rel_tol=1e-9))
check("every fill's charges match the cost model", bad_costs == 0,
      f"{bad_costs} mismatches")

print("== 6. equity-series sanity ==")
min_cash = min(m.cash for m in result.marks)
check("cash never negative in any daily mark", min_cash >= -0.01,
      f"min cash Rs {min_cash:,.2f}")
peak, recomputed_dd = config.starting_capital_inr, 0.0
for m in result.marks:
    peak = max(peak, m.equity)
    recomputed_dd = max(recomputed_dd, peak - m.equity)
check("drawdown recomputed from equity series matches",
      math.isclose(recomputed_dd, max_dd, abs_tol=0.01),
      f"recomputed={recomputed_dd:.2f}")

print("== 7. benchmark comparability ==")
first_mark = result.marks[0].date
b0 = next((b.close for b in bench if b.date >= first_mark), bench[0].close)
b1 = bench[-1].close
bench_ret = round((b1 / b0 - 1) * 100, 2)
check("benchmark price return reproduces recorded value",
      math.isclose(bench_ret, RECORDED["benchmark_nifty50_return_pct"], abs_tol=0.01),
      f"rerun={bench_ret}% recorded={RECORDED['benchmark_nifty50_return_pct']}%")
print("      ^NSEI is a PRICE-return index: no dividends, no costs.")
print("      Strategy series uses split/dividend-adjusted Yahoo prices WITH")
print("      modeled costs. The two series' treatments do not match in either")
print("      direction, and their net effect on the comparison is NOT quantified:")
print("      no aligned NIFTY 50 total-return history was obtained from a free")
print("      official source on 2026-11-14, and a single-date dividend yield")
print("      cannot quantify it. The +11.15% vs +27.8% gap is therefore reported")
print("      as an unmatched-treatments comparison, not a measured alpha.")
print("      Independent of treatment: current-constituent universe selection")
print("      is survivorship-biased, and sizing on adjusted prices is itself an")
print("      assumption (adjustment factors shift position quantities).")

print()
print("RESULT:", "ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES: {failures}")
sys.exit(1 if failures else 0)
