# EXP-001: Swing SMA-crossover on NIFTY 50 stocks (pre-registration)

Written BEFORE the first run, on 2026-11-14. Any rule change after seeing
results is a new experiment entry in `experiments/log.md`, never an edit of
this one.

## Hypothesis

A simple, fully mechanical trend-following rule on liquid large-cap Indian
stocks, after realistic costs, may beat doing nothing. Whether it beats
buying and holding NIFTY 50 is an open question this experiment measures.
We do NOT claim in advance that it will make money.

## Universe

The 50 current NIFTY 50 constituents, snapshot from the official NSE
Indices CSV (niftyindices.com/IndexConstituent/ind_nifty50list.csv)
downloaded 2026-11-14. Known limitation: using today's membership
introduces survivorship bias - stocks that fell out of the index during the
period are absent. Results must be read with that bias stated.

## Data

Daily OHLCV from Yahoo Finance via yfinance 1.8.0, `auto_adjust=True`
(adjusted for splits and dividends). This is a deliberate per-experiment
convention: signals on raw prices misread bonuses/splits as crashes.
Documented limits: Yahoo is an unofficial source and adjustments can be
wrong or late; the engine's bhavcopy loader (raw, official) exists for
cross-checks but is not the feed for this run. Period: 2023-11-14 to
2026-11-13 (last available close at run time). Intraday is out of scope -
daily bars cannot validate same-day entries.

## Rules (frozen)

1. Signal: SMA(20) vs SMA(60) of daily closes, per symbol.
   - Cross above at close of day D: buy decision recorded on D.
   - Cross below at close of day D: sell decision for the full position.
2. Execution: next trading day's open, 10 bps assumed slippage per side.
3. Sizing: each buy = whole shares worth at most 25% of equity at the
   signal close; at most 4 concurrent positions; no pyramiding; a buy is
   skipped if cash is insufficient.
4. Costs: delivery-segment model in `papertrading/costs.py` (assumption
   modeled on one discount broker's published charges of 2026-11-14,
   applied uniformly across the whole period - actual historical rates
   differed; stated, not corrected for).
5. Loss limit: if mark-to-market loss reaches Rs 40,000 of the Rs 1,00,000
   virtual capital, the experiment halts and all open positions are
   liquidated at the next trading day's open. This is NOT a hard cap:
   overnight gaps can take losses past the limit, and that outcome will be
   reported, not hidden.

## Benchmark

NIFTY 50 index (`^NSEI`) buy-and-hold over the same period. Mismatch noted:
the index series is price-return while the strategy series is adjusted
(dividend-inclusive); this comparison is approximate and stated as such.

## What will be reported regardless of outcome

Total return net of itemized costs, max drawdown, number of trades, skipped
trades with reasons, loss-limit status, benchmark comparison, and every
skipped-day data problem. A losing result is reported exactly as it lands.

## What this experiment cannot show

Future performance, live fill quality (liquidity, partial fills, real
slippage), robustness to other periods, and anything intraday.
