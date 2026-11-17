#!/usr/bin/env python3
"""Prepare a gap-labelled autonomous forward decision manifest.

This does not append decisions or execute anything. It fetches/caches raw
Yahoo daily bars only when local cache is missing the requested data-through
date, then writes a candidate manifest for review.

Usage:
  python3 scripts/prepare_forward_run.py --data-through 2026-11-16 \
    --decision-date 2026-11-17 --output /tmp/forward-prep.json
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from papertrading.autonomy import AutonomyPolicy
from papertrading.data import Bar, load_yfinance
from papertrading.forward import load_verified_state, prepare_forward_plan
from run_experiment import UNIVERSE

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "yf"


def read_cache(symbol: str) -> list[Bar]:
    path = CACHE / f"{symbol}.csv"
    if not path.exists():
        return []
    with path.open(newline="") as stream:
        return [
            Bar(
                row["date"], float(row["open"]), float(row["high"]),
                float(row["low"]), float(row["close"]),
                int(float(row["volume"])),
            )
            for row in csv.DictReader(stream)
        ]


def write_cache(symbol: str, bars: list[Bar]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{symbol}.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["date", "open", "high", "low", "close", "volume"])
        for bar in bars:
            writer.writerow([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])


def load_symbol(symbol: str, data_through: str, decision_date: str) -> list[Bar]:
    bars = read_cache(symbol)
    if bars and max(bar.date for bar in bars) >= data_through:
        return bars
    start = (date.fromisoformat(data_through) - timedelta(days=180)).isoformat()
    bars = load_yfinance(symbol if symbol.startswith("^") else f"{symbol}.NS", start, decision_date)
    write_cache(symbol, bars)
    return bars


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-through", required=True)
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    state = load_verified_state(ROOT / "app" / "data" / "exp001.json")
    policy = AutonomyPolicy.load(ROOT / "config" / "autonomy.json")
    bars = {
        symbol: load_symbol(symbol, args.data_through, args.decision_date)
        for symbol in UNIVERSE
    }
    manifest = prepare_forward_plan(
        bars,
        state,
        policy,
        decision_date=args.decision_date,
        data_through=args.data_through,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {output} with {len(manifest['decisions'])} prepared decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
