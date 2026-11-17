"""Gap-labelled preparation for prospective autonomous paper decisions.

This module plans; it does not execute, append to the append-only decision
log, connect to a broker or repair the missing 2026-11-16 checkpoint. A
prepared decision is not a logged decision until a separate forward runner
writes it before the next execution window.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping

from .autonomy import AutonomyPolicy, plan_position, portfolio_halt, stop_price
from .costs import charges
from .data import Bar
from .ledger import Decision
from .strategy import generate_signals

FORWARD_RULE = "autonomous-sma-cross-20-60-v1"
MISSING_CHECKPOINT_DATE = "2026-11-16"


@dataclass(frozen=True)
class ForwardState:
    as_of: str
    cash_inr: float
    positions: Mapping[str, int]
    source: str


def load_verified_state(app_data_path: str | Path) -> ForwardState:
    """Load the last verified EXP-001 terminal state shown by the public app."""
    payload = json.loads(Path(app_data_path).read_text())
    timeline = payload.get("timeline", {})
    summary = payload.get("summary", {})
    positions = summary.get("open_positions_at_end", {})
    if not isinstance(positions, dict) or not all(
        isinstance(symbol, str) and isinstance(qty, int) and qty > 0
        for symbol, qty in positions.items()
    ):
        raise ValueError("verified state has invalid open positions")
    cash = float(summary.get("cash_inr", 0.0))
    if cash < 0:
        raise ValueError("verified state cash cannot be negative")
    return ForwardState(
        as_of=str(timeline.get("latest_verified_mark_date", "")),
        cash_inr=cash,
        positions=positions,
        source=str(payload.get("sources", {}).get("experiment_register", "")),
    )


def _latest_bar_date(bars: list[Bar]) -> str:
    if not bars:
        raise ValueError("no bars")
    return max(bar.date for bar in bars)


def prepare_forward_plan(
    symbol_bars: Mapping[str, list[Bar]],
    state: ForwardState,
    policy: AutonomyPolicy,
    *,
    decision_date: str,
    data_through: str,
    segment: str = "delivery",
) -> dict[str, object]:
    """Prepare candidate decisions from complete bars through data_through.

    The decision date must be after the newest data date. This preserves the
    no-lookahead boundary for a decision made after that close and before the
    next trading session.
    """
    if date.fromisoformat(decision_date) <= date.fromisoformat(data_through):
        raise ValueError("decision_date must be after data_through")
    if not state.as_of:
        raise ValueError("verified state must name its as-of date")
    if policy.modes.get(segment, {}).get("status") != "enabled":
        raise ValueError(f"mode {segment!r} is not enabled")

    histories: dict[str, list[Bar]] = {}
    missing: list[str] = []
    for symbol, bars in sorted(symbol_bars.items()):
        usable = sorted((bar for bar in bars if bar.date <= data_through),
                        key=lambda bar: bar.date)
        if usable and _latest_bar_date(usable) == data_through:
            histories[symbol] = usable
        else:
            missing.append(symbol)

    missing_open = sorted(set(state.positions) - set(histories))
    if missing_open:
        raise ValueError(
            "cannot prepare forward plan without current bars for open positions: "
            + ", ".join(missing_open)
        )

    closes = {symbol: bars[-1].close for symbol, bars in histories.items()}
    planning_equity = state.cash_inr + sum(
        qty * closes[symbol] for symbol, qty in state.positions.items()
    )
    halt = portfolio_halt(100000.0, planning_equity, policy.max_loss_inr)

    stops = {
        symbol: stop_price(closes[symbol], histories[symbol], policy)
        for symbol in sorted(state.positions)
    }
    decisions: list[Decision] = []
    notes: list[str] = []
    cash_remaining = state.cash_inr
    deployed_today = 0.0
    buys_today = 0
    open_count = len([qty for qty in state.positions.values() if qty > 0])

    if halt:
        notes.append("portfolio halt threshold already reached on reconstructed planning equity")
    else:
        for symbol, bars in histories.items():
            signals = generate_signals(bars)
            latest = signals[-1] if signals else None
            if latest is None or latest[0] != data_through:
                continue
            side = latest[1]
            held = int(state.positions.get(symbol, 0))
            if side == "sell" and held:
                decisions.append(Decision(
                    date=decision_date,
                    decision_id=f"forward-{decision_date}-{len(decisions) + 1:04d}",
                    symbol=symbol,
                    side="sell",
                    qty=held,
                    rule=FORWARD_RULE,
                    rationale=(
                        f"AI paper decision after {data_through} close: SMA20 crossed "
                        "below SMA60; sell at next session open"
                    ),
                ))
                open_count -= 1
            elif side == "buy" and not held:
                plan = plan_position(
                    symbol,
                    bars[-1].close,
                    bars,
                    policy,
                    planning_equity,
                    cash_remaining,
                    deployed_today_inr=deployed_today,
                    buys_today=buys_today,
                    open_positions=open_count,
                )
                if plan is None:
                    notes.append(f"{symbol}: buy signal rejected by policy caps")
                    continue
                qty = plan.qty
                while qty > 0:
                    cost = charges("buy", qty, plan.reference_price, segment)["total"]
                    if qty * plan.reference_price + cost <= cash_remaining + 1e-9:
                        break
                    qty -= 1
                if qty < 1:
                    notes.append(f"{symbol}: buy signal rejected by cash after estimated charges")
                    continue
                exposure = qty * plan.reference_price
                decisions.append(Decision(
                    date=decision_date,
                    decision_id=f"forward-{decision_date}-{len(decisions) + 1:04d}",
                    symbol=symbol,
                    side="buy",
                    qty=qty,
                    rule=FORWARD_RULE,
                    rationale=(
                        f"AI paper decision after {data_through} close: SMA20 crossed "
                        "above SMA60; risk and exposure caps applied"
                    ),
                ))
                cash_remaining -= exposure + charges("buy", qty, plan.reference_price, segment)["total"]
                deployed_today += exposure
                buys_today += 1
                open_count += 1

    if not decisions and not notes:
        notes.append("no crossover signal on the data-through close")

    return {
        "schema": 1,
        "status": "prepared_not_executed",
        "decision_date": decision_date,
        "data_through": data_through,
        "gap": {
            "missing_checkpoint_date": MISSING_CHECKPOINT_DATE,
            "label": "gap-aware continuation",
            "honesty": (
                "The missing 2026-11-16 forward checkpoint is not repaired. "
                "Planning starts from the verified 2026-11-13 terminal state and "
                "uses later bars only as preparation data, not as a contemporaneous mark."
            ),
        },
        "source_state": {
            "as_of": state.as_of,
            "cash_inr": round(state.cash_inr, 2),
            "positions": dict(state.positions),
            "source": state.source,
        },
        "planning_equity_inr_reconstructed": round(planning_equity, 2),
        "portfolio_halt": halt,
        "stops_initialized": {
            symbol: round(value, 4) for symbol, value in stops.items()
        },
        "decisions": [
            {
                "date": item.date,
                "decision_id": item.decision_id,
                "symbol": item.symbol,
                "side": item.side,
                "qty": item.qty,
                "rule": item.rule,
                "rationale": item.rationale,
            }
            for item in decisions
        ],
        "notes": notes,
        "symbols_checked": len(symbol_bars),
        "symbols_missing_current_bar": missing,
        "limits": {
            "mode": segment,
            "delivery_status": policy.modes[segment]["status"],
            "max_loss_inr": policy.max_loss_inr,
            "stop_rule": "daily close creates next-open decision; no guaranteed fill",
        },
        "not_done": [
            "not appended to decisions/log.csv",
            "not executed",
            "not a broker or real-money order",
            "not a repaired 2026-11-16 checkpoint",
        ],
    }
