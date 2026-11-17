# Autonomous paper-trading policy v1 (2026-11-17)

This policy governs prospective virtual decisions only. It does not create a
broker connection, real order, account, payment or live-trading claim.

## Daily activity and allocation

- Delivery is the only enabled mode.
- No-trade is a valid daily outcome.
- At most 2 new virtual buys per day.
- New gross exposure across a day is capped at 20% of virtual equity.
- One position is capped at 10% of virtual equity, with at most 4 open
  positions.
- Each position risks at most 1% of virtual equity between its reference
  price and initial stop.
- Transaction costs still apply before execution; the planner's exposure cap
  is not permission to spend cash needed for charges.

## Stops and portfolio halt

- Initial stop: 1.5 x ATR(14) below the reference price, bounded to a 4%-8%
  distance. With too little history, the 4% minimum is used.
- Trailing stop: may move upward after favorable closes; it never moves down.
- Daily-bar limit: stops are evaluated after a close and can only create a
  sell decision for the next trading day's open. They are not guaranteed
  fills and are not hard floors; gaps can cross them.
- Overall halt: stop all new trades when virtual losses reach Rs 40,000 of
  the Rs 1,00,000 starting capital. Existing positions may then be liquidated
  at the next available open. This is not a hard cap.

## Mode gates

- Delivery: enabled because daily OHLCV data, a delivery cost model and a
  no-leverage ledger exist.
- Intraday: paused until intraday bars, same-day execution, square-off and
  liquidity assumptions are modelled.
- Futures: paused until contract, expiry, margin, leverage, rollover and
  derivative-cost data are modelled.
- Options: paused until option chains, expiry, premium/Greeks, liquidity,
  assignment, margin and derivative-cost data are modelled.

## Learning and strategy changes

Every decision, stop, skip and no-trade day must be logged before execution.
Reviews compare net return, drawdown, risk and skipped decisions against a
suitable benchmark. A strategy change is a new pre-specified experiment
version, never a retrospective rewrite after losses. AI decisions stay
labelled as AI decisions; they are not human judgement.
