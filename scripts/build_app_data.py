#!/usr/bin/env python3
"""Build the static app's data bundle from the committed experiment record.

The app must render recorded facts, not decorative placeholders. This script
reads the append-only decision CSV and experiment register, derives simple
aggregates, and writes app/data/exp001.json. It does not fetch market data or
create new experiment results.
"""
from __future__ import annotations

import ast
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "decisions" / "log.csv"
LOG = ROOT / "experiments" / "log.md"
OUT = ROOT / "app" / "data" / "exp001.json"
AUTONOMY = ROOT / "config" / "autonomy.json"


def scalar(text: str, key: str) -> str:
    match = re.search(rf"^- {re.escape(key)}: (.+)$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"missing experiment value: {key}")
    return match.group(1).strip()


def money(text: str, label: str) -> float:
    match = re.search(rf"{re.escape(label)} Rs ([0-9,]+(?:\.\d+)?)", text)
    if not match:
        raise ValueError(f"missing money value: {label}")
    return float(match.group(1).replace(",", ""))


def main() -> None:
    with DECISIONS.open(newline="") as f:
        decisions = list(csv.DictReader(f))
    if not decisions:
        raise ValueError("decision log is empty")
    for row in decisions:
        row["qty"] = int(row["qty"])

    text = LOG.read_text()
    monthly: dict[str, dict[str, int]] = defaultdict(lambda: {"buy": 0, "sell": 0})
    symbols: Counter[str] = Counter()
    for row in decisions:
        month = row["date"][:7]
        monthly[month][row["side"]] += 1
        symbols[row["symbol"]] += 1

    open_positions = ast.literal_eval(scalar(text, "open_positions_at_end"))
    open_position_values = {
        symbol: money(text, symbol) for symbol in open_positions
    }
    payload = {
        "schema": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "product": {
            "name": "Paper Trading India",
            "status": "Paper trading only",
            "real_money": "No real-money trades, broker connection or orders",
        },
        "timeline": {
            "experiment_started_on": "2026-11-14",
            "historical_window": scalar(text, "period"),
            "forward_tracking_started_on": "2026-11-16",
            "latest_verified_mark_date": "2026-11-13",
            "current_state": (
                "The 2026-11-16 forward checkpoint artifacts could not be "
                "recovered. The only verified portfolio state shown here is "
                "the 2026-11-13 historical-simulation terminal state; it is "
                "not today's live state. A continuation must be gap-labelled."
            ),
        },
        "summary": {
            "starting_capital_inr": float(scalar(text, "starting_capital_inr")),
            "final_equity_inr": float(scalar(text, "final_equity_inr")),
            "total_return_pct": float(scalar(text, "total_return_pct")),
            "max_drawdown_inr": float(scalar(text, "max_drawdown_inr")),
            "loss_limit_inr": float(scalar(text, "loss_limit_inr")),
            "loss_limit_hit": scalar(text, "loss_limit_hit"),
            "trades_executed": int(scalar(text, "trades_executed")),
            "skipped_decisions": int(scalar(text, "skipped_decisions")),
            "benchmark_nifty50_return_pct": float(scalar(text, "benchmark_nifty50_return_pct")),
            "cash_inr": money(text, "Terminal decomposition: cash"),
            "open_positions_at_end": open_positions,
            "open_position_values_inr": open_position_values,
        },
        "autonomy": json.loads(AUTONOMY.read_text()),
        "strategy": {
            "id": "sma-cross-20-60",
            "name": "SMA 20/60 crossover",
            "status": "Historical simulation completed once",
            "signal": "Buy when SMA20 crosses above SMA60; sell when SMA20 crosses below SMA60.",
            "execution": "Next trading day's open with 10 bps assumed slippage per side.",
            "sizing": "25% of equity per position, maximum 4 positions, no pyramiding.",
        },
        "counts": {
            "decisions": len(decisions),
            "buys": sum(1 for row in decisions if row["side"] == "buy"),
            "sells": sum(1 for row in decisions if row["side"] == "sell"),
        },
        "monthly_activity": [
            {"month": month, **monthly[month]} for month in sorted(monthly)
        ],
        "symbol_activity": [
            {"symbol": symbol, "decisions": count}
            for symbol, count in symbols.most_common()
        ],
        "decisions": decisions,
        "caveats": [
            "Historical simulation only; it does not predict future results.",
            "The +11.15% strategy result and +27.8% NIFTY 50 price-index result use unmatched treatments; the gap is not measured alpha.",
            "The decision CSV is a deterministic backfill, not a contemporaneous decision record.",
            "Paper fills ignore liquidity, partial fills and real slippage beyond the configured assumption.",
            "No real-money trading is taking place.",
        ],
        "sources": {
            "decision_log": "decisions/log.csv",
            "experiment_register": "experiments/log.md",
            "integrity_review": "scripts/verify_exp001.py",
            "manifest": "experiments/exp001-manifest.sha256",
            "autonomy_policy": "config/autonomy.json",
            "autonomy_rules": "docs/autonomy.md",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(decisions)} decisions")


if __name__ == "__main__":
    main()
