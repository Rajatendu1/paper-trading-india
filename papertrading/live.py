"""Live-session guards and virtual execution for timestamped quote snapshots.

This module is deliberately narrower than a trading daemon. It accepts an
already retrieved quote snapshot, proves that the quote belongs to the NSE
normal session and is fresh enough, then plans or applies virtual delivery
fills against the existing paper ledger. It does not poll a quote API, append
to the decision log, connect to a broker or place a real order.

Live-session execution stays `prepared_not_activated` until the feed and
cadence decision is made explicitly. Raw live quote snapshots are local
research inputs, not content to republish without the data source's
permission.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

from .config import Config
from .costs import charges
from .ledger import Decision, Fill, Ledger


@dataclass(frozen=True)
class LiveSessionPolicy:
    status: str
    exchange: str
    segment: str
    timezone: str
    session_open: time
    session_close: time
    holidays: frozenset[str]
    max_quote_age_seconds: int
    allowed_exchanges: frozenset[str]
    source_delay_seconds: Mapping[str, int]
    public_redistribution: str

    @classmethod
    def load(cls, path: str | Path) -> "LiveSessionPolicy":
        return cls.from_mapping(json.loads(Path(path).read_text()))

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "LiveSessionPolicy":
        session = data.get("normal_session")
        quote_policy = data.get("quote_policy")
        if not isinstance(session, Mapping) or not isinstance(quote_policy, Mapping):
            raise ValueError("live session policy needs normal_session and quote_policy")
        policy = cls(
            status=str(data.get("status", "")),
            exchange=str(data.get("exchange", "")),
            segment=str(data.get("segment", "")),
            timezone=str(data.get("timezone", "")),
            session_open=_parse_clock(str(session.get("open", ""))),
            session_close=_parse_clock(str(session.get("close", ""))),
            holidays=frozenset(str(item) for item in data.get("holidays_2026", [])),
            max_quote_age_seconds=int(quote_policy.get("max_quote_age_seconds", 0)),
            allowed_exchanges=frozenset(
                str(item) for item in quote_policy.get("allowed_exchanges", [])
            ),
            source_delay_seconds={
                str(key): int(value)
                for key, value in dict(quote_policy.get("source_delay_seconds", {})).items()
            },
            public_redistribution=str(quote_policy.get("public_redistribution", "")),
        )
        policy.validate()
        return policy

    def validate(self) -> None:
        if self.status not in {"prepared_not_activated", "activated"}:
            raise ValueError("live session status must be prepared_not_activated or activated")
        if self.exchange != "NSE":
            raise ValueError("only the NSE cash-market session is modelled")
        if self.segment != "delivery":
            raise ValueError("only virtual delivery execution is enabled")
        if self.session_open >= self.session_close:
            raise ValueError("session open must be before session close")
        if self.max_quote_age_seconds < 1:
            raise ValueError("max_quote_age_seconds must be positive")
        if self.exchange not in self.allowed_exchanges:
            raise ValueError("allowed exchanges must include the modelled exchange")
        if not self.public_redistribution:
            raise ValueError("public quote redistribution boundary is required")
        ZoneInfo(self.timezone)  # raises if the configured timezone is invalid


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    quoted_at: datetime
    retrieved_at: datetime
    source: str
    exchange: str = "NSE"
    source_delay_seconds: int = 0

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "Quote":
        quote = cls(
            symbol=str(data.get("symbol", "")).strip().upper(),
            price=float(data.get("price", 0.0)),
            quoted_at=_parse_datetime(str(data.get("quoted_at", ""))),
            retrieved_at=_parse_datetime(str(data.get("retrieved_at", ""))),
            source=str(data.get("source", "")).strip(),
            exchange=str(data.get("exchange", "NSE")).strip().upper(),
            source_delay_seconds=int(data.get("source_delay_seconds", 0)),
        )
        quote.validate()
        return quote

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("quote symbol is required")
        if self.price <= 0:
            raise ValueError("quote price must be positive")
        if not self.source:
            raise ValueError("quote source is required")
        if self.source_delay_seconds < 0:
            raise ValueError("source delay cannot be negative")
        if self.quoted_at.tzinfo is None or self.retrieved_at.tzinfo is None:
            raise ValueError("quote timestamps must be timezone-aware")
        if self.retrieved_at < self.quoted_at:
            raise ValueError("retrieved_at cannot precede quoted_at")


def _parse_clock(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid session clock {value!r}") from exc


def _parse_datetime(value: str) -> datetime:
    if not value:
        raise ValueError("timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {value!r}")
    return parsed


def _local(value: datetime, policy: LiveSessionPolicy) -> datetime:
    return value.astimezone(ZoneInfo(policy.timezone))


def is_trading_day(day: str, policy: LiveSessionPolicy) -> bool:
    local_date = datetime.fromisoformat(day).date()
    return local_date.weekday() < 5 and day not in policy.holidays


def in_normal_session(moment: datetime, policy: LiveSessionPolicy) -> bool:
    local = _local(moment, policy)
    day = local.date().isoformat()
    return (
        is_trading_day(day, policy)
        and policy.session_open <= local.time().replace(tzinfo=None) <= policy.session_close
    )


def quote_rejection_reasons(
    quote: Quote,
    policy: LiveSessionPolicy,
    *,
    now: datetime,
) -> list[str]:
    """Explain why a quote cannot support a current virtual session fill."""
    reasons: list[str] = []
    if quote.exchange not in policy.allowed_exchanges:
        reasons.append(f"exchange {quote.exchange} is not enabled")
    configured_delay = policy.source_delay_seconds.get(quote.exchange, 0)
    if quote.source_delay_seconds != configured_delay:
        reasons.append(
            f"source delay for {quote.exchange} must be {configured_delay}s in this policy"
        )
    if not in_normal_session(now, policy):
        reasons.append("current time is outside the modelled NSE normal session")
    if not in_normal_session(quote.quoted_at, policy):
        reasons.append("quote timestamp is outside the modelled NSE normal session")
    age_seconds = (now - quote.quoted_at).total_seconds() + quote.source_delay_seconds
    if age_seconds > policy.max_quote_age_seconds:
        reasons.append(
            f"quote is stale: effective age {age_seconds:.0f}s exceeds "
            f"{policy.max_quote_age_seconds}s"
        )
    if quote.retrieved_at > now:
        reasons.append("quote retrieval timestamp is in the future")
    return reasons


def _fill_price(raw_price: float, side: str, config: Config) -> float:
    slip = config.slippage_bps / 10_000
    return raw_price * (1 + slip) if side == "buy" else raw_price * (1 - slip)


def run_session_decisions(
    decisions: list[Decision],
    quotes: Mapping[str, Quote],
    ledger: Ledger,
    config: Config,
    policy: LiveSessionPolicy,
    *,
    now: datetime,
    dry_run: bool = True,
) -> dict[str, object]:
    """Plan or apply virtual fills from timestamped quote snapshots.

    With dry_run=True no ledger object is changed. With dry_run=False the
    policy must be activated; fills are applied only to the in-memory paper
    Ledger supplied by the caller. Persistence, scheduling and quote polling
    remain separate runner decisions.
    """
    if not dry_run and policy.status != "activated":
        raise ValueError("live-session execution is prepared_not_activated")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if config.segment != policy.segment:
        raise ValueError("config and live-session policy segments differ")

    cash = ledger.cash
    positions = {
        symbol: position.qty
        for symbol, position in ledger.positions.items()
        if position.qty > 0
    }
    fills: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    for decision in sorted(decisions, key=lambda item: (item.date, item.decision_id)):
        quote = quotes.get(decision.symbol)
        if quote is None:
            skipped.append({
                "decision_id": decision.decision_id,
                "symbol": decision.symbol,
                "reason": "missing timestamped quote",
            })
            continue
        reasons = quote_rejection_reasons(quote, policy, now=now)
        if reasons:
            skipped.append({
                "decision_id": decision.decision_id,
                "symbol": decision.symbol,
                "reason": "; ".join(reasons),
                "quote_source": quote.source,
                "quoted_at": quote.quoted_at.isoformat(),
            })
            continue

        price = _fill_price(quote.price, decision.side, config)
        cost = charges(decision.side, decision.qty, price, config.segment)["total"]
        quote_local = _local(quote.quoted_at, policy)
        fill = Fill(
            date=quote_local.date().isoformat(),
            symbol=decision.symbol,
            side=decision.side,
            qty=decision.qty,
            price=round(price, 4),
            cost_total=round(cost, 6),
            reason="live-session-virtual",
        )
        if decision.side == "buy":
            required = fill.qty * fill.price + fill.cost_total
            if required > cash + 1e-9:
                skipped.append({
                    "decision_id": decision.decision_id,
                    "symbol": decision.symbol,
                    "reason": f"insufficient virtual cash: need {required:.2f}, have {cash:.2f}",
                })
                continue
        else:
            held = positions.get(decision.symbol, 0)
            if decision.qty > held:
                skipped.append({
                    "decision_id": decision.decision_id,
                    "symbol": decision.symbol,
                    "reason": f"cannot sell {decision.qty}; only {held} held",
                })
                continue

        if dry_run:
            if decision.side == "buy":
                cash -= fill.qty * fill.price + fill.cost_total
                positions[decision.symbol] = positions.get(decision.symbol, 0) + fill.qty
            else:
                cash += fill.qty * fill.price - fill.cost_total
                positions[decision.symbol] = positions.get(decision.symbol, 0) - fill.qty
                if positions[decision.symbol] == 0:
                    del positions[decision.symbol]
        else:
            ledger.apply_fill(fill)
            cash = ledger.cash
            positions = {
                symbol: position.qty
                for symbol, position in ledger.positions.items()
                if position.qty > 0
            }

        fills.append({
            "decision_id": decision.decision_id,
            "symbol": decision.symbol,
            "side": decision.side,
            "qty": decision.qty,
            "virtual_fill_price": fill.price,
            "estimated_cost_total": fill.cost_total,
            "quote": {
                "source": quote.source,
                "exchange": quote.exchange,
                "quoted_at": quote.quoted_at.isoformat(),
                "retrieved_at": quote.retrieved_at.isoformat(),
                "source_delay_seconds": quote.source_delay_seconds,
            },
        })

    return {
        "schema": 1,
        "status": "session_plan_not_executed" if dry_run else "virtual_fills_executed_local_only",
        "activation_status": policy.status,
        "dry_run": dry_run,
        "exchange": policy.exchange,
        "segment": policy.segment,
        "session_timezone": policy.timezone,
        "normal_session": {
            "open": policy.session_open.strftime("%H:%M"),
            "close": policy.session_close.strftime("%H:%M"),
        },
        "evaluated_at": now.isoformat(),
        "decision_count": len(decisions),
        "fills": fills,
        "skipped": skipped,
        "cash_after_virtual_fills": round(cash, 2),
        "positions_after_virtual_fills": dict(sorted(positions.items())),
        "quote_publication_boundary": policy.public_redistribution,
        "not_done": [
            "not appended to decisions/log.csv by this module",
            "not a broker order",
            "not real money",
            "no quote polling or scheduling was activated",
            "raw live quote snapshots are not approved for public redistribution",
        ],
    }
