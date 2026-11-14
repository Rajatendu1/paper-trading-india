"""Configuration for the paper-trading experiment.

The simulation parameters (starting capital, loss limit) are public by the
owner's explicit decision (2026-11-14). Nothing here is real money: this
project never connects to a broker and never places real orders.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    starting_capital_inr: float = 100_000.0
    max_loss_inr: float = 40_000.0
    # Assumed slippage per side, in basis points. An explicit assumption,
    # not a measurement; real slippage can be worse.
    slippage_bps: float = 10.0
    benchmark_symbol: str = "^NSEI"  # NIFTY 50 on Yahoo Finance
    # Which cost model to apply: "delivery" (positions held overnight) or
    # "intraday" (squared off same day). See costs.py for what this changes.
    segment: str = "delivery"

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        data = json.loads(Path(path).read_text())
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Unknown config keys: {sorted(unknown)}")
        cfg = cls(**data)
        if cfg.segment not in ("delivery", "intraday"):
            raise ValueError(f"segment must be delivery|intraday, got {cfg.segment!r}")
        return cfg
