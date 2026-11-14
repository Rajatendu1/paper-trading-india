"""Strategy rules specified before any run.

Rules are fixed in docs/experiment.md BEFORE any run that reports them.
Changing a rule after seeing results and presenting the change as the
original plan is exactly the dishonesty the append-only experiment log
(experiments/log.md) exists to prevent: every run and every rule change is
recorded there with its result, good or bad.

EXP-001 rule (swing SMA crossover):
- Compute SMA(fast) and SMA(slow) of daily closes for one symbol.
- When SMA(fast) crosses ABOVE SMA(slow) at day D's close -> buy decision
  recorded on D (executes at D+1's open per engine rules).
- When SMA(fast) crosses BELOW SMA(slow) at day D's close -> sell decision
  for the full position, recorded on D.
- No pyramiding: at most one open buy per symbol at a time.
"""
from __future__ import annotations

from .data import Bar

RULE_NAME = "sma-cross-20-60"


def sma(closes: list[float], n: int) -> list[float | None]:
    """Simple moving average; None until n samples exist."""
    out: list[float | None] = []
    run = 0.0
    for i, c in enumerate(closes):
        run += c
        if i >= n:
            run -= closes[i - n]
        out.append(run / n if i >= n - 1 else None)
    return out


def generate_signals(bars: list[Bar], fast: int = 20, slow: int = 60
                     ) -> list[tuple[str, str]]:
    """Crossover signals from one symbol's bars.

    Returns [(date, "buy"|"sell"), ...] ordered by date. The decision is
    recorded on the signal date; the engine executes it at the next open.
    """
    if fast >= slow:
        raise ValueError("fast window must be shorter than slow window")
    bars = sorted(bars, key=lambda b: b.date)
    closes = [b.close for b in bars]
    f, s = sma(closes, fast), sma(closes, slow)

    signals: list[tuple[str, str]] = []
    prev_diff: float | None = None
    for b, fv, sv in zip(bars, f, s):
        if fv is None or sv is None:
            continue
        diff = fv - sv
        if prev_diff is not None:
            if prev_diff <= 0 < diff:
                signals.append((b.date, "buy"))
            elif prev_diff >= 0 > diff:
                signals.append((b.date, "sell"))
        prev_diff = diff
    # flatten alternating duplicates defensively (crossovers already
    # alternate, but never emit buy,buy in a row)
    out: list[tuple[str, str]] = []
    for d, side in signals:
        if out and out[-1][1] == side:
            continue
        out.append((d, side))
    return out
