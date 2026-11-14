"""Execution and mark-to-market engine.

Execution rule (fixed beforehand, stated here so it cannot drift):
a decision recorded on date D executes at the OPEN of the first trading day
AFTER D, at that open price plus assumed slippage, plus itemized transaction
costs. Decisions therefore never use same-day close information - no
lookahead by construction.

Loss-limit rule: when mark-to-market equity falls to or below
(starting_capital - max_loss) at a close, the experiment halts. All open
positions are liquidated at the OPEN of the next trading day that has a bar
for each symbol, and no new strategy decisions execute from the breach on.
IMPORTANT: this is not a hard cap. Prices can gap down overnight, so losses
can exceed the limit before liquidation fills happen. Nothing here simulates
or promises an exact floor.

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
    liquidated_on: str | None = None

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

    def _liquidate(self, day: str) -> bool:
        """Force-sell every open position at this day's open. Returns True
        when nothing remains held (symbols without a bar retry next day)."""
        for sym, pos in list(self.ledger.positions.items()):
            if pos.qty <= 0:
                continue
            bar = self.prices.get(sym, {}).get(day)
            if bar is None:
                continue  # no bar (suspended/missing) - retry next day
            price = self._fill_price(bar, "sell")
            cost = charges("sell", pos.qty, price, self.config.segment)["total"]
            self.ledger.apply_fill(
                Fill(day, sym, "sell", pos.qty, price, cost,
                     reason="loss-limit-liquidation"))
        return all(p.qty == 0 for p in self.ledger.positions.values())

    def history(self, symbol: str, upto: str) -> list[Bar]:
        """Bars for a symbol strictly up to and including a date. Strategy
        callbacks must use this - never engine.prices directly - so no
        future data can leak into a decision."""
        return [b for d, b in sorted(self.prices.get(symbol, {}).items())
                if d <= upto]

    def run(self, decisions: list[Decision] | None = None,
            upto: str | None = None, strategy=None) -> Result:
        """decisions: pre-specified Decision list. strategy: optional
        callback(day, engine, equity_at_close) -> list[Decision], invoked
        after each close while not halted; its decisions are dated that day
        and so execute at the next open like any others."""
        result = Result()
        pending = sorted(decisions or [], key=lambda d: (d.date, d.decision_id))
        peak = self.config.starting_capital_inr
        liquidating = False

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
                            Fill(day, d.symbol, d.side, d.qty, price, cost,
                                 reason="strategy"))
                    except ValueError as e:
                        result.skipped.append((d, str(e)))
            else:
                # halted: pending strategy decisions are dropped, not deferred
                if pending:
                    for d in pending:
                        result.skipped.append((d, f"halted on {result.halted_on}"))
                    pending = []
                if liquidating and self._liquidate(day):
                    liquidating = False
                    result.liquidated_on = day

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
                liquidating = any(p.qty > 0
                                  for p in self.ledger.positions.values())
                if not liquidating:
                    result.liquidated_on = day  # nothing to sell
            if result.halted_on is None and strategy is not None:
                for d in strategy(day, self, equity) or []:
                    if d.date != day:
                        raise ValueError(
                            f"strategy decision {d.decision_id} dated {d.date}, "
                            f"must be signal day {day}")
                    pending.append(d)
                pending.sort(key=lambda d: (d.date, d.decision_id))
        return result
