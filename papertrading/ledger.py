"""Append-only decision log and position ledger.

The decision log is append-only: every paper trade is written
down with the rule that prompted it BEFORE it executes, and entries are never
edited or deleted - corrections are new entries. Future observations are
therefore never counted as historical success: the log is the whole record.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

LOG_HEADER = ["date", "decision_id", "symbol", "side", "qty", "rule", "rationale"]


@dataclass(frozen=True)
class Decision:
    date: str          # ISO date the decision was recorded (after close)
    decision_id: str
    symbol: str
    side: str          # "buy" | "sell"
    qty: int
    rule: str          # the pre-fixed rule that prompted this decision
    rationale: str     # short human note

    def __post_init__(self):
        if self.side not in ("buy", "sell"):
            raise ValueError(f"side must be buy|sell, got {self.side!r}")
        if self.qty <= 0:
            raise ValueError("qty must be positive")
        if not self.rule.strip():
            raise ValueError("every decision must name the rule that prompted it")


class DecisionLog:
    """Append-only CSV log. Existing entries are never rewritten."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(",".join(LOG_HEADER) + "\n")
        else:
            header = self.path.read_text().splitlines()[0]
            if header.split(",") != LOG_HEADER:
                raise ValueError(f"Log header mismatch in {self.path}; refusing to touch it")

    def append(self, d: Decision) -> None:
        existing = {r["decision_id"] for r in self.entries()}
        if d.decision_id in existing:
            raise ValueError(f"decision_id {d.decision_id!r} already logged; refusing duplicate")
        with self.path.open("a", newline="") as f:
            csv.writer(f).writerow(
                [d.date, d.decision_id, d.symbol, d.side, d.qty, d.rule, d.rationale])

    def entries(self) -> list[dict]:
        with self.path.open(newline="") as f:
            return list(csv.DictReader(f))


@dataclass
class Fill:
    date: str
    symbol: str
    side: str
    qty: int
    price: float
    cost_total: float  # transaction charges on this fill
    reason: str = ""   # e.g. "strategy" or "loss-limit-liquidation"


@dataclass
class Position:
    symbol: str
    qty: int = 0
    avg_price: float = 0.0  # volume-weighted average fill price

    def buy(self, qty: int, price: float) -> None:
        self.avg_price = (self.avg_price * self.qty + price * qty) / (self.qty + qty)
        self.qty += qty

    def sell(self, qty: int) -> None:
        if qty > self.qty:
            raise ValueError(
                f"Cannot sell {qty} of {self.symbol}; only {self.qty} held. "
                "Short selling is not supported (delivery segment).")
        self.qty -= qty
        if self.qty == 0:
            self.avg_price = 0.0


@dataclass
class Ledger:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)

    def apply_fill(self, fill: Fill) -> None:
        pos = self.positions.setdefault(fill.symbol, Position(fill.symbol))
        if fill.side == "buy":
            total = fill.qty * fill.price + fill.cost_total
            if total > self.cash + 1e-9:
                raise ValueError(
                    f"Insufficient cash: need {total:.2f}, have {self.cash:.2f}")
            pos.buy(fill.qty, fill.price)
            self.cash -= total
        else:
            pos.sell(fill.qty)
            self.cash += fill.qty * fill.price - fill.cost_total
        self.fills.append(fill)

    def market_value(self, closes: dict[str, float]) -> float:
        return sum(p.qty * closes.get(sym, p.avg_price)
                   for sym, p in self.positions.items() if p.qty > 0)

    def equity(self, closes: dict[str, float]) -> float:
        return self.cash + self.market_value(closes)
