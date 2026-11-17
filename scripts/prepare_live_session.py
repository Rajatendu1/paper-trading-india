#!/usr/bin/env python3
"""Prepare a live-session virtual fill manifest from local quote snapshots.

Inputs are local JSON files only. This command does not poll a quote source,
append decisions, persist fills, connect to a broker or place a real order.
The output remains `session_plan_not_executed` while
`config/live-session.json` has status `prepared_not_activated`.

Quote snapshot format:

```json
{
  "quotes": [
    {
      "symbol": "RELIANCE.NS",
      "price": 1500.0,
      "quoted_at": "2026-11-18T10:00:00+05:30",
      "retrieved_at": "2026-11-18T10:00:02+05:30",
      "source": "manual-yahoo-chart-query2",
      "exchange": "NSE",
      "source_delay_seconds": 0
    }
  ]
}
```
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from papertrading.config import Config
from papertrading.forward import load_verified_state
from papertrading.ledger import Decision, Ledger, Position
from papertrading.live import LiveSessionPolicy, Quote, run_session_decisions

ROOT = Path(__file__).resolve().parents[1]


def _quote_key(symbol: str) -> str:
    symbol = symbol.strip().upper()
    return symbol[:-3] if symbol.endswith(".NS") else symbol


def _load_decisions(path: Path) -> list[Decision]:
    payload = json.loads(path.read_text())
    if payload.get("status") != "prepared_not_executed":
        raise ValueError("forward plan must be prepared_not_executed")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("forward plan decisions must be a list")
    return [
        Decision(
            date=str(item["date"]),
            decision_id=str(item["decision_id"]),
            symbol=str(item["symbol"]),
            side=str(item["side"]),
            qty=int(item["qty"]),
            rule=str(item["rule"]),
            rationale=str(item["rationale"]),
        )
        for item in decisions
    ]


def _load_quotes(path: Path) -> dict[str, Quote]:
    payload = json.loads(path.read_text())
    rows = payload if isinstance(payload, list) else payload.get("quotes")
    if not isinstance(rows, list):
        raise ValueError("quote file must be a list or contain a quotes list")
    quotes = [Quote.from_mapping(item) for item in rows]
    return {_quote_key(quote.symbol): quote for quote in quotes}


def _verified_ledger() -> Ledger:
    state = load_verified_state(ROOT / "app" / "data" / "exp001.json")
    return Ledger(
        cash=state.cash_inr,
        positions={
            symbol: Position(symbol=symbol, qty=qty, avg_price=0.0)
            for symbol, qty in state.positions.items()
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="prepared_not_executed forward manifest")
    parser.add_argument("--quotes", required=True, help="local timestamped quote snapshots")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--now",
        help="timezone-aware evaluation timestamp; defaults to current UTC time",
    )
    args = parser.parse_args()

    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now else datetime.now(timezone.utc)
    )
    if now.tzinfo is None:
        raise ValueError("--now must be timezone-aware")

    config = Config.load(ROOT / "config.json")
    policy = LiveSessionPolicy.load(ROOT / "config" / "live-session.json")
    decisions = _load_decisions(Path(args.plan))
    quotes = _load_quotes(Path(args.quotes))
    manifest = run_session_decisions(
        decisions,
        quotes,
        _verified_ledger(),
        config,
        policy,
        now=now,
        dry_run=True,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {output} with {len(manifest['fills'])} planned virtual fills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
