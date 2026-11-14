"""Indian equity transaction cost model.

IMPORTANT: these rates are a configurable assumption modeled on one discount
broker's published charges (source below, fetched 2026-11-14). They are not
necessarily the user's broker or the cheapest available. Every charge is
returned itemized so results can be audited line by line, and every constant
can be overridden when constructing a ChargeModel.

Source: https://zerodha.com/charges/ (retrieved 2026-11-14)
"""
from __future__ import annotations

from dataclasses import dataclass

SOURCE_URL = "https://zerodha.com/charges/"
AS_OF = "2026-11-14"


@dataclass(frozen=True)
class ChargeModel:
    # Securities Transaction Tax
    stt_delivery: float = 0.001          # 0.1% on buy AND sell (delivery)
    stt_intraday_sell: float = 0.00025   # 0.025% on sell side only (intraday)
    # Exchange transaction charge (NSE)
    txn_nse: float = 0.0000307           # 0.00307% of turnover
    # SEBI charge: Rs 10 per crore of turnover
    sebi_per_crore: float = 10.0
    # GST on (brokerage + SEBI + transaction charges)
    gst: float = 0.18
    # Stamp duty, buy side only
    stamp_delivery_buy: float = 0.00015  # 0.015%
    stamp_intraday_buy: float = 0.00003  # 0.003%
    # DP charge: per scrip per day on DELIVERY sells, irrespective of quantity
    dp_per_scrip_sell: float = 15.34
    # Intraday brokerage: flat Rs 20 or 0.03% per executed order, lower of
    intraday_brokerage_flat: float = 20.0
    intraday_brokerage_pct: float = 0.0003


def charges(side: str, qty: int, price: float, segment: str,
            model: ChargeModel | None = None) -> dict[str, float]:
    """Itemized charges for one executed order.

    side: "buy" or "sell". segment: "delivery" or "intraday".
    Returns a dict of charge name -> amount in INR, plus "total".
    """
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be buy|sell, got {side!r}")
    if segment not in ("delivery", "intraday"):
        raise ValueError(f"segment must be delivery|intraday, got {segment!r}")
    if qty <= 0 or price <= 0:
        raise ValueError("qty and price must be positive")
    m = model or ChargeModel()

    value = qty * price

    if segment == "delivery":
        brokerage = 0.0
        stt = value * m.stt_delivery
        stamp = value * m.stamp_delivery_buy if side == "buy" else 0.0
        dp = m.dp_per_scrip_sell if side == "sell" else 0.0
    else:
        brokerage = min(m.intraday_brokerage_flat, value * m.intraday_brokerage_pct)
        stt = value * m.stt_intraday_sell if side == "sell" else 0.0
        stamp = value * m.stamp_intraday_buy if side == "buy" else 0.0
        dp = 0.0

    txn = value * m.txn_nse
    sebi = value * m.sebi_per_crore / 1e7
    gst = (brokerage + sebi + txn) * m.gst

    items = {
        "brokerage": brokerage,
        "stt": stt,
        "txn": txn,
        "sebi": sebi,
        "gst": gst,
        "stamp": stamp,
        "dp": dp,
    }
    items["total"] = sum(items.values())
    return items
