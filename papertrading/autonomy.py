"""Autonomous paper-trading risk controls.

This module turns the public autonomy policy into deterministic checks. It
plans only virtual delivery trades from daily bars. Intraday and derivatives
remain gated off until their data, costs and market mechanics are modelled.

The stop rules are decision rules, not guaranteed exits: a stop breached at a
daily close can only create a sell decision for the next trading day's open.
Overnight gaps can fill worse than the stop, in simulation and in live
markets.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .data import Bar


@dataclass(frozen=True)
class AutonomyPolicy:
    effective_on: str
    max_daily_new_exposure_pct: float
    max_new_buys_per_day: int
    max_position_pct: float
    max_open_positions: int
    per_trade_risk_pct: float
    atr_window: int
    atr_stop_multiple: float
    min_stop_pct: float
    max_stop_pct: float
    max_loss_inr: float
    modes: Mapping[str, Mapping[str, object]]

    @classmethod
    def load(cls, path: str | Path) -> "AutonomyPolicy":
        return cls.from_mapping(json.loads(Path(path).read_text()))

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "AutonomyPolicy":
        risk = data.get("risk")
        stops = data.get("stops")
        modes = data.get("modes")
        if not isinstance(risk, Mapping) or not isinstance(stops, Mapping):
            raise ValueError("autonomy policy needs risk and stops objects")
        if not isinstance(modes, Mapping) or not modes:
            raise ValueError("autonomy policy needs at least one mode gate")
        policy = cls(
            effective_on=str(data.get("effective_on", "")),
            max_daily_new_exposure_pct=float(risk["max_daily_new_exposure_pct"]),
            max_new_buys_per_day=int(risk["max_new_buys_per_day"]),
            max_position_pct=float(risk["max_position_pct"]),
            max_open_positions=int(risk["max_open_positions"]),
            per_trade_risk_pct=float(risk["per_trade_risk_pct"]),
            atr_window=int(stops["atr_window"]),
            atr_stop_multiple=float(stops["atr_stop_multiple"]),
            min_stop_pct=float(stops["min_stop_pct"]),
            max_stop_pct=float(stops["max_stop_pct"]),
            max_loss_inr=float(risk["max_loss_inr"]),
            modes=modes,
        )
        policy.validate()
        return policy

    def validate(self) -> None:
        pct_fields = (
            self.max_daily_new_exposure_pct,
            self.max_position_pct,
            self.per_trade_risk_pct,
            self.min_stop_pct,
            self.max_stop_pct,
        )
        if not self.effective_on:
            raise ValueError("effective_on is required")
        if any(not 0 < value <= 1 for value in pct_fields):
            raise ValueError("policy percentages must be in (0, 1]")
        if self.min_stop_pct > self.max_stop_pct:
            raise ValueError("min_stop_pct cannot exceed max_stop_pct")
        if self.max_new_buys_per_day < 1 or self.max_open_positions < 1:
            raise ValueError("daily buy and open-position limits must be positive")
        if self.atr_window < 1 or self.atr_stop_multiple <= 0:
            raise ValueError("ATR settings must be positive")
        if self.max_loss_inr <= 0:
            raise ValueError("max_loss_inr must be positive")
        for name, mode in self.modes.items():
            status = mode.get("status") if isinstance(mode, Mapping) else None
            if status not in {"enabled", "paused"}:
                raise ValueError(f"mode {name!r} must be enabled or paused")


@dataclass(frozen=True)
class PositionPlan:
    symbol: str
    reference_price: float
    stop_price: float
    qty: int
    exposure_inr: float
    risk_inr: float
    reason: str


def average_true_range(bars: list[Bar], window: int) -> float | None:
    """Simple ATR over the latest complete window; None when history is short."""
    if window < 1:
        raise ValueError("ATR window must be positive")
    bars = sorted(bars, key=lambda bar: bar.date)
    if len(bars) < window + 1:
        return None
    ranges: list[float] = []
    for previous, current in zip(bars[-window - 1:-1], bars[-window:]):
        ranges.append(max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        ))
    return sum(ranges) / window


def stop_price(reference_price: float, bars: list[Bar], policy: AutonomyPolicy) -> float:
    """Initial stop under a reference price, bounded by the public min/max."""
    if reference_price <= 0:
        raise ValueError("reference price must be positive")
    atr = average_true_range(bars, policy.atr_window)
    volatility_pct = policy.min_stop_pct if atr is None else (
        policy.atr_stop_multiple * atr / reference_price
    )
    stop_pct = min(max(volatility_pct, policy.min_stop_pct), policy.max_stop_pct)
    return reference_price * (1 - stop_pct)


def trailing_stop(current_stop: float, latest_close: float,
                  bars: list[Bar], policy: AutonomyPolicy) -> float:
    """Move a long stop upward only; never loosen it after adverse movement."""
    candidate = stop_price(latest_close, bars, policy)
    return max(current_stop, candidate)


def plan_position(symbol: str, reference_price: float, bars: list[Bar],
                  policy: AutonomyPolicy, equity: float, cash: float,
                  deployed_today_inr: float = 0.0,
                  buys_today: int = 0,
                  open_positions: int = 0) -> PositionPlan | None:
    """Size one prospective virtual buy under every active cap.

    Returns None when any cap leaves room for less than one whole share. The
    caller still has to apply itemized transaction costs before execution.
    """
    if not symbol.strip():
        raise ValueError("symbol is required")
    if equity <= 0 or cash < 0 or deployed_today_inr < 0:
        raise ValueError("equity, cash and deployed amount must be valid")
    if buys_today >= policy.max_new_buys_per_day:
        return None
    if open_positions >= policy.max_open_positions:
        return None

    stop = stop_price(reference_price, bars, policy)
    risk_per_share = reference_price - stop
    if risk_per_share <= 0:
        raise ValueError("stop must be below the reference price for a long buy")

    risk_budget = equity * policy.per_trade_risk_pct
    position_cap = equity * policy.max_position_pct
    daily_remaining = max(
        0.0,
        equity * policy.max_daily_new_exposure_pct - deployed_today_inr,
    )
    exposure_budget = min(cash, position_cap, daily_remaining)
    qty = min(
        math.floor(risk_budget / risk_per_share),
        math.floor(exposure_budget / reference_price),
    )
    if qty < 1:
        return None
    exposure = qty * reference_price
    return PositionPlan(
        symbol=symbol,
        reference_price=reference_price,
        stop_price=stop,
        qty=qty,
        exposure_inr=exposure,
        risk_inr=qty * risk_per_share,
        reason="risk-and-exposure-capped autonomous delivery buy",
    )


def portfolio_halt(starting_capital_inr: float, equity: float,
                   max_loss_inr: float) -> bool:
    """Overall halt rule: stop all new trades at the public virtual-loss line."""
    if starting_capital_inr <= 0 or max_loss_inr <= 0:
        raise ValueError("capital and max loss must be positive")
    return starting_capital_inr - equity >= max_loss_inr
