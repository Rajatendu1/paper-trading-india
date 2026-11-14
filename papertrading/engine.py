"""Execution and mark-to-market engine.

Execution rule (fixed beforehand, stated here so it cannot drift):
a decision recorded on date D executes at the OPEN of the first trading day
AFTER D, at that open price plus assumed slippage, plus itemized transaction
costs. Decisions therefore never use same-day close information - no
lookahead by construction.

Loss-limit rule: when mark-to-market equity falls to or below
(starting_capital - max_loss), the experiment halts new executions and the
breach is recorded. Real markets could gap past a limit; this paper rule
records the breach exactly, it does not simulate an emergency exit.

This engine works on daily bars. It cannot validate intraday (same-day)
entries/exits - a daily candle does not say what happened inside the day.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config
from .costs import charges
from .data import Bar
from .ledger import Decision, Fill, Ledger


@dataclass
class DayMark:
    date: str
    equity: float
    cash: float
    drawdown: float          # peak-to-date decline in equity
    loss_limit_hit: bool


@dataclass
class Result:
    marks: list[DayMark] = field(default_factory=list)
    skipped: list[tuple[Decision, str]] = field(default_factory=list)
    halted_on: str | None = None

    @property
    def final_equity(self) -> float:
        return self.marks[-1].equity if self.marks else 0.0


class PaperEngine:
    def __init__(self, config: Config, prices: dict[str, list[Bar]]):
        self.config = config
        # index bars by symbol -> date -> Bar
        self.prices = {s: {b.date: b for b in bars} for s, bars in prices.items()}
        self.days = sorted({b.date for bars in prices.values() for b in bars})
        self.ledger = Ledger(cash=config.starting_capital_inr)

    def _fill_price(self, bar: Bar, side: str) -> float:
        slip = self.config.slippage_bps / 10_000
        return bar.open * (1 + slip) if side == "buy" else bar.open * (1 - slip)

    def run(self, decisions: list[Decision], upto: str | None = None) -> Result:
        result = Result()
        pending = sorted(decisions, key=lambda d: (d.date, d.decision_id))
        peak = self.config.starting_capital_inr

        for day in self.days:
            if upto and day > upto:
                break
            if result.halted_on is None:
                due, pending = ([d for d in pending if d.date < day],
                                [d for d in pending if d.date >= day])
                for d in due:
                    bar = self.prices.get(d.symbol, {}).get(day)
                    if bar is None:
                        result.skipped.append((d, f"no bar for {d.symbol} on {day}"))
                        continue
                    price = self._fill_price(bar, d.side)
                    cost = charges(d.side, d.qty, price, self.config.segment)["total"]
                    try:
                        self.ledger.apply_fill(
                            Fill(day, d.symbol, d.side, d.qty, price, cost))
                    except ValueError as e:
                        result.skipped.append((d, str(e)))

            closes = {s: bars[day].close for s, bars in self.prices.items()
                      if day in bars}
            equity = self.ledger.equity(closes)
            peak = max(peak, equity)
            hit = (self.config.starting_capital_inr - equity
                   >= self.config.max_loss_inr)
            result.marks.append(DayMark(day, equity, self.ledger.cash,
                                        peak - equity, hit))
            if hit and result.halted_on is None:
                result.halted_on = day
        return result
