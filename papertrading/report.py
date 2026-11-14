"""Summary reporting for the paper-trading experiment.

Reports describe the simulation only. They are not evidence of how the same
decisions would have done with real orders: paper fills ignore liquidity,
partial fills and real slippage beyond the configured assumption.
"""
from __future__ import annotations

from .config import Config
from .engine import Result


def summarize(config: Config, result: Result) -> dict:
    if not result.marks:
        return {"status": "no data"}
    first, last = result.marks[0], result.marks[-1]
    total_return = last.equity / config.starting_capital_inr - 1
    return {
        "period": f"{first.date} -> {last.date}",
        "starting_capital_inr": config.starting_capital_inr,
        "final_equity_inr": round(last.equity, 2),
        "total_return_pct": round(total_return * 100, 2),
        "max_drawdown_inr": round(max(m.drawdown for m in result.marks), 2),
        "loss_limit_inr": config.max_loss_inr,
        "loss_limit_hit": result.halted_on,
        "cost_model": "configurable assumption, see costs.py (not necessarily the user's broker)",
        "skipped_decisions": len(result.skipped),
        "note": "Paper simulation. Not a promise of profit or reliable income.",
    }


def summary_text(config: Config, result: Result) -> str:
    s = summarize(config, result)
    lines = [f"{k}: {v}" for k, v in s.items()]
    return "\n".join(lines)
